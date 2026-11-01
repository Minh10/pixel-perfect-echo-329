"""End-to-end QA evaluation (answer correctness, numerical accuracy, citations, abstention, latency, cost).

    FINAUDIT_LLM_PROVIDER=anthropic FINAUDIT_LLM_MODEL=claude-opus-5-5 FINAUDIT_LLM_API_KEY=... \
    FINAUDIT_LLM_PRICE_INPUT_PER_MTOK=4 FINAUDIT_LLM_PRICE_OUTPUT_PER_MTOK=20 \
    python eval/run_qa_eval.py --corpus eval/data/corpus [--limit N]

Requires a configured LLM; without one it exits with an explanation and writes no results.
Scoring (per item):
  * numeric gold (FinanceBench bare-number answers, chart C2): absolute value match within 1% relative
    (`numeric_match`) against the pipeline's deterministic `value`, else any number in the answer text
    (sign-insensitive because FinanceBench states outflows as positive amounts);
  * text gold: token F1 vs the gold answer is reported, but correctness of free-text answers needs human or
    LLM-judge review — the per-item outputs (results/raw/qa_runs.jsonl) are written for that purpose;
  * citations: page-level precision/recall vs gold evidence pages;
  * abstention: precision/recall/F1 of abstaining, with unanswerable items as positives.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

from app.config import Settings
from app.evaluation import metrics as M
from app.indexing.store import ChunkStore
from app.qa.llm import LLMError, LLMProvider, LLMUnavailable, get_llm
from app.qa.pipeline import QAPipeline
from app.qa.schemas import QARequest
from app.retrieval.search import Retriever
from app.storage.db import Repository

HERE = Path(__file__).parent


def score_item(it: dict, r: dict) -> dict:
    should_abstain = it["category"] == "unanswerable"
    did_abstain = r["status"] == "abstained"
    gold = {(d, p) for d, p in it["gold_pages"]}
    cited = {(c["chunk"]["documentId"], p) for c in r.get("citations", []) for p in c["chunk"]["pages"]}
    cp, cr = M.citation_pr(cited, gold) if gold else (float("nan"), float("nan"))
    out = {"id": it["id"], "category": it["category"], "status": r["status"],
           "should_abstain": should_abstain, "did_abstain": did_abstain,
           "citation_precision": cp, "citation_recall": cr, "numeric_correct": None, "token_f1": None}
    if it.get("gold_value") is not None and not did_abstain:
        gv = Decimal(it["gold_value"])
        pv = Decimal(r["value"]["value"]) if r.get("value") else None
        # Sign-insensitive: FinanceBench states outflows as positive amounts ("$1577.00" for "(1,577)").
        ok = M.numeric_match(abs(pv), abs(gv)) if pv is not None else False
        if not ok:  # e.g. the headline number is in the answer text but final.ref pointed elsewhere
            ok = any(M.numeric_match(abs(n), abs(gv)) for n in M.numbers_in(r.get("answer") or ""))
        out["numeric_correct"] = ok
    elif it.get("gold_value") is not None:
        out["numeric_correct"] = False
    if it.get("answer") and not should_abstain:
        out["token_f1"] = M.token_f1(r.get("answer") or "", it["answer"])
    return out


def run(s: Settings, items: list[dict], llm: LLMProvider) -> tuple[list[dict], list[dict]]:
    repo, store = Repository(s.db_path), ChunkStore(s.db_path)
    pipe = QAPipeline(s, store, Retriever(s, store=store), llm, repo.list_documents())
    raw, scores = [], []
    for it in items:
        t = time.perf_counter()
        try:
            resp = pipe.answer(QARequest(question=it["question"])).model_dump(by_alias=True)
        except LLMError as exc:
            resp = {"status": "error", "error": str(exc), "citations": []}
        resp["wall_ms"] = (time.perf_counter() - t) * 1000
        raw.append({"item": it["id"], "question": it["question"], "gold": it.get("answer"), "response": resp})
        if resp["status"] != "error":
            scores.append(score_item(it, resp) | {"latency_ms": resp["wall_ms"],
                                                  "input_tokens": resp["usage"]["inputTokens"],
                                                  "output_tokens": resp["usage"]["outputTokens"],
                                                  "cost_usd": resp["usage"]["costUsd"]})
    return raw, scores


def summarize(scores: list[dict]) -> dict:
    num = [s["numeric_correct"] for s in scores if s["numeric_correct"] is not None]
    answerable = [s for s in scores if not s["should_abstain"]]
    costs = [s["cost_usd"] for s in scores if s["cost_usd"] is not None]
    return {
        "n": len(scores),
        "numerical_accuracy": sum(num) / len(num) if num else float("nan"), "n_numeric": len(num),
        "token_f1_text": M.mean([s["token_f1"] for s in answerable if s["token_f1"] is not None]),
        "answer_rate_answerable": M.mean([0.0 if s["did_abstain"] else 1.0 for s in answerable]),
        "citation_precision": M.mean([s["citation_precision"] for s in scores]),
        "citation_recall": M.mean([s["citation_recall"] for s in scores]),
        "abstention": M.abstention_scores([(s["should_abstain"], s["did_abstain"]) for s in scores]),
        "latency_ms": {"p50": M.percentile([s["latency_ms"] for s in scores], 0.5),
                       "p95": M.percentile([s["latency_ms"] for s in scores], 0.95)},
        "tokens": {"input": sum(s["input_tokens"] or 0 for s in scores), "output": sum(s["output_tokens"] or 0 for s in scores)},
        "cost_usd_total": sum(costs) if len(costs) == len(scores) and costs else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=HERE / "data" / "corpus")
    ap.add_argument("--benchmark", type=Path, default=HERE / "data" / "benchmark.jsonl")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    s = Settings(data_dir=args.corpus, embedder_model_path=HERE.parent / "models" / "all-MiniLM-L6-v2")
    try:
        llm = get_llm(s)
    except LLMUnavailable as exc:
        print(f"QA evaluation not run: {exc}. Configure FINAUDIT_LLM_PROVIDER/MODEL and the API key env var.",
              file=sys.stderr)
        return 2
    items = [json.loads(line) for line in args.benchmark.read_text().splitlines()][: args.limit]
    raw, scores = run(s, items, llm)
    out = HERE / "results"
    (out / "raw").mkdir(parents=True, exist_ok=True)
    (out / "raw" / "qa_runs.jsonl").write_text("".join(json.dumps(r, default=str) + "\n" for r in raw))
    summary = {"provider": llm.provider, "model": llm.model, "retrieval": {"method": s.qa_method, "chunkSet": s.qa_chunk_set,
               "topK": s.qa_top_k}, "overall": summarize(scores),
               "by_category": {c: summarize([x for x in scores if x["category"] == c])
                               for c in sorted({x["category"] for x in scores})},
               "errors": sum(1 for r in raw if r["response"]["status"] == "error")}
    (out / "qa_results.json").write_text(json.dumps(summary, indent=1, default=float))
    print(json.dumps(summary, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
