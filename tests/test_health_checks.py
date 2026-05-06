from __future__ import annotations

import importlib.util
from pathlib import Path
import urllib.error


def _load_module():
    path = Path(__file__).resolve().parents[1] / "ops" / "health_checks.py"
    spec = importlib.util.spec_from_file_location("test_health_checks_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _http_error(url: str, code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "error", hdrs=None, fp=None)


def test_check_http_treats_root_404_as_alive(monkeypatch) -> None:
    mod = _load_module()

    def _raise(*args, **kwargs):
        raise _http_error("http://127.0.0.1:18712/", 404)

    monkeypatch.setattr(mod.urllib.request, "urlopen", _raise)

    result = mod.check_http("public_mcp", "http://127.0.0.1:18712/")

    assert result["ok"] is True
    assert result["status"] == 404


def test_check_http_rejects_non_root_404_by_default(monkeypatch) -> None:
    mod = _load_module()

    def _raise(*args, **kwargs):
        raise _http_error("http://127.0.0.1:18713/v2/advisor/health", 404)

    monkeypatch.setattr(mod.urllib.request, "urlopen", _raise)

    result = mod.check_http("advisor_v3", "http://127.0.0.1:18713/v2/advisor/health")

    assert result["ok"] is False
    assert result["status"] == 404


def test_resolve_runtime_registry_uses_unified_advisor_host() -> None:
    mod = _load_module()

    registry = mod.resolve_runtime_registry()
    advisor = next(svc for svc in registry["services"] if svc["name"] == "advisor_v3")

    assert advisor["liveness_url"] == "http://127.0.0.1:18711/v2/advisor/health"
    assert advisor["agent_entry_url"] == "http://127.0.0.1:18711"
    assert advisor["port"] == 18711


def test_summarize_runtime_quick_marks_wrong_advisor_health_route_unhealthy(monkeypatch) -> None:
    mod = _load_module()

    monkeypatch.setattr(
        mod,
        "resolve_runtime_registry",
        lambda: {
            "services": [
                {
                    "name": "public_mcp",
                    "liveness_url": "http://127.0.0.1:18712/",
                    "agent_entry_url": "http://127.0.0.1:18712/mcp",
                    "port": 18712,
                    "required": True,
                },
                {
                    "name": "advisor_v3",
                    "liveness_url": "http://127.0.0.1:18713/v2/advisor/health",
                    "agent_entry_url": "http://127.0.0.1:18713",
                    "port": 18713,
                    "required": False,
                },
            ],
            "databases": [],
        },
    )

    def _fake_check_http(label: str, url: str, *, timeout: int = 5, alive_statuses=None):
        if label == "public_mcp":
            return {"check": label, "ok": True, "status": 404}
        return {"check": label, "ok": False, "status": 404}

    monkeypatch.setattr(mod, "check_http", _fake_check_http)

    snapshot = mod.summarize_runtime_quick()
    services = {svc["name"]: svc for svc in snapshot["services"]}

    assert services["public_mcp"]["ok"] is True
    assert services["advisor_v3"]["ok"] is False
    assert snapshot["public_mcp_ingress"]["ok"] is True
