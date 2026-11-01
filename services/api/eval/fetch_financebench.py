"""Download the FinanceBench open-source sample (questions + source PDFs) at a pinned commit.

FinanceBench (Islam et al., 2023, arXiv:2311.11944, https://github.com/patronus-ai/financebench) provides
human-annotated questions, gold answers and evidence pages over real SEC filings. Neither the data nor the
PDFs are redistributed in this repository. This script fetches them into eval/data/financebench/ (git-ignored)
and verifies every file against eval/financebench.lock.json.

    python eval/fetch_financebench.py              # download + verify the benchmark subset
    python eval/fetch_financebench.py --write-lock # (maintainers) record checksums after a fresh download
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

COMMIT = "cc39aeb4afdf33909ee1412188bf89035950c2eb"
BASE = f"https://raw.githubusercontent.com/patronus-ai/financebench/{COMMIT}"
HERE = Path(__file__).parent
OUT = HERE / "data" / "financebench"
LOCK = HERE / "financebench.lock.json"
SUBSET = HERE / "benchmark" / "subset.json"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _get(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=300) as r, tmp.open("wb") as fh:  # noqa: S310 - pinned https URL
        while chunk := r.read(1 << 20):
            fh.write(chunk)
    tmp.replace(dest)


def files_for(doc_names: list[str]) -> list[str]:
    return ["data/financebench_open_source.jsonl", "data/financebench_document_information.jsonl",
            *[f"pdfs/{d}.pdf" for d in doc_names]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-lock", action="store_true")
    args = ap.parse_args()
    docs = json.loads(SUBSET.read_text())["financebench_documents"]
    lock = json.loads(LOCK.read_text()) if LOCK.exists() else {"commit": COMMIT, "files": {}}
    if lock.get("commit") != COMMIT:
        print(f"lock file is for commit {lock.get('commit')}, script pins {COMMIT}", file=sys.stderr)
        return 2
    bad = 0
    for rel in files_for(docs):
        dest = OUT / rel
        if not dest.exists():
            print(f"download {rel}")
            _get(f"{BASE}/{rel}", dest)
        digest = _sha256(dest)
        if args.write_lock:
            lock["files"][rel] = digest
        elif lock["files"].get(rel) != digest:
            print(f"CHECKSUM MISMATCH {rel}: {digest} != {lock['files'].get(rel)}", file=sys.stderr)
            bad += 1
    if args.write_lock:
        LOCK.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
        print(f"wrote {LOCK}")
    print(f"{len(files_for(docs))} files in {OUT}; {bad} checksum failures")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
