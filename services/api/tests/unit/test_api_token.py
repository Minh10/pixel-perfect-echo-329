"""FINAUDIT_API_TOKEN gates document routes and leaves the health probe open."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_unset_token_leaves_document_routes_open(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path / "data", parser="pymupdf", api_token=None)))
    assert client.get("/api/v1/documents").status_code == 200


def test_token_required_except_health(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path / "data", parser="pymupdf", api_token="secret")))
    assert client.get("/api/v1/health").status_code == 200
    denied = client.get("/api/v1/documents")
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "unauthorized"
    assert client.get("/api/v1/documents", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/v1/documents", headers={"Authorization": "Bearer secret"}).status_code == 200
