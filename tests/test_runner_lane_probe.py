from __future__ import annotations

from pathlib import Path

from ops.runner_lane_probe import ProbeResult, _parse_jsonish, build_summary


def test_parse_jsonish_handles_fenced_json_with_preamble() -> None:
    raw = 'MCP issues detected. Run /mcp list for status.```json\n{"ok":true,"mode":"runner_probe"}\n```'
    parsed = _parse_jsonish(raw)
    assert parsed == {"ok": True, "mode": "runner_probe"}


def test_build_summary_surfaces_runner_verdicts(tmp_path: Path) -> None:
    results = [
        ProbeResult(
            lane="codex_ambient",
            ok=True,
            returncode=0,
            elapsed_ms=1000,
            command=["codex"],
            summary="ok",
            parsed_output={"ok": True},
            tokens_used=20752,
        ),
        ProbeResult(
            lane="codex_isolated",
            ok=False,
            returncode=1,
            elapsed_ms=1000,
            command=["codex"],
            summary="failed",
            stderr_excerpt="401 Unauthorized",
        ),
        ProbeResult(
            lane="codex_auth_only",
            ok=True,
            returncode=0,
            elapsed_ms=1000,
            command=["codex"],
            summary="ok",
            parsed_output={"ok": True},
            tokens_used=905,
        ),
        ProbeResult(
            lane="gemini_ambient",
            ok=True,
            returncode=0,
            elapsed_ms=1000,
            command=["gemini"],
            summary="ok",
            parsed_output={"ok": True},
            stderr_excerpt="glm_router",
        ),
        ProbeResult(
            lane="gemini_no_mcp",
            ok=True,
            returncode=0,
            elapsed_ms=1000,
            command=["gemini"],
            summary="ok",
            parsed_output={"ok": True},
        ),
        ProbeResult(
            lane="claudeminmax",
            ok=True,
            returncode=0,
            elapsed_ms=1000,
            command=["claudeminmax"],
            summary="ok",
            parsed_output={"ok": True},
        ),
        ProbeResult(
            lane="hcom_start",
            ok=False,
            returncode=1,
            elapsed_ms=1000,
            command=["hcom"],
            summary="failed",
            parsed_output={"message": "hcom hooks installed; restart the tool, then re-run hcom start"},
        ),
    ]
    summary = build_summary(results, 'Return exactly this JSON: {"ok":true}', tmp_path)
    verdicts = summary["verdicts"]
    assert "codex ambient lane works but is too heavy for microtasks" in verdicts
    assert "codex clean lane needs isolated auth bootstrap, not empty CODEX_HOME" in verdicts
    assert "codex auth-only lane is the right batch baseline: auth kept, MCP/config stripped" in verdicts
    assert "gemini ambient lane works but needs a clean MCP allowlist/profile" in verdicts
    assert "gemini no-MCP lane is the right cheap secondary-review baseline" in verdicts
    assert "claudeminmax is the best current detached batch lane" in verdicts
    assert "hcom start is not idempotent on this machine because Codex notify hook is already occupied" in verdicts
