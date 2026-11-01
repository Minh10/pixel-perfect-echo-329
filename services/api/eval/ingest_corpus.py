"""Ingest the benchmark corpus through the production code path (validation -> job queue -> worker).

    python eval/ingest_corpus.py --data-dir eval/data/corpus --workers 4 [--parser pymupdf]

Documents: the FinanceBench subset (eval/benchmark/subset.json) plus the repository's synthetic fixtures
(used for chart questions).  Company/period metadata come from FinanceBench's document information file;
nothing is inferred.  Already-ingested documents (same sha256) are skipped, so the script is idempotent.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
from pathlib import Path

from app.config import Settings
from app.processing.validation import validate_pdf
from app.storage.db import Repository
from app.storage.files import FileStore
from app.worker import Worker

HERE = Path(__file__).parent
FB = HERE / "data" / "financebench"
FIXTURES = HERE.parent / "tests" / "fixtures"
TYPE_MAP = {"10K": "Annual Report", "10Q": "Quarterly Report"}


def corpus_manifest() -> list[dict]:
    docs = json.loads((HERE / "benchmark" / "subset.json").read_text())["financebench_documents"]
    info = {}
    for line in (FB / "data" / "financebench_document_information.jsonl").read_text().splitlines():
        rec = json.loads(line)
        info[rec["doc_name"]] = rec
    out = []
    for name in docs:
        meta = info[name]
        out.append({"key": name, "path": FB / "pdfs" / f"{name}.pdf", "title": name, "issuer": meta["company"],
                    "period": str(meta["doc_period"]), "doc_type": TYPE_MAP.get(meta["doc_type"])})
    out.append({"key": "SYNTHETIC_ANNUAL_REPORT_EXCERPT", "path": FIXTURES / "annual_report_excerpt.pdf",
                "title": "Fictional Example Holdings - Annual Report 2025 (synthetic fixture)",
                "issuer": "Fictional Example Holdings plc", "period": "2025", "doc_type": "Annual Report"})
    return out


def _work(settings: Settings) -> None:
    Worker(settings).run_until_idle(max_jobs=1000)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=HERE / "data" / "corpus")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--parser", default="pymupdf", choices=["pymupdf", "docling", "auto"])
    args = ap.parse_args()
    s = Settings(data_dir=args.data_dir, parser=args.parser, auto_index=False)
    repo, files = Repository(s.db_path), FileStore(s.documents_dir)
    known = {d["sha256"]: d for d in repo.list_documents()}
    mapping: dict[str, str] = {}
    for m in corpus_manifest():
        import hashlib

        data = m["path"].read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if sha in known:
            mapping[m["key"]] = known[sha]["id"]
            continue
        tmp = s.data_dir / "tmp" / f"{m['key']}.pdf"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        v = validate_pdf(tmp, len(data), sha, s.max_pages)
        doc_id = f"doc_{m['key'].lower()}"
        files.store_source(doc_id, v.tmp_path)
        repo.create_document_with_job(
            {"id": doc_id, "title": m["title"], "issuer": m["issuer"], "period": m["period"],
             "doc_type": m["doc_type"], "filename": m["path"].name, "size_bytes": v.size_bytes,
             "sha256": sha, "page_count": v.page_count},
            requested_parser=args.parser, max_attempts=1,
        )
        mapping[m["key"]] = doc_id
    t = time.time()
    procs = [mp.Process(target=_work, args=(s,)) for _ in range(args.workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    docs = repo.list_documents()
    print(f"ingested {len(docs)} documents in {time.time() - t:.0f}s")
    for d in sorted(docs, key=lambda d: d["id"]):
        print(f"  {d['id']:<40} {d['status']:<8} pages={d['page_count']:<4} {d['error_message'] or ''}")
    (args.data_dir / "manifest.json").write_text(json.dumps(mapping, indent=2))


if __name__ == "__main__":
    main()
