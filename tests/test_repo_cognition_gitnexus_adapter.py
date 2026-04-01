from __future__ import annotations

import json
import subprocess

from chatgptrest.repo_cognition import gitnexus_adapter as adapter


def _completed(stdout: str, *, rc: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["gitnexus"], returncode=rc, stdout=stdout, stderr=stderr)


def test_query_gitnexus_normalizes_cli_payload(monkeypatch) -> None:
    payload = {
        "processes": [{"heuristicLabel": "PublicMcpIngress", "summary": "MCP ingress flow", "relevance": 0.91}],
        "process_symbols": [{"id": "Function:a.py:f:1", "name": "f", "filePath": "a.py", "startLine": 1, "endLine": 5}],
        "definitions": [{"id": "File:b.py", "name": "b.py", "filePath": "b.py"}],
    }

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        assert cmd[:3] == ["gitnexus", "query", "-r"]
        assert "ChatgptREST" in cmd
        assert "-g" in cmd
        return _completed(json.dumps(payload))

    monkeypatch.setattr(adapter, "_canonical_repo_name", lambda: "ChatgptREST")
    monkeypatch.setattr(adapter.subprocess, "run", fake_run)

    result = adapter.query_gitnexus("public MCP ingress drift", goal_hint="public_agent")

    assert result["status"] == "resolved"
    assert result["manual_command"] is None
    assert result["processes"][0]["name"] == "PublicMcpIngress"
    assert result["symbols"][0]["file_path"] == "a.py"
    assert result["symbols"][1]["file_path"] == "b.py"


def test_query_gitnexus_timeout_returns_manual_query(monkeypatch) -> None:
    def fake_run(cmd, **kwargs):  # noqa: ANN001
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=15)

    monkeypatch.setattr(adapter, "_canonical_repo_name", lambda: "ChatgptREST")
    monkeypatch.setattr(adapter.subprocess, "run", fake_run)

    result = adapter.query_gitnexus("public MCP ingress drift", goal_hint="public_agent")

    assert result["status"] == "error"
    assert "timed out" in str(result["error"])
    assert result["manual_command"] == "gitnexus query -r ChatgptREST -g public_agent 'public MCP ingress drift' -l 5"


def test_check_gitnexus_status_reports_stale(monkeypatch) -> None:
    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda *args, **kwargs: _completed("Repository: /tmp/repo\nStatus: ⚠️ stale (re-run gitnexus analyze)\n"),
    )

    assert adapter.check_gitnexus_status() == "stale"
