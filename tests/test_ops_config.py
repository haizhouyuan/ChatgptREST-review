"""Tests for /v1/ops/config endpoint."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from chatgptrest.api.app import create_app

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None  # type: ignore[misc, assignment]


@pytest.fixture(autouse=True)
def _test_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.delenv("CHATGPTREST_API_TOKEN", raising=False)
    monkeypatch.delenv("CHATGPTREST_OPS_TOKEN", raising=False)


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
class TestOpsConfigEndpoint:
    def test_config_returns_200(self) -> None:
        app = create_app()
        client = TestClient(app)
        r = client.get("/v1/ops/config")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert isinstance(data["config"], dict)
        assert len(data["config"]) > 0

    def test_config_redacts_sensitive_vars(self) -> None:
        app = create_app()
        client = TestClient(app)
        r = client.get("/v1/ops/config")
        config = r.json()["config"]
        # TOKEN vars must always be marked sensitive
        for name in ("CHATGPTREST_API_TOKEN", "CHATGPTREST_OPS_TOKEN"):
            if name in config:
                assert config[name]["sensitive"] is True

    def test_config_exposes_non_sensitive_vars(self) -> None:
        app = create_app()
        client = TestClient(app)
        r = client.get("/v1/ops/config")
        config = r.json()["config"]
        # DB_PATH is not sensitive
        if "CHATGPTREST_DB_PATH" in config:
            assert config["CHATGPTREST_DB_PATH"]["sensitive"] is False

    def test_config_shows_overridden_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS", "120")
        app = create_app()
        client = TestClient(app)
        r = client.get("/v1/ops/config")
        config = r.json()["config"]
        entry = config.get("CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS", {})
        assert entry.get("effective") == 120
        assert entry.get("current") == "120"

    def test_config_auth_required_when_token_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CHATGPTREST_OPS_TOKEN", "secret-ops-token")
        app = create_app()
        client = TestClient(app)
        # No token → 401
        r = client.get("/v1/ops/config")
        assert r.status_code == 401
        # Correct token → 200
        r = client.get("/v1/ops/config", headers={"Authorization": "Bearer secret-ops-token"})
        assert r.status_code == 200
        # Verify the token itself is redacted in output
        config = r.json()["config"]
        assert config["CHATGPTREST_OPS_TOKEN"]["current"] == "***"
