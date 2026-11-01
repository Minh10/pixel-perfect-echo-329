"""End-to-end Milestone 3 API: upload -> parse -> auto-index -> retrieve -> citations -> QA -> delete."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import rag_routes
from app.config import Settings
from app.main import create_app
from app.worker import Worker
from tests.helpers import ScriptedLLM

pytestmark = pytest.mark.integration


@pytest.fixture
def env(tmp_path: Path, fixtures_dir: Path):
    s = Settings(data_dir=tmp_path / "data", parser="pymupdf", embedder="none", qa_method="bm25")
    client, worker = TestClient(create_app(s)), Worker(s)
    with (fixtures_dir / "annual_report_excerpt.pdf").open("rb") as fh:
        doc = client.post("/api/v1/documents", files={"file": ("a.pdf", fh)},
                          data={"issuer": "Fictional Example Holdings plc", "period": "2025"}).json()["document"]
    assert worker.run_until_idle() == 2  # parse + index
    return client, worker, doc


def test_index_retrieve_cite_and_delete(env) -> None:
    client, worker, doc = env
    st = client.get(f"/api/v1/documents/{doc['id']}/index").json()
    assert st["indexed"] and {r["chunkSet"] for r in st["runs"]} == {"layout", "flat"}
    layout = next(r for r in st["runs"] if r["chunkSet"] == "layout")
    assert layout["denseStatus"] == "unavailable"  # embedder=none

    r = client.post("/api/v1/retrieve", json={"query": "operating profit 2025", "method": "hybrid", "k": 3}).json()
    assert r["effectiveMethod"] == "bm25" and any("dense retrieval unavailable" in w for w in r["warnings"])
    top = r["results"][0]["chunk"]
    assert top["kind"] == "table" and top["pages"] == [2] and top["regions"][0]["workspaceEvidenceId"] == "ev-p2-b003"
    assert top["pageImageUrl"].endswith(f"/documents/{doc['id']}/pages/2/image")
    assert client.get(top["pageImageUrl"]).status_code == 200

    cite = client.get(f"/api/v1/citations/{top['chunkId']}").json()
    assert cite["chunkId"] == top["chunkId"] and "Operating profit: 2025 = 703" in cite["content"]

    # re-index: same ids, no duplicates
    before = client.get("/api/v1/index/status").json()["chunks"]
    assert client.post(f"/api/v1/documents/{doc['id']}/index").status_code == 202
    assert client.post(f"/api/v1/documents/{doc['id']}/index").status_code == 409  # already queued
    worker.run_until_idle()
    assert client.get("/api/v1/index/status").json()["chunks"] == before
    assert client.get(f"/api/v1/citations/{top['chunkId']}").status_code == 200

    assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 204
    assert client.get(f"/api/v1/citations/{top['chunkId']}").json()["error"]["code"] == "citation_not_found"
    assert client.get("/api/v1/index/status").json()["chunks"] == {"layout": 0, "flat": 0}


def test_qa_unavailable_without_llm_is_honest(env) -> None:
    client, _, _ = env
    r = client.post("/api/v1/qa", json={"question": "What was operating profit in 2025?"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "llm_unavailable"
    status = client.get("/api/v1/index/status").json()
    assert status["llm"]["available"] is False and "api_key" not in str(status).lower().replace("api_key_env", "")


def test_qa_end_to_end_with_scripted_llm(env, monkeypatch) -> None:
    client, _, doc = env

    class Planner(ScriptedLLM):
        def generate_json(self, system, parts, schema, schema_name):
            e = re.search(r"\[(E\d+)\] TABLE", parts[0]).group(1)
            self.responses = [{
                "status": "answered", "insufficiency_reason": None,
                "answer": "Operating profit was 703 (GBP m) in 2025.",
                "citations": [{"evidence_id": e, "quote": "Operating profit: 2025 = 703"}],
                "operands": [{"id": "a", "evidence_id": e, "quote": "703", "row_label": "Operating profit", "period": "2025",
                              "metric": "operating profit", "currency": "GBP",
                              "scale": "millions", "value_kind": "reported"}],
                "calculations": [], "final": {"ref": "a", "unit": "GBP millions", "metric": "operating profit"}}]
            return super().generate_json(system, parts, schema, schema_name)

    monkeypatch.setattr(rag_routes, "get_llm", lambda cfg: Planner([]))
    r = client.post("/api/v1/qa", json={"question": "What was Fictional Example Holdings' operating profit in 2025?"}).json()
    assert r["status"] == "answered" and r["value"] == {"value": "703", "unit": "GBP millions",
                                                         "valueKind": "reported", "source": "a"}
    assert r["documentsConsidered"][0]["documentId"] == doc["id"]
    c = r["citations"][0]
    assert c["evidenceKind"] == "table" and c["chunk"]["regions"][0]["page"] == 2
    assert r["usage"]["llmCalls"] == 1 and r["usage"]["costUsd"] is None
    assert "confidence" not in r  # no invented confidence score


def test_figure_interpretation_requires_llm(env) -> None:
    client, _, doc = env
    assert client.post(f"/api/v1/documents/{doc['id']}/figures/p3-b002/interpret").status_code == 503
    assert client.post(f"/api/v1/documents/{doc['id']}/figures/p2-b003/interpret").json()["error"]["code"] == "not_a_figure"
    assert client.get(f"/api/v1/documents/{doc['id']}/figures/p3-b002/interpretation").status_code == 404
