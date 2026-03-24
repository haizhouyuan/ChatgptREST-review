from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
import pytest

from chatgptrest.api.client_ip import _trusted_cidrs
from chatgptrest.advisor.runtime import get_advisor_runtime_if_ready, reset_advisor_runtime
from chatgptrest.evomap.paths import resolve_evomap_db_path
from chatgptrest.api.routes_advisor_v3 import (
    _openmind_event_bus_db_path,
    _openmind_kb_search_db_path,
    make_v3_advisor_router,
)


@pytest.fixture(autouse=True)
def _clear_trusted_proxy_cache():
    _trusted_cidrs.cache_clear()
    yield
    _trusted_cidrs.cache_clear()


def _make_client(**kwargs) -> TestClient:
    reset_advisor_runtime()
    app = FastAPI()
    app.include_router(make_v3_advisor_router())
    return TestClient(app, raise_server_exceptions=False, **kwargs)


def test_dashboard_fails_closed_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENMIND_API_KEY", raising=False)
    monkeypatch.delenv("OPENMIND_AUTH_MODE", raising=False)

    client = _make_client()

    r = client.get("/v2/advisor/dashboard")
    assert r.status_code == 503


def test_dashboard_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    client = _make_client()

    r = client.get("/v2/advisor/dashboard")
    assert r.status_code == 401

    r2 = client.get("/v2/advisor/dashboard", headers={"X-Api-Key": "secret-key"})
    assert r2.status_code != 401


def test_rate_limit_applies_to_non_health_routes(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setenv("OPENMIND_RATE_LIMIT", "1")

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}

    first = client.get("/v2/advisor/evomap/stats", headers=headers)
    assert first.status_code != 429

    second = client.get("/v2/advisor/evomap/stats", headers=headers)
    assert second.status_code == 429
    assert second.json()["detail"]["error"] == "Rate limit exceeded"


def test_health_is_exempt_from_auth_and_rate_limit(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setenv("OPENMIND_RATE_LIMIT", "1")

    client = _make_client()

    first = client.get("/v2/advisor/health")
    second = client.get("/v2/advisor/health")

    assert first.status_code != 401
    assert first.status_code != 429
    assert second.status_code != 401
    assert second.status_code != 429
    assert first.json()["status"] == "not_initialized"
    assert second.json()["status"] == "not_initialized"
    assert get_advisor_runtime_if_ready() is None


def test_health_reports_mock_llm_as_degraded(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    class _FakeLlm:
        _mock_fn = staticmethod(lambda prompt, system_msg="": "mock")

    fake_state = {
        "kb_hub": None,
        "llm": _FakeLlm(),
        "memory": None,
        "event_bus": object(),
        "routing_fabric": object(),
        "circuit_breaker": object(),
    }
    monkeypatch.setattr(
        "chatgptrest.api.routes_advisor_v3.get_advisor_runtime_if_ready",
        lambda: fake_state,
    )

    client = _make_client()
    response = client.get("/v2/advisor/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["subsystems"]["llm"]["status"] == "mock"
    assert body["subsystems"]["routing"]["status"] == "ok"
    assert any(item["component"] == "llm" for item in body["degradation"])


def test_open_mode_still_allows_unauthenticated_access(monkeypatch) -> None:
    monkeypatch.delenv("OPENMIND_API_KEY", raising=False)
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "open")

    client = _make_client()

    r = client.get("/v2/advisor/evomap/stats")
    assert r.status_code != 401
    assert r.status_code != 503


def test_cc_routes_default_to_loopback_only(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.delenv("OPENMIND_CONTROL_API_KEY", raising=False)

    client = _make_client()

    r = client.get("/v2/advisor/cc-health", headers={"X-Api-Key": "secret-key"})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "cc_control_requires_loopback"


def test_cc_routes_accept_dedicated_control_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setenv("OPENMIND_CONTROL_API_KEY", "control-key")

    client = _make_client()

    denied = client.get("/v2/advisor/cc-health", headers={"X-Api-Key": "secret-key"})
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "cc_control_requires_control_key"

    allowed = client.get(
        "/v2/advisor/cc-health",
        headers={"X-Api-Key": "secret-key", "X-Control-Api-Key": "control-key"},
    )
    assert allowed.status_code != 403


def test_cc_routes_allow_real_loopback_when_no_proxy_headers(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.delenv("OPENMIND_CONTROL_API_KEY", raising=False)
    monkeypatch.delenv("CHATGPTREST_TRUSTED_PROXY_CIDRS", raising=False)
    _trusted_cidrs.cache_clear()

    client = _make_client(client=("127.0.0.1", 12001))

    response = client.get("/v2/advisor/cc-health", headers={"X-Api-Key": "secret-key"})

    assert response.status_code != 403


def test_cc_routes_reject_forwarded_non_loopback_client_behind_trusted_proxy(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.delenv("OPENMIND_CONTROL_API_KEY", raising=False)
    monkeypatch.setenv("CHATGPTREST_TRUSTED_PROXY_CIDRS", "127.0.0.1/32")
    _trusted_cidrs.cache_clear()

    client = _make_client(client=("127.0.0.1", 12002))

    response = client.get(
        "/v2/advisor/cc-health",
        headers={
            "X-Api-Key": "secret-key",
            "X-Forwarded-For": "198.51.100.7, 127.0.0.1",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "cc_control_requires_loopback"
    assert response.json()["detail"]["client_ip"] == "198.51.100.7"


def test_cc_control_dependency_only_applies_to_cc_routes(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    app = FastAPI()
    app.include_router(make_v3_advisor_router())

    cc_health = next(route for route in app.routes if isinstance(route, APIRoute) and route.path == "/v2/advisor/cc-health")
    dashboard = next(route for route in app.routes if isinstance(route, APIRoute) and route.path == "/v2/advisor/dashboard")

    cc_dep_names = [getattr(dep.call, "__name__", "") for dep in cc_health.dependant.dependencies]
    dashboard_dep_names = [getattr(dep.call, "__name__", "") for dep in dashboard.dependant.dependencies]

    assert "_require_cc_control_access" in cc_dep_names
    assert "_require_cc_control_access" not in dashboard_dep_names


def test_openmind_path_helpers_prefer_canonical_envs(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_KB_PATH", "/tmp/legacy-kb.db")
    monkeypatch.setenv("OPENMIND_KB_SEARCH_DB", "/tmp/canonical-kb.db")
    monkeypatch.setenv("OPENMIND_EVENTS_DB", "/tmp/legacy-events.db")
    monkeypatch.setenv("OPENMIND_EVENTBUS_DB", "/tmp/canonical-events.db")
    monkeypatch.setenv("OPENMIND_EVO_DB", "/tmp/legacy-evomap.db")
    monkeypatch.setenv("OPENMIND_EVOMAP_DB", "/tmp/canonical-evomap.db")

    assert _openmind_kb_search_db_path() == "/tmp/canonical-kb.db"
    assert _openmind_event_bus_db_path() == "/tmp/canonical-events.db"
    assert resolve_evomap_db_path() == "/tmp/canonical-evomap.db"


def test_advisor_ask_blocks_synthetic_or_trivial_prompt(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    client = _make_client()

    response = client.post(
        "/v2/advisor/ask",
        headers={"X-Api-Key": "secret-key"},
        json={"question": "hello"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "agent_trivial_prompt_blocked"


def test_advisor_ask_enforces_client_name_allowlist(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")

    client = _make_client()

    response = client.post(
        "/v2/advisor/ask",
        headers={"X-Api-Key": "secret-key"},
        json={"question": "请分析这个问题背后的约束"},
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["error"] == "client_not_allowed"
    assert detail["allowed_client_names"] == ["chatgptrest-mcp"]


def test_advisor_ask_enforces_trace_headers(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")

    client = _make_client()

    response = client.post(
        "/v2/advisor/ask",
        headers={
            "X-Api-Key": "secret-key",
            "X-Client-Name": "chatgptrest-mcp",
        },
        json={"question": "请分析这个问题背后的约束"},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "missing_trace_headers"
    assert detail["operation"] == "advisor_ask"
