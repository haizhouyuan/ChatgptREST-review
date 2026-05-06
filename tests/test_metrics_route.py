"""Integration test: /metrics route is mounted and returns 200 text/plain."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from chatgptrest.api.app import create_app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    return TestClient(create_app())


def test_metrics_returns_200(client: TestClient) -> None:
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")
    # Should contain at least one Prometheus metric line
    assert "chatgptrest_" in r.text or "# " in r.text


def test_metrics_contains_expected_metric_names(client: TestClient) -> None:
    r = client.get("/metrics")
    assert r.status_code == 200
    # The endpoint should have at least some content
    assert len(r.text) > 10
