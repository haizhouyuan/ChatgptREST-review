from __future__ import annotations

import io
import json
import urllib.error

import pytest


def _load_mcp_server_module():
    import importlib
    import chatgptrest.mcp.server as mod

    return importlib.reload(mod)


def test_mcp_http_json_transport_failure_logs_and_dedupes_autoreport(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    mod = _load_mcp_server_module()
    log_path = tmp_path / "mcp_http_failures.jsonl"
    monkeypatch.setenv("CHATGPTREST_MCP_FAILURE_LOG_PATH", str(log_path))
    monkeypatch.setenv("CHATGPTREST_MCP_FAILURE_LOG_ENABLED", "1")
    monkeypatch.setenv("CHATGPTREST_MCP_FAILURE_AUTOREPORT_ENABLED", "1")
    monkeypatch.setenv("CHATGPTREST_MCP_FAILURE_AUTOREPORT_DEDUPE_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_MCP_AUTO_START_API", "0")
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

    report_calls: list[dict] = []

    def fake_auto_report(**kwargs):  # noqa: ANN003
        report_calls.append(dict(kwargs))
        return {"attempted": True, "ok": True, "issue_id": "iss_auto_1", "created": True, "status": "open"}

    def fake_urlopen(_req, timeout=0):  # noqa: ANN001,ARG001
        raise urllib.error.URLError("[Errno 111] Connection refused")

    monkeypatch.setattr(mod, "_mcp_auto_report_issue_from_failure", fake_auto_report)
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)

    for _ in range(2):
        with pytest.raises(RuntimeError, match="HTTP request failed"):
            mod._http_json(method="GET", url="http://example.invalid/v1/jobs/j1", headers={"X-Client-Name": "codex"})

    assert len(report_calls) == 1
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["failure_kind"] == "mcp_transport"
    assert first["issue_report"]["attempted"] is True
    assert first["issue_report"]["ok"] is True
    assert second["issue_report"]["deduped"] is True


def test_mcp_http_json_http_404_logs_without_autoreport(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    mod = _load_mcp_server_module()
    log_path = tmp_path / "mcp_http_failures_404.jsonl"
    monkeypatch.setenv("CHATGPTREST_MCP_FAILURE_LOG_PATH", str(log_path))
    monkeypatch.setenv("CHATGPTREST_MCP_FAILURE_LOG_ENABLED", "1")
    monkeypatch.setenv("CHATGPTREST_MCP_FAILURE_AUTOREPORT_ENABLED", "1")

    report_calls: list[dict] = []

    def fake_auto_report(**kwargs):  # noqa: ANN003
        report_calls.append(dict(kwargs))
        return {"attempted": True, "ok": True}

    def fake_urlopen(_req, timeout=0):  # noqa: ANN001,ARG001
        raise urllib.error.HTTPError(
            url="http://example.invalid/v1/jobs/missing",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(b'{"detail":"not found"}'),
        )

    monkeypatch.setattr(mod, "_mcp_auto_report_issue_from_failure", fake_auto_report)
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="HTTP 404"):
        mod._http_json(method="GET", url="http://example.invalid/v1/jobs/missing", headers={"X-Client-Name": "codex"})

    assert report_calls == []
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["status_code"] == 404
    assert payload["failure_kind"] is None


def test_mcp_http_json_can_disable_failure_hooks(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_mcp_server_module()
    monkeypatch.setenv("CHATGPTREST_MCP_AUTO_START_API", "0")
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

    def fake_urlopen(_req, timeout=0):  # noqa: ANN001,ARG001
        raise urllib.error.URLError("connection reset")

    def fail_hook(**kwargs):  # noqa: ANN003
        raise AssertionError("failure hook should not run")

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(mod, "_mcp_handle_http_failure", fail_hook)

    with pytest.raises(RuntimeError, match="HTTP request failed"):
        mod._http_json(
            method="GET",
            url="http://example.invalid/v1/jobs/j1",
            headers={"X-Client-Name": "codex"},
            enable_failure_hooks=False,
        )
