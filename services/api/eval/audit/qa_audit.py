"""Run every executable stage of end-to-end QA on the audit question set and write per-question results.

    PYTHONPATH=. python eval/audit/qa_audit.py --corpus <corpus dir> --csv <out.csv>

Stages per question:
  1. gold verification — executed check that each gold label and value occur together (value within 12 lines
     after the label) in the PDF page's raw text layer, or that 'absent' terms really are absent;
  2. document routing + retrieval (QA default: dense over layout chunks, k=8; plus hybrid for comparison);
  3. validator upper bound — the gold operand, claimed with the verbatim source row label, the period of the
     column it sits in (or the question's single year) and the gold scale, is bound by the M3.5 evidence
     validator (app/qa/evidence_binding.py) against the stored FinancialFacts / statement text of the chunk
     (if even this is rejected the pipeline cannot answer).  The PR #2 baseline (1/30) used the PR #2 validator;
  4. LLM answer — only if a provider is configured; otherwise recorded as NOT RUN with the exact blocker.
Answer accuracy, numerical accuracy, citation precision/recall, abstention quality, LLM latency and token cost
are filled ONLY from a real LLM run; they are never estimated.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path

import pymupdf

from app.config import Settings
from app.evaluation.metrics import numbers_in, parse_number
from app.indexing.store import ChunkStore
from app.indexing.vectors import close_clients
from app.qa.evidence import route_documents
from app.qa.llm import LLMUnavailable, get_llm
from app.qa.evidence_binding import OperandClaim, bind_table, bind_text
from app.retrieval.search import Retriever
from app.storage.db import Repository

HERE = Path(__file__).parent
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
NOT_MEASURED = "NOT MEASURED (no LLM run)"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip().lower()


class Pages:
    def __init__(self, docs_dir: Path) -> None:
        self.dir, self.cache = docs_dir, {}

    def lines(self, doc: str, page: int) -> list[str]:
        if doc not in self.cache:
            with pymupdf.open(self.dir / doc / "source.pdf") as d:
                self.cache[doc] = [[norm(ln) for ln in p.get_text().splitlines() if ln.strip()] for p in d]
        return self.cache[doc][page - 1]

    def all_text(self, doc: str) -> str:
        self.lines(doc, 1)
        return " ".join(" ".join(p) for p in self.cache[doc])


def verify_evidence(pages: Pages, ev: dict) -> tuple[bool, str]:
    lines = pages.lines(ev["doc"], ev["page"])
    if "contains" in ev:  # context fact (unit statement, period header) on the page
        blob = " ".join(lines)
        missing = [c for c in ev["contains"] if norm(c) not in blob]
        return (not missing, f"p{ev['page']} contains {ev['contains']}" if not missing else f"MISSING {missing} on p{ev['page']}")
    label, value = norm(ev["label"]), norm(ev["value"])
    for i, ln in enumerate(lines):
        window = " ".join(lines[i:i + 3])
        if label in window:
            after = " ".join(lines[i:i + 12])
            if value in after:
                return True, after[:160]
    return False, f"label {ev['label']!r} with value {ev['value']!r} not found on p{ev['page']}"


def is_amount(ev: dict) -> bool:
    if "contains" in ev:
        return False
    return parse_number(ev["value"]) is not None and not YEAR.fullmatch(ev["value"].strip())


def best_case_validation(store: ChunkStore, it: dict, ev: dict) -> tuple[str, str]:
    """Return (verdict, detail) for the gold operand with the truest claim we can give."""
    target = parse_number(ev["value"])
    chunks = [c for c in store.chunks_for(ev["doc"], "layout") if ev["page"] in c["pages"] and c["kind"] in ("table", "text")
              and any(n == target for n in numbers_in(c["content"]))]
    if not chunks:
        return "NO_CHUNK", f"no layout chunk on p{ev['page']} contains {ev['value']}"
    scale = "percent" if "%" in ev["value"] else "millions"
    if ev["value"].strip("()").replace(".", "").isdigit() and "." in ev["value"]:
        scale = "percent"  # e.g. effective tax rate "(0.6)"
    qy = YEAR.findall(it["question"])
    q_period = qy[-1] if len(set(qy)) == 1 else None
    last = ("REJECT", "no candidate chunk")
    for ch in sorted(chunks, key=lambda c: c["kind"] != "table"):
        meta = ch.get("meta") or {}
        if ch["kind"] == "table":
            facts = list(store.facts(meta.get("factIds") or []).values())
            rl = norm(ev["label"])
            own = [f for f in facts if f.get("value") is not None and abs(float(f["value"])) == abs(float(target))
                   and rl in norm(f["rowLabel"] + " " + (f.get("rowGroup") or ""))]
            per = (own[0].get("period") or {}) if len(own) == 1 else {}
            period = per.get("label") if (per.get("fiscalYear") or per.get("endDate")) else q_period
            claim = OperandClaim(id="gold", quote=ev["value"], row_label=ev["label"], period=period,
                                 metric=ev["label"], scale=scale)
            checks = bind_table(claim, facts, it["question"],
                                context=" ".join(x for x in (meta.get("title"), meta.get("context")) if x))[0] \
                if facts else [{"check": "operand_facts_available", "ok": False, "detail": "no facts for chunk"}]
        else:
            claim = OperandClaim(id="gold", quote=ev["value"], row_label=ev["label"], period=q_period,
                                 metric=ev["label"], scale=scale)
            checks = bind_text(claim, ch["content"], it["question"])[0]
        failed = [f"{c['check']}: {c['detail']}" for c in checks if not c["ok"]]
        if not failed:
            return "ACCEPT", f"{ch['kind']} claim period={claim.period!r} scale={scale}"
        last = ("REJECT", "; ".join(failed))
    return last


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--items", type=Path, default=HERE / "qa_audit_set.jsonl")
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    s = Settings(data_dir=args.corpus, embedder_model_path=HERE.parents[1] / "models" / "all-MiniLM-L6-v2")
    repo, store = Repository(s.db_path), ChunkStore(s.db_path)
    docs = repo.list_documents()
    pages = Pages(s.documents_dir)
    retriever = Retriever(s, store=store)
    retriever.search("warm up", method="dense", chunk_set="layout", k=1)
    try:
        get_llm(s)
        llm_blocker = None
    except LLMUnavailable as exc:
        llm_blocker = str(exc)
    items = [json.loads(line) for line in args.items.read_text().splitlines() if line.strip()]
    rows = []
    for it in items:
        gold_ev = it.get("evidence", [])
        ver = [verify_evidence(pages, ev) for ev in gold_ev]
        chk = it.get("check")
        if chk and chk["type"] == "absent_terms":
            targets = [d["id"] for d in docs] if chk["doc"] == "*" else [chk["doc"]]
            present = [(t, d) for d in targets for t in chk["terms"] if norm(t) in pages.all_text(d)]
            ver.append((not present, "absent: " + ", ".join(chk["terms"]) if not present else f"PRESENT {present}"))
        elif chk:
            ver.append((True, "period logic: " + chk["reason"]))
        verified = all(v[0] for v in ver)
        routed = [d["documentId"] for d in route_documents(it["question"], docs)]
        gold_pages = {(e["doc"], e["page"]) for e in gold_ev if is_amount(e)} or {(e["doc"], e["page"]) for e in gold_ev}
        ret = {}
        for method in ("dense", "hybrid"):
            t = time.perf_counter()
            res = retriever.search(it["question"], method=method, chunk_set="layout", document_ids=routed or None, k=8)
            ms = (time.perf_counter() - t) * 1000
            got = store.get(h.chunk_id for h in res.hits)
            ranked = [(got[h.chunk_id]["document_id"], got[h.chunk_id]["pages"][0]) for h in res.hits]
            covered = {g for g in gold_pages if g in ranked}
            first = next((i + 1 for i, r in enumerate(ranked) if r in gold_pages), None)
            ret[method] = {"ranked": ranked, "covered": len(covered), "first": first, "ms": round(ms, 1),
                           "effective": res.effective_method}
        validations = []
        if it["gold_status"] == "answer":
            for ev in gold_ev:
                if is_amount(ev):
                    v, d = best_case_validation(store, it, ev)
                    validations.append((ev["doc"], ev["page"], ev["value"], v, d))
        # failure category from executed (pre-LLM) stages only
        cats = []
        if not verified:
            cats.append("gold_unverified")
        gold_docs = {e["doc"] for e in gold_ev if is_amount(e)}
        if routed and gold_docs and not gold_docs <= set(routed):
            cats.append("routing_miss")
        if not routed and it["gold_status"] == "answer":
            cats.append("routing_none(open corpus)")
        if it["gold_status"] == "answer":
            d = ret["dense"]
            if d["covered"] == 0:
                cats.append("retrieval_miss@8")
            elif d["covered"] < len(gold_pages):
                cats.append("retrieval_partial@8")
            rej = [v for v in validations if v[3] != "ACCEPT"]
            if rej:
                checks = sorted({m.split(":")[0] for v in rej for m in v[4].split("; ") if ":" in m} | {v[3] for v in rej if v[3] == "NO_CHUNK"})
                cats.append("validator_rejects_gold(" + ",".join(checks) + ")")
        rows.append({
            "id": it["id"], "category": it["category"] + ("+" + "+".join(it["tags"]) if it.get("tags") else ""),
            "question": it["question"], "gold_status": it["gold_status"], "gold_answer": it["gold_answer"],
            "gold_value": it.get("gold_value", ""), "gold_unit": it.get("gold_unit", ""),
            "gold_evidence": "; ".join(f"{e['doc']} p.{e['page']} [{e['label']} → {e['value']}]" if "label" in e
                                      else f"{e['doc']} p.{e['page']} [contains {e['contains']}]" for e in gold_ev)
                             or (chk or {}).get("reason", "") or f"absent terms {(chk or {}).get('terms')}",
            "gold_verified": "PASS" if verified else "FAIL",
            "gold_verification_detail": " || ".join(v[1] for v in ver),
            "routed_documents": ",".join(routed) or "(none: whole corpus)",
            "retrieval_dense_top8": " ".join(f"{d.removeprefix('doc_')}:p{p}" for d, p in ret["dense"]["ranked"]),
            "gold_pages_in_dense_top8": f"{ret['dense']['covered']}/{len(gold_pages)}" if it["gold_status"] == "answer" else "n/a",
            "first_gold_rank_dense": ret["dense"]["first"] or "", "dense_effective_method": ret["dense"]["effective"],
            "gold_pages_in_hybrid_top8": f"{ret['hybrid']['covered']}/{len(gold_pages)}" if it["gold_status"] == "answer" else "n/a",
            "first_gold_rank_hybrid": ret["hybrid"]["first"] or "",
            "retrieval_latency_ms_dense": ret["dense"]["ms"], "retrieval_latency_ms_hybrid": ret["hybrid"]["ms"],
            "validator_best_case": " | ".join(f"{v[2]}@p{v[1]}:{v[3]}" for v in validations) or "n/a",
            "validator_failed_checks": " | ".join(v[4] for v in validations if v[3] != "ACCEPT"),
            "llm_status": "NOT RUN — " + llm_blocker if llm_blocker else "RUN",
            "system_answer": "" if llm_blocker else "(see qa run)", "system_value": "", "system_citations": "",
            "answer_correct": NOT_MEASURED, "numeric_correct": NOT_MEASURED, "citation_precision": NOT_MEASURED,
            "citation_recall": NOT_MEASURED, "abstention_correct": NOT_MEASURED, "llm_latency_ms": NOT_MEASURED,
            "input_tokens": NOT_MEASURED, "output_tokens": NOT_MEASURED, "cost_usd": NOT_MEASURED,
            "failure_categories_pre_llm": "; ".join(cats) or "none detected before the LLM stage",
        })
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    if args.json:
        args.json.write_text(json.dumps(rows, indent=1))
    close_clients()
    print(f"{len(rows)} items · gold verified {sum(r['gold_verified'] == 'PASS' for r in rows)}/{len(rows)} · LLM: "
          f"{rows[0]['llm_status']}")
    for r in rows:
        print(f"{r['id']:<4} {r['gold_verified']} dense {r['gold_pages_in_dense_top8']:<4} hybrid {r['gold_pages_in_hybrid_top8']:<4} "
              f"val {r['validator_best_case'][:60]:<60} | {r['failure_categories_pre_llm'][:110]}")


if __name__ == "__main__":
    main()
