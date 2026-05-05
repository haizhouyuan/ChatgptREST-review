"""Unit tests for pydantic-settings configuration."""

from __future__ import annotations

import os

import pytest

from runtime_allocator.config import Settings


class TestConfig:
    def test_default_values(self, monkeypatch):
        # Clear any existing env vars that might interfere
        for key in list(os.environ.keys()):
            if key.startswith("PAPERCLIP_"):
                monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("PAPERCLIP_API_KEYS", "dev-key:admin")
        s = Settings()
        assert s.port == 8080
        assert s.host == "0.0.0.0"
        assert s.log_level == "INFO"
        assert s.rate_limit_rps == 10.0
        assert s.rate_limit_burst == 20

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("PAPERCLIP_PORT", "9090")
        monkeypatch.setenv("PAPERCLIP_RATE_LIMIT_RPS", "50")
        monkeypatch.setenv("PAPERCLIP_API_KEYS", "dev-key:admin")
        s = Settings()
        assert s.port == 9090
        assert s.rate_limit_rps == 50.0

    def test_webhook_settings(self, monkeypatch):
        monkeypatch.setenv("PAPERCLIP_API_KEYS", "dev-key:admin")
        s = Settings()
        assert s.webhook_url == ""
        assert s.webhook_secret == ""
