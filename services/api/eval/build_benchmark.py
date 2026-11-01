"""Build the FINAUDIT benchmark (eval/data/benchmark.jsonl) from FinanceBench + constructed items.

    python eval/build_benchmark.py --corpus eval/data/corpus

* FinanceBench items: every open-source question on the subset documents (no filtering by difficulty or
  system performance).  Gold pages = FinanceBench evidence_page_num + 1.  Each evidence page is verified
  against the PDF's own text layer (token coverage of the annotator's evidence_text); if the evidence is
  found on an adjacent page instead, the page is corrected and flagged.  The verification table is written
  to eval/results/benchmark_report.md.
* Constructed items (eval/benchmark/constructed.jsonl, our own, labelled as such):
  - cross_document: comparisons whose components are FinanceBench human gold answers; gold pages = union.
  - unanswerable: verified by executed checks (term absence in the document text, or period logic).
  - chart: synthetic fixture whose true bar values are defined in the generator source.
FinanceBench text is not redistributed: the output goes to eval/data/ (git-ignored).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pymupdf

from app.evaluation.metrics import parse_number

HERE = Path(__file__).parent
FB = HERE / "data" / "financebench"
TOK = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> set[str]:
    return {t for t in TOK.findall(s.lower().replace(",", "")) if len(t) > 2 or t.isdigit()}


def coverage(evidence: str, page_text: str) -> float:
    ev = _tokens(evidence)
    return len(ev & _tokens(page_text)) / len(ev) if ev else 0.0


def categorize(q: dict, pages: set[int]) -> tuple[str, list[str]]:
    reasoning = (q.get("question_reasoning") or "").lower()
    ans_num = parse_number(q["answer"]) is not None and len(q["answer"].split()) <= 2
    category = "numerical" if ("numerical" in reasoning or ans_num) else "factual"
    tags = [category]
    if len(pages) > 1:
        tags.append("multi_page")
    return category, tags


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=HERE / "data" / "corpus")
    ap.add_argument("--out", type=Path, default=HERE / "data" / "benchmark.jsonl")
    args = ap.parse_args()
    manifest = json.loads((args.corpus / "manifest.json").read_text())
    subset = set(json.loads((HERE / "benchmark" / "subset.json").read_text())["financebench_documents"])
    texts: dict[str, list[str]] = {}

    def page_texts(key: str) -> list[str]:
        if key not in texts:
            src = args.corpus / "documents" / manifest[key] / "source.pdf"
            with pymupdf.open(src) as d:
                texts[key] = [p.get_text("text") for p in d]
        return texts[key]

    items, report = [], []
    for line in (FB / "data" / "financebench_open_source.jsonl").read_text().splitlines():
        q = json.loads(line)
        if q["doc_name"] not in subset:
            continue
        gold: set[tuple[str, int]] = set()
        flags = []
        for ev in q["evidence"]:
            key, stated = ev["doc_name"], ev["evidence_page_num"] + 1
            pts = page_texts(key)
            cov = {p: coverage(ev["evidence_text"], pts[p - 1]) for p in (stated - 1, stated, stated + 1)
                   if 1 <= p <= len(pts)}
            best = max(cov, key=lambda p: (cov[p], p == stated))
            if cov.get(stated, 0) >= 0.8:
                status, page = "verified", stated
            elif cov[best] >= 0.8:
                status, page = "shifted", best
            else:
                status, page = "unverified", stated
            flags.append(status)
            gold.add((manifest[key], page))
            report.append((q["financebench_id"], key, stated, page, status, round(cov.get(stated, 0), 2), round(cov[best], 2)))
        pages = {p for _, p in gold}
        category, tags = categorize(q, pages)
        gv = parse_number(q["answer"]) if parse_number(q["answer"]) is not None and len(q["answer"].split()) <= 2 else None
        items.append({
            "id": q["financebench_id"], "source": "financebench", "category": category, "tags": tags,
            "question": q["question"], "answer": q["answer"], "answer_kind": "number" if gv is not None else "text",
            "gold_value": str(gv) if gv is not None else None,
            "document_ids": sorted({d for d, _ in gold}), "gold_pages": sorted([list(g) for g in gold]),
            "page_alignment": flags, "company": q["company"], "doc_name": q["doc_name"],
            "question_reasoning": q.get("question_reasoning"), "question_type": q.get("question_type"),
        })
    by_id = {i["id"]: i for i in items}

    for line in (HERE / "benchmark" / "constructed.jsonl").read_text().splitlines():
        c = json.loads(line)
        it = {"id": c["id"], "source": "constructed", "category": c["category"], "tags": [c["category"]],
              "question": c["question"], "answer": c["answer"], "answer_kind": c["answer_kind"],
              "gold_value": c.get("gold_value"), "verification": c.get("verification")}
        if c["category"] == "cross_document":
            parts = [by_id[d] for d in c["derived_from"]]
            it["gold_pages"] = sorted({tuple(g) for p in parts for g in p["gold_pages"]})
            it["document_ids"] = sorted({d for p in parts for d in p["document_ids"]})
            it["derived_from"] = c["derived_from"]
        elif c["category"] == "unanswerable":
            chk = c["check"]
            keys = list(manifest) if chk["document"] == "*" else [chk["document"]]
            if chk["type"] == "absent_terms":
                for key in keys:
                    blob = " ".join(page_texts(key)).lower()
                    found = [t for t in chk["terms"] if t in blob]
                    if found:
                        raise SystemExit(f"{c['id']}: term(s) {found} occur in {key}; item is not unanswerable")
                it["verification"] = f"executed: terms {chk['terms']} absent from {chk['document']} text layer"
            else:
                it["verification"] = f"period logic: {chk['reason']}"
            it["gold_pages"], it["document_ids"] = [], []
        else:  # chart
            doc_id = manifest[c["document"]]
            it["gold_pages"] = [[doc_id, p] for p in c["gold_pages"]]
            it["document_ids"] = [doc_id]
            it["requires_image"] = c.get("requires_image", False)
        items.append(it)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(i) + "\n" for i in items))
    _write_report(items, report)
    print(f"wrote {len(items)} items to {args.out}")


def _write_report(items: list[dict], report: list[tuple]) -> None:
    from collections import Counter

    out = HERE / "results" / "benchmark_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    cats = Counter(i["category"] for i in items)
    tags = Counter(t for i in items for t in i["tags"])
    status = Counter(r[4] for r in report)
    lines = ["# Benchmark composition and evidence-page verification", "",
             "Generated by `eval/build_benchmark.py`. FinanceBench question text is not reproduced here.", "",
             "## Composition", "", "| Category | Items |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(cats.items())]
    lines += ["", f"Tag `multi_page` (gold evidence on >= 2 pages): {tags.get('multi_page', 0)} items.", "",
              "## FinanceBench evidence-page verification", "",
              "Coverage = share of the annotator's evidence tokens found in the PDF page's text layer.", "",
              f"Verified on stated page: {status.get('verified', 0)}; shifted to adjacent page: "
              f"{status.get('shifted', 0)}; unverified: {status.get('unverified', 0)} (of {len(report)} evidence entries).",
              "", "| FinanceBench id | Document | Stated page (1-based) | Used page | Status | Coverage stated | Best |",
              "|---|---|---|---|---|---|---|"]
    lines += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |" for r in report]
    out.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
