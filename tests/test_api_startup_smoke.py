from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")


def test_create_app_records_startup_manifest_and_route_inventory(env: None) -> None:  # noqa: ARG001
    app = create_app()

    manifest = app.state.startup_manifest

    assert manifest["status"] == "ready"
    assert manifest["route_count"] >= 1
    assert any(route["path"] == "/healthz" for route in manifest["route_inventory"])
    assert "/v1/advisor/advise" not in {route["path"] for route in manifest["route_inventory"]}
    assert "/v2/advisor/advise" not in {route["path"] for route in manifest["route_inventory"]}
    assert "/v2/advisor/health" not in {route["path"] for route in manifest["route_inventory"]}
    assert "/v3/agent/turn" not in {route["path"] for route in manifest["route_inventory"]}
    assert "/v1/advisor/*" in manifest["retired_surfaces"]
    assert "/v2/advisor/*" in manifest["retired_surfaces"]
