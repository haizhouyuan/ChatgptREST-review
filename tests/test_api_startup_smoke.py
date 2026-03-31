from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import chatgptrest.api.routes_advisor_v3 as routes_advisor_v3
from chatgptrest.api.app import create_app


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")


def test_routes_advisor_module_imports(env: None) -> None:  # noqa: ARG001
    mod = importlib.import_module("chatgptrest.api.routes_advisor")
    assert hasattr(mod, "make_advisor_router")


def test_create_app_includes_advisor_route(env: None) -> None:  # noqa: ARG001
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/advise",
        json={
            "raw_question": "启动冒烟",
            "context": {"project": "chatgptrest"},
            "execute": False,
            "force": True,
        },
    )
    assert r.status_code == 200


def test_create_app_records_startup_manifest_and_route_inventory(env: None) -> None:  # noqa: ARG001
    app = create_app()

    manifest = app.state.startup_manifest

    assert manifest["status"] == "ready"
    assert manifest["route_count"] >= 1
    assert any(item["name"] == "advisor_v3" and item["loaded"] is True for item in manifest["routers"])
    assert any(route["path"] == "/healthz" for route in manifest["route_inventory"])
    assert any(route["path"] == "/v2/advisor/advise" for route in manifest["route_inventory"])


def test_create_app_marks_router_failure_in_startup_manifest(
    env: None, monkeypatch: pytest.MonkeyPatch
) -> None:  # noqa: ARG001
    original = routes_advisor_v3.make_v3_advisor_router

    def _boom():
        raise RuntimeError("v3 import failed")

    monkeypatch.setattr(routes_advisor_v3, "make_v3_advisor_router", _boom)
    try:
        app = create_app()
    finally:
        monkeypatch.setattr(routes_advisor_v3, "make_v3_advisor_router", original)

    manifest = app.state.startup_manifest

    assert manifest["status"] == "router_load_failed"
    error = next(item for item in manifest["router_load_errors"] if item["name"] == "advisor_v3")
    assert error["error_type"] == "RuntimeError"
    assert "v3 import failed" in error["error"]
