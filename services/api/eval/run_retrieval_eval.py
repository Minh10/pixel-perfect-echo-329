"""Retrieval evaluation: B1-B4 (+ ablations) under identical conditions.

    python eval/run_retrieval_eval.py --corpus eval/data/corpus [--embedders onnx wordllama] [--reindex]

Settings evaluated for every configuration:
  * filtered — retrieval restricted to the item's gold document(s) (isolates ranking quality)
  * open     — retrieval over the whole corpus (cross-document: the system must find the right filing)
Unanswerable items have no gold evidence and are excluded from retrieval metrics.
Outputs: eval/results/retrieval_results.json, eval/results/retrieval_report.md,
         eval/results/raw/retrieval_runs.jsonl (per-query rankings, git-ignored).
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

from app.config import Settings
from app.evaluation import metrics as M
from app.indexing.service import index_document
from app.indexing.store import ChunkStore
from app.indexing.vectors import close_clients
from app.retrieval.embeddings import get_embedder
from app.retrieval.search import BASELINES, Retriever
from app.storage.db import Repository
from app.storage.files import FileStore

HERE = Path(__file__).parent
KS = (5, 10)


def build_index(s: Settings, embedders: list[str]) -> dict:
    repo, files, store = Repository(s.db_path), FileStore(s.documents_dir), ChunkStore(s.db_path)
    stats: dict = {"documents": 0, "seconds": {}, "chunks": {}}
    docs = [d for d in repo.list_documents() if d["status"] == "ready"]
    stats["documents"] = len(docs)
    for name in embedders:
        es = s.model_copy(update={"embedder": name})
        t = time.perf_counter()
        for d in docs:
            index_document(d, files, store, es)
        stats["seconds"][name] = round(time.perf_counter() - t, 1)
    stats["chunks"] = {cs: store.count(chunk_set=cs) for cs in ("layout", "flat")}
    return stats


def evaluate(s: Settings, items: list[dict], embedder: str, configs: dict, store: ChunkStore) -> tuple[dict, list]:
    es = s.model_copy(update={"embedder": embedder})
    retriever = Retriever(es, store=store, embedder=get_embedder(es))
    retriever.search("warm up query", method="hybrid", chunk_set="layout", k=5)  # load model / collections
    results, raw = {}, []
    for cname, (method, chunk_set) in configs.items():
        for setting in ("filtered", "open"):
            per = {m: [] for m in ("recall@5", "recall@10", "hit@5", "hit@10", "mrr", "ndcg@10")}
            lat, cats = [], []
            for it in items:
                gold = {(d, p) for d, p in it["gold_pages"]}
                doc_ids = it["document_ids"] if setting == "filtered" else None
                t = time.perf_counter()
                res = retriever.search(it["question"], method=method, chunk_set=chunk_set, document_ids=doc_ids, k=10)
                lat.append((time.perf_counter() - t) * 1000)
                chunks = store.get(h.chunk_id for h in res.hits)
                ranked = [{(chunks[h.chunk_id]["document_id"], p) for p in chunks[h.chunk_id]["pages"]} for h in res.hits]
                per["recall@5"].append(M.recall_at_k(ranked, gold, 5))
                per["recall@10"].append(M.recall_at_k(ranked, gold, 10))
                per["hit@5"].append(M.hit_at_k(ranked, gold, 5))
                per["hit@10"].append(M.hit_at_k(ranked, gold, 10))
                per["mrr"].append(M.mrr(ranked, gold))
                per["ndcg@10"].append(M.ndcg_at_k(ranked, gold, 10))
                cats.append(it["tags"])
                raw.append({"config": cname, "embedder": embedder, "setting": setting, "item": it["id"],
                            "ranked": [[h.chunk_id, chunks[h.chunk_id]["document_id"], chunks[h.chunk_id]["pages"]]
                                       for h in res.hits], "warnings": res.warnings,
                            "effective": res.effective_method})
            key = f"{cname}|{embedder}|{setting}" if method != "bm25" else f"{cname}|-|{setting}"
            summary = {m: {"mean": M.mean(v), "ci95": M.bootstrap_ci(v)} for m, v in per.items()}
            by_tag: dict[str, dict] = {}
            for tag in sorted({t for c in cats for t in c}):
                idx = [i for i, c in enumerate(cats) if tag in c]
                by_tag[tag] = {"n": len(idx), **{m: M.mean([per[m][i] for i in idx]) for m in ("recall@5", "recall@10", "mrr")}}
            results[key] = {"config": cname, "method": method, "chunk_set": chunk_set, "setting": setting,
                            "embedder": embedder if method != "bm25" else None, "n": len(items),
                            "metrics": summary, "per_query": per, "by_tag": by_tag,
                            "latency_ms": {"p50": M.percentile(lat, 0.5), "p95": M.percentile(lat, 0.95)}}
    return results, raw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=HERE / "data" / "corpus")
    ap.add_argument("--benchmark", type=Path, default=HERE / "data" / "benchmark.jsonl")
    ap.add_argument("--embedders", nargs="+", default=["onnx"])
    ap.add_argument("--reindex", action="store_true")
    ap.add_argument("--report-only", action="store_true", help="regenerate the markdown from retrieval_results.json")
    args = ap.parse_args()
    if args.report_only:
        saved = json.loads((HERE / "results" / "retrieval_results.json").read_text())
        write_report(HERE / "results" / "retrieval_report.md", saved["meta"], saved["results"], saved["comparisons"])
        return
    s = Settings(data_dir=args.corpus, embedder_model_path=HERE.parent / "models" / "all-MiniLM-L6-v2")
    store = ChunkStore(s.db_path)
    index_stats = build_index(s, args.embedders) if args.reindex or store.count() == 0 else {"reused": True}
    items = [json.loads(line) for line in args.benchmark.read_text().splitlines()]
    items = [i for i in items if i["gold_pages"]]
    results, raw = {}, []
    for k, emb in enumerate(args.embedders):
        configs = BASELINES if k == 0 else {n: c for n, c in BASELINES.items() if c[0] != "bm25"}
        r, rw = evaluate(s, items, emb, configs, store)
        results.update(r)
        raw += rw
    comparisons = {}
    emb0 = args.embedders[0]

    def key(c: str, setting: str) -> str:
        m = BASELINES[c][0]
        return f"{c}|{'-' if m == 'bm25' else emb0}|{setting}"

    for setting in ("filtered", "open"):
        for a, b in [("B1", "B2"), ("B1", "B3"), ("B1", "B4"), ("B3", "B4"), ("B2", "B4")]:
            for metric in ("recall@5", "recall@10", "mrr"):
                comparisons[f"{b} vs {a}|{setting}|{metric}"] = M.paired_test(
                    results[key(a, setting)]["per_query"][metric], results[key(b, setting)]["per_query"][metric])
    meta = {"items": len(items), "index": index_stats, "embedders": args.embedders,
            "machine": {"python": platform.python_version(), "cpu": platform.processor() or platform.machine()},
            "rrf_k": s.rrf_k, "candidates": s.retrieval_candidates,
            "embedder_ids": {e: get_embedder(s.model_copy(update={"embedder": e})).id for e in args.embedders}}
    out = HERE / "results"
    (out / "raw").mkdir(parents=True, exist_ok=True)
    (out / "raw" / "retrieval_runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in raw))
    (out / "retrieval_results.json").write_text(json.dumps({"meta": meta, "results": results,
                                                            "comparisons": comparisons}, indent=1, default=float))
    write_report(out / "retrieval_report.md", meta, results, comparisons)
    close_clients()
    print((out / "retrieval_report.md").read_text())


def _f(x: float) -> str:
    return "—" if x != x else f"{x:.3f}"


def write_report(path: Path, meta: dict, results: dict, comps: dict) -> None:
    L = ["# Retrieval evaluation", "",
         f"Items with gold evidence: {meta['items']} · embedders: {meta['embedder_ids']} · RRF k={meta['rrf_k']} · "
         f"candidate depth {meta['candidates']} · Python {meta['machine']['python']}", "",
         "Page-level relevance (see `app/evaluation/metrics.py`). 95% CIs: percentile bootstrap over queries (2,000 resamples).", ""]
    for setting, title in (("filtered", "Gold document(s) given (ranking quality)"), ("open", "Open corpus (cross-document)")):
        L += [f"## {title}", "", "| Config | Method | Chunks | Embedder | Recall@5 | Recall@10 | Hit@5 | MRR | nDCG@10 | p50 ms | p95 ms |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in results.values():
            if r["setting"] != setting:
                continue
            m = r["metrics"]
            cell = lambda k: f"{_f(m[k]['mean'])} [{_f(m[k]['ci95'][0])}, {_f(m[k]['ci95'][1])}]"  # noqa: E731
            L.append(f"| {r['config']} | {r['method']} | {r['chunk_set']} | {r['embedder'] or '—'} | {cell('recall@5')} | "
                     f"{cell('recall@10')} | {_f(m['hit@5']['mean'])} | {cell('mrr')} | {_f(m['ndcg@10']['mean'])} | "
                     f"{r['latency_ms']['p50']:.1f} | {r['latency_ms']['p95']:.1f} |")
        L.append("")
    adj = M.holm({k: v["p"] for k, v in comps.items()})
    L += ["## Paired comparisons (difference = second − first; sign-flip permutation test, 10,000 permutations)", "",
          f"`p` is uncorrected; `p (Holm)` is Holm–Bonferroni-adjusted over all {len(comps)} comparisons in this table.", "",
          "| Comparison | Setting | Metric | Δ mean | 95% CI | p | p (Holm) | n |", "|---|---|---|---|---|---|---|---|"]
    for k, v in comps.items():
        name, setting, metric = k.split("|")
        L.append(f"| {name} | {setting} | {metric} | {v['diff']:+.3f} | [{v['ci_low']:+.3f}, {v['ci_high']:+.3f}] | "
                 f"{v['p']:.4f} | {adj[k]:.4f} | {v['n']} |")
    L += ["", "## Recall@10 by question tag (filtered setting)", "", "| Config | Tag | n | Recall@5 | Recall@10 | MRR |", "|---|---|---|---|---|---|"]
    for r in results.values():
        if r["setting"] == "filtered":
            for tag, v in r["by_tag"].items():
                L.append(f"| {r['config']} ({r['embedder'] or 'bm25'}) | {tag} | {v['n']} | {_f(v['recall@5'])} | {_f(v['recall@10'])} | {_f(v['mrr'])} |")
    path.write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
