"""Second-pass check of benchmark ground truth against RAW PDF page text (independent of the system under test).

    PYTHONPATH=. python eval/grounding/verify_cases.py --corpus <corpus dir> eval/grounding/cases_*.jsonl

For every case it confirms, using only `pymupdf.Page.get_text()` (no parse.json, no normalization, no binding
code), that the quoted value, the row label / metric phrase and the period text exist on the cited page, and
that each value listed in the case note is printed there.  It cannot confirm the semantic label (which column a
value belongs to); that was read off the page by the case author and is recorded in `note` for human review.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pymupdf

MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip().lower()


def squash(s: str) -> str:
    return re.sub(r"[\s$]+", "", s.replace("\xa0", " ")).lower()


def verify(case: dict, corpus: Path) -> list[str]:
    pdf = corpus / "documents" / case["doc"] / "source.pdf"
    raw = pymupdf.open(pdf)[case["page"] - 1].get_text()
    t, sq = norm(raw), squash(raw)
    cl = case["claim"]
    problems = []
    if squash(cl["quote"]) not in sq:
        problems.append(f"quote {cl['quote']!r} not on page")
    if norm(cl["row_label"]) not in t:
        problems.append(f"row label {cl['row_label']!r} not on page")
    per = cl.get("period") or ""
    years = re.findall(r"(?:19|20)\d{2}", per)
    if not years or not all(y in t for y in years):
        problems.append(f"period year(s) {per!r} not on page")
    if re.search(MONTHS, per, re.IGNORECASE) and norm(re.sub(r"\s*,\s*", " ", per)) not in norm(t.replace(",", " ")):
        problems.append(f"period date {per!r} not printed on page")
    if case["kind"] == "text":
        sentence = next((s for s in re.split(r"(?<=[.;])\s+", t) if squash(cl["quote"]) in squash(s)), None)
        if sentence is None:
            problems.append("no sentence holds the quote")
    for num in re.findall(r"\(?\$?\d[\d,]*\.?\d*\)?", case.get("note", "")):
        if len(re.sub(r"\D", "", num)) >= 2 and squash(num) not in sq:
            problems.append(f"note value {num!r} not on page")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args()
    bad = 0
    n = 0
    for f in args.files:
        for line in f.read_text().splitlines():
            case = json.loads(line)
            n += 1
            probs = verify(case, args.corpus)
            if probs:
                bad += 1
                print(f"{case['id']}: " + "; ".join(probs))
    print(f"verified {n - bad}/{n} cases against raw PDF text")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
