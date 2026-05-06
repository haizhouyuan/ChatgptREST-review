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
    monkeypatch.delenv("CHATGPTREST_API_TOKEN", raising=False)
    monkeypatch.delenv("CHATGPTREST_OPS_TOKEN", raising=False)


def test_create_app_does_not_mount_v3_agent_routes(env: None) -> None:  # noqa: ARG001
    app = create_app()
    route_paths = {route["path"] for route in app.state.startup_manifest["route_inventory"]}

    assert "/v3/agent/turn" not in route_paths
    assert "/v3/agent/health" not in route_paths
    assert "/v3/agent/*" in app.state.startup_manifest["retired_surfaces"]


def test_v3_agent_turn_is_not_available(env: None) -> None:  # noqa: ARG001
    app = create_app()
    client = TestClient(app)

    response = client.post("/v3/agent/turn", json={"message": "hello"})

    assert response.status_code == 404


def test_advisor_routes_are_not_available(env: None) -> None:  # noqa: ARG001
    app = create_app()
    client = TestClient(app)

    assert client.post("/v1/advisor/advise", json={"raw_question": "hello"}).status_code == 404
    assert client.get("/v2/advisor/health").status_code == 404
