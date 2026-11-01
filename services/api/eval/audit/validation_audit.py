"""Adversarial audit of the operand-association validator (PR #2) on REAL 10-K chunks.

    PYTHONPATH=. python eval/audit/validation_audit.py --db <corpus>/finaudit.sqlite3

Each case = (real chunk, question, operand label, quoted value, scale) with a ground truth of ACCEPT
(the value really is that metric/period/unit) or REJECT (deliberately mis-associated on exactly one
dimension).  Ground truth is read off the chunk text itself, which is printed in the output for review.
Metrics: false accepts (wrong association accepted — safety failure) and false rejects (correct
association rejected — causes unnecessary abstention).  No LLM is involved.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.indexing.store import ChunkStore
from app.qa.pipeline import operand_association_checks

T, R = "ACCEPT", "REJECT"
# (id, doc, page, kind, must-contain, question, label, quote, scale, truth, dimension, note)
CASES = [
    ("V01", "doc_3m_2018_10k", 60, "table", "Purchases of property", "What was 3M's capital expenditure in 2018?",
     "Purchases of property, plant and equipment (PP&E) 2018", "(1,577)", "millions", T, "-", "exact row label"),
    ("V02", "doc_3m_2018_10k", 60, "table", "Purchases of property", "What was 3M's capital expenditure in 2018?",
     "Capital expenditure 2018", "(1,577)", "millions", T, "-", "paraphrased label (how an analyst/LLM would say it)"),
    ("V03", "doc_3m_2018_10k", 60, "table", "Purchases of property", "What was 3M's capital expenditure in 2018?",
     "Purchases of property, plant and equipment (PP&E) 2018 (USD millions)", "(1,577)", "millions", T, "-",
     "currency in label; 3M reports in USD but the chunk states only '(Millions)'"),
    ("V04", "doc_3m_2018_10k", 60, "table", "Purchases of property", "What was 3M's capital expenditure in 2018?",
     "Purchases of property, plant and equipment (PP&E) 2017", "(1,577)", "millions", R, "period", "2018 value labelled 2017"),
    ("V05", "doc_3m_2018_10k", 60, "table", "Purchases of property", "What was 3M's capital expenditure in 2018?",
     "Purchases of property, plant and equipment (PP&E) 2017", "(1,373)", "millions", R, "period vs question",
     "true 2017 value, but the question asks 2018"),
    ("V06", "doc_3m_2018_10k", 60, "table", "Purchases of property", "What was 3M's capital expenditure in 2018?",
     "Proceeds from sale of PP&E and other assets 2018", "(1,577)", "millions", R, "metric", "value of another row"),
    ("V07", "doc_3m_2018_10k", 60, "table", "Purchases of property", "What was 3M's capital expenditure in 2018?",
     "Purchases of property, plant and equipment (PP&E) 2018", "(1,577)", "thousands", R, "scale", "millions stated as thousands"),
    ("V08", "doc_3m_2018_10k", 60, "table", "Purchases of property", "What was 3M's capital expenditure in 2018?",
     "Purchases of property, plant and equipment (PP&E) 2018 (EUR)", "(1,577)", "millions", R, "currency", "wrong currency"),
    ("V09", "doc_amd_2022_10k", 56, "table", "Cash and cash equivalents", "What was AMD's cash and cash equivalents at the end of 2022?",
     "Cash and cash equivalents 2022", "$4,835", "millions", T, "-", "balance sheet without column labels or units line"),
    ("V10", "doc_amd_2022_10k", 56, "table", "Cash and cash equivalents", "What was AMD's cash and cash equivalents at the end of 2022?",
     "Cash and cash equivalents 2022", "$2,535", "millions", R, "period", "2021 value labelled 2022"),
    ("V11", "doc_amd_2022_10k", 56, "table", "Cash and cash equivalents", "What was AMD's cash and cash equivalents at the end of 2022?",
     "Cash and cash equivalents 2022", "$2,535", "units", R, "period", "same as V10 with scale 'units' to isolate the period check"),
    ("V12", "doc_boeing_2022_10k", 24, "table", "Revenues: $66,608", "What were Boeing's revenues in 2022?",
     "Revenues 2022", "$66,608", "millions", T, "-", "years only in the table title"),
    ("V13", "doc_boeing_2022_10k", 24, "table", "Revenues: $66,608", "What were Boeing's revenues in 2022?",
     "Revenues 2022", "$62,286", "millions", R, "period", "2021 value labelled 2022"),
    ("V14", "doc_boeing_2022_10k", 24, "table", "Revenues: $66,608", "What was Boeing's net loss in 2022?",
     "Net loss attributable to Boeing Shareholders 2022", "($4,935)", "millions", T, "-", "loss row, parenthesised"),
    ("V15", "doc_boeing_2022_10k", 24, "table", "Revenues: $66,608", "What was Boeing's net loss in 2022?",
     "Net loss attributable to Boeing Shareholders 2022", "($3,547)", "millions", R, "metric", "loss from operations labelled net loss"),
    ("V16", "doc_pepsico_2022_10k", 79, "table", "FLNA: 2022", "What were PepsiCo's FLNA restructuring charges in 2022?",
     "FLNA restructuring charges 2022", "$46", "millions", T, "-", "segment row, proper period columns, no units line in chunk"),
    ("V17", "doc_pepsico_2022_10k", 79, "table", "FLNA: 2022", "What were PepsiCo's FLNA restructuring charges in 2022?",
     "FLNA restructuring charges 2022", "$210", "units", R, "period/column",
     "cumulative 'Plan to Date through 12/31/2022' value labelled FY2022 (scale 'units' isolates the period check)"),
    ("V18", "doc_pepsico_2022_10k", 79, "table", "FLNA: 2022", "What were PepsiCo's FLNA restructuring charges in 2022?",
     "FLNA restructuring charges 2022", "$28", "units", R, "period", "2021 value labelled 2022"),
    ("V19", "doc_synthetic_annual_report_excerpt", 2, "table", "Operating profit", "What was operating profit in 2025?",
     "Operating profit 2025", "703", "millions", T, "-", "synthetic fixture (GBP m)"),
    ("V20", "doc_synthetic_annual_report_excerpt", 2, "table", "Operating profit", "What was operating profit in 2025?",
     "Operating profit 2025", "1,794", "millions", R, "metric", "gross profit value labelled operating profit"),
    ("V21", "doc_synthetic_annual_report_excerpt", 2, "table", "Operating profit", "What was operating profit in 2025?",
     "Operating profit 2025", "591", "millions", R, "period", "2024 value labelled 2025"),
    ("V22", "doc_synthetic_annual_report_excerpt", 2, "text", "Group revenue increased", "What was operating profit in 2025?",
     "Operating profit 2025", "703", "millions", T, "-", "narrative statement"),
    ("V23", "doc_synthetic_annual_report_excerpt", 2, "text", "Group revenue increased", "What was revenue in 2025?",
     "Revenue 2025", "703", "millions", R, "metric", "operating profit figure labelled revenue (same sentence)"),
    ("V24", "doc_3m_2018_10k", 39, "text", "Employment increased", "How many positions did 3M's employment increase by in 2018?",
     "Employment increase 2018", "1,980", "units", T, "-", "real narrative with two years in one sentence"),
    ("V25", "doc_3m_2018_10k", 39, "text", "Employment increased", "How many positions did 3M's employment decrease by in 2017?",
     "Employment decrease 2017", "48", "units", T, "-", "the 2017 clause of the same sentence"),
    ("V26", "doc_3m_2018_10k", 39, "text", "Employment increased", "How many positions did 3M's employment increase by in 2018?",
     "Employment increase 2018", "48", "units", R, "period/metric", "2017 decrease labelled 2018 increase"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("eval/audit/validation_audit_results.json"))
    args = ap.parse_args()
    store = ChunkStore(args.db)
    results = []
    for cid, doc, page, kind, must, q, label, quote, scale, truth, dim, note in CASES:
        chunks = [r for r in store.chunks_for(doc, "layout") if r["pages"] == [page] and r["kind"] == kind and must in r["content"]]
        if not chunks:
            raise SystemExit(f"{cid}: chunk not found ({doc} p{page} {kind} {must!r})")
        ch = chunks[0]
        assert quote.replace(" ", "") in ch["content"].replace(" ", ""), f"{cid}: quote not in chunk"
        checks = operand_association_checks(kind=kind, label=label, quote=quote, scale=scale, text=ch["content"],
                                            question=q, units=ch["meta"].get("units"))
        accepted = all(c["ok"] for c in checks)
        failed = [f"{c['check']}: {c['detail']}" for c in checks if not c["ok"]]
        outcome = ("correct" if (accepted == (truth == T)) else ("FALSE_ACCEPT" if accepted else "FALSE_REJECT"))
        results.append({"id": cid, "document": doc, "page": page, "kind": kind, "chunk_id": ch["chunk_id"],
                        "question": q, "label": label, "quote": quote, "scale": scale, "truth": truth,
                        "corrupted_dimension": dim, "note": note, "engine": "ACCEPT" if accepted else "REJECT",
                        "outcome": outcome, "failed_checks": failed,
                        "checks": {c["check"]: c["ok"] for c in checks}})
    args.out.write_text(json.dumps(results, indent=1))
    fa = [r for r in results if r["outcome"] == "FALSE_ACCEPT"]
    fr = [r for r in results if r["outcome"] == "FALSE_REJECT"]
    nt, nr = sum(r["truth"] == T for r in results), sum(r["truth"] == R for r in results)
    print(f"cases={len(results)} correct-associations={nt} corrupted={nr}")
    print(f"FALSE ACCEPTS {len(fa)}/{nr}: {[r['id'] for r in fa]}")
    print(f"FALSE REJECTS {len(fr)}/{nt}: {[r['id'] for r in fr]}")
    for r in results:
        print(f"{r['id']} truth={r['truth']} engine={r['engine']} {r['outcome']:<13} {r['note']}")
        for f in r["failed_checks"]:
            print(f"      x {f}")


if __name__ == "__main__":
    main()
