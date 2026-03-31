from __future__ import annotations

from pathlib import Path

import chatgptrest.eval.admin_mcp_provider_compatibility_gate as mod


def test_parse_streamable_http_json_accepts_sse_payload() -> None:
    payload = 'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n\n'
    parsed = mod._parse_streamable_http_json(payload)

    assert parsed["result"]["ok"] is True


def test_run_admin_mcp_provider_compatibility_gate_passes_with_monkeypatched_transport(monkeypatch) -> None:
    class _DummyContext:
        def __enter__(self):
            return "http://127.0.0.1:19999/mcp"

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(mod, "_launch_admin_mcp_server", lambda **kwargs: _DummyContext())

    def fake_jsonrpc_call(url, *, request_id, method, params, timeout_seconds=30.0):  # noqa: ARG001
        if method == "initialize":
            return {"result": {"protocolVersion": "2025-03-26", "serverInfo": {"name": "chatgptrest"}}}
        if method == "tools/list":
            return {"result": {"tools": [{"name": "chatgptrest_gemini_ask_submit"}, {"name": "chatgptrest_job_wait"}, {"name": "chatgptrest_answer_get"}]}}
        if params["name"] == "chatgptrest_gemini_ask_submit":
            return {"result": {"content": [{"text": '{"job_id":"job-1","kind":"gemini_web.ask","status":"queued"}'}]}}
        if params["name"] == "chatgptrest_job_wait":
            return {"result": {"content": [{"text": '{"status":"completed","kind":"gemini_web.ask"}'}]}}
        if params["name"] == "chatgptrest_answer_get":
            return {"result": {"content": [{"text": '{"chunk":"done","done":true}'}]}}
        raise AssertionError(params)

    monkeypatch.setattr(mod, "_jsonrpc_call", fake_jsonrpc_call)

    report = mod.run_admin_mcp_provider_compatibility_gate(base_url="http://127.0.0.1:18711")

    assert report.num_checks == 5
    assert report.num_failed == 0


def test_admin_mcp_provider_compatibility_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = mod.AdminMcpProviderCompatibilityGateReport(
        base_url="http://127.0.0.1:18711",
        mcp_url="http://127.0.0.1:19999/mcp",
        num_checks=1,
        num_passed=1,
        num_failed=0,
        checks=[mod.AdminMcpProviderCompatibilityCheck(name="initialize", passed=True, details={"server_name": "chatgptrest"})],
        scope_boundary=["dynamic admin mcp replay"],
    )

    json_path, md_path = mod.write_admin_mcp_provider_compatibility_gate_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    assert "Admin MCP Provider Compatibility Gate Report" in md_path.read_text(encoding="utf-8")
