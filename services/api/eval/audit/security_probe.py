"""Runtime security probes against an in-process API instance (no network exposure).

    PYTHONPATH=. python eval/audit/security_probe.py

Uses a temporary data dir with the synthetic fixture.  A dummy LLM key value is placed in the process
environment only to check that no endpoint echoes it; it is not a real credential and is never sent anywhere
(provider stays 'none').
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

DUMMY = "dummy-not-a-real-key-7f3a"
os.environ["FINAUDIT_LLM_API_KEY"] = DUMMY

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.worker import Worker  # noqa: E402

FIX = Path(__file__).parents[2] / "tests" / "fixtures" / "annual_report_excerpt.pdf"


def main() -> None:
    d = Path(tempfile.mkdtemp())
    s = Settings(data_dir=d, parser="pymupdf", embedder="none")
    c = TestClient(create_app(s))
    results = []

    def rec(name, ok, detail):
        results.append((name, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

    with FIX.open("rb") as fh:
        doc = c.post("/api/v1/documents", files={"file": ('evil"\r\nX-Injected: 1.pdf', fh, "application/pdf")}).json()
    doc_id = doc["document"]["id"] if "document" in doc else None
    Worker(s).run_until_idle()
    rec("upload with CRLF/quote filename accepted safely", doc_id is not None, f"stored filename={doc.get('document', {}).get('filename')!r}")
    if doc_id:
        r = c.get(f"/api/v1/documents/{doc_id}/source")
        cd = r.headers.get("content-disposition", "")
        rec("no header injection via filename", "X-Injected" not in r.headers and "\r" not in cd and "\n" not in cd,
            f"content-disposition={cd!r}")
    for path in ["/api/v1/documents/..%2F..%2Fetc/source", "/api/v1/documents/doc_x%2F..%2F..%2Fpasswd",
                 f"/api/v1/documents/{doc_id}/blocks/..%2F..%2Fsource.pdf/image",
                 f"/api/v1/documents/{doc_id}/pages/0/image", f"/api/v1/documents/{doc_id}/pages/999999/image"]:
        r = c.get(path)
        rec(f"traversal/out-of-range rejected {path.split('/api/v1')[1][:48]}", r.status_code in (404, 409, 422),
            f"status={r.status_code}")
    r = c.get(f"/api/v1/documents/{doc_id}/pages/1/image", params={"dpi": 100000})
    rec("dpi clamped", r.status_code == 200 and len(r.content) < 20_000_000, f"status={r.status_code} bytes={len(r.content)}")
    r = c.options("/api/v1/documents", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    rec("CORS refuses unknown origin", "access-control-allow-origin" not in {k.lower() for k in r.headers},
        f"status={r.status_code} acao={r.headers.get('access-control-allow-origin')}")
    bodies = [c.get("/api/v1/index/status").text, c.get("/api/v1/health").text,
              c.post("/api/v1/qa", json={"question": "What was operating profit in 2025?"}).text,
              c.get("/openapi.json").text]
    rec("configured key never echoed", all(DUMMY not in b for b in bodies), "checked index/status, health, qa error, openapi")
    r = c.post("/api/v1/qa", json={"question": "x" * 5000})
    rec("oversized question rejected", r.status_code == 422, f"status={r.status_code}")
    r = c.post("/api/v1/retrieve", json={"query": "profit", "k": 10000})
    rec("retrieve k bounded", r.status_code == 422, f"status={r.status_code}")
    r = c.post("/api/v1/qa", json={"question": "What was operating profit in 2025?", "method": "sql"})
    rec("qa method enum enforced", r.status_code == 422, f"status={r.status_code}")
    print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} probes passed")


if __name__ == "__main__":
    main()
