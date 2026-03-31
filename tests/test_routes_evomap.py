"""Tests for EvoMap Dashboard API."""

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.routes_evomap import make_evomap_router
from chatgptrest.evomap.observer import EvoMapObserver
from chatgptrest.evomap.signals import Signal, SignalType


@pytest.fixture
def client(monkeypatch):
    """Create test client with in-memory observer."""
    monkeypatch.setenv("OPENMIND_EVOMAP_DB", ":memory:")

    router = make_evomap_router()
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_get_signals_empty(client):
    """Test get_signals returns empty list initially."""
    response = client.get("/v2/evomap/signals")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["count"] == 0
    assert data["signals"] == []


def test_get_signals_with_filters(client):
    """Test get_signals supports query filters."""
    response = client.get("/v2/evomap/signals?signal_type=route_selected&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "signals" in data


def test_get_trends(client):
    """Test get_trends returns daily aggregated data."""
    response = client.get("/v2/evomap/trends?days=7")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "trends" in data


def test_get_config(client):
    """Test get_config returns current config."""
    response = client.get("/v2/evomap/config")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "config" in data
    assert "signal_retention_days" in data["config"]


def test_update_config(client):
    """Test update_config modifies config."""
    response = client.post(
        "/v2/evomap/config",
        json={"signal_retention_days": 60},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["config"]["signal_retention_days"] == 60


def test_get_trends_invalid_days(client):
    """Test get_trends rejects invalid days parameter."""
    response = client.get("/v2/evomap/trends?days=0")
    assert response.status_code == 422  # Validation error


def test_reuses_app_state_observer(monkeypatch):
    """Dashboard should reuse the shared observer when app.state provides one."""
    monkeypatch.delenv("OPENMIND_EVOMAP_DB", raising=False)
    obs = EvoMapObserver(db_path=":memory:")
    obs.record(
        Signal(
            trace_id="tr_shared",
            signal_type=SignalType.ROUTE_SELECTED,
            source="advisor",
            domain="routing",
            data={"route": "funnel"},
        )
    )

    from fastapi import FastAPI

    app = FastAPI()
    app.state.evomap_observer = obs
    app.include_router(make_evomap_router())
    client = TestClient(app)

    response = client.get("/v2/evomap/signals")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["signals"][0]["trace_id"] == "tr_shared"

    obs.close()
