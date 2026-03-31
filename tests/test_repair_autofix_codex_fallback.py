from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from chatgptrest.core.config import AppConfig
from chatgptrest.executors import repair as repair_mod


def _cfg(tmp_path: Path) -> AppConfig:
    return AppConfig(
        db_path=tmp_path / "jobdb.sqlite3",
        artifacts_dir=tmp_path / "artifacts",
        preview_chars=200,
        lease_ttl_seconds=60,
        max_attempts=3,
        chatgpt_mcp_url="http://127.0.0.1:18701/mcp",
        driver_mode="external_mcp",
        driver_url="http://127.0.0.1:18701/mcp",
        min_prompt_interval_seconds=61,
        gemini_min_prompt_interval_seconds=61,
        qwen_min_prompt_interval_seconds=0,
        chatgpt_max_prompts_per_hour=0,
        chatgpt_max_prompts_per_day=0,
        wait_slice_seconds=60,
        wait_slice_growth_factor=1.0,
        pro_fallback_presets=("thinking_heavy", "auto"),
        api_token=None,
        ops_token=None,
    )


def test_repair_autofix_uses_codex_secondary_fallback(monkeypatch, tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    calls: list[dict[str, object]] = []

    def fake_run_codex_with_schema(**kwargs):  # noqa: ANN003
        calls.append(dict(kwargs))
        if len(calls) == 1:
            return {"ok": False, "error": "primary codex timeout"}
        return {
            "ok": True,
            "output": {
                "summary": "fallback plan",
                "actions": [{"name": "capture_ui", "risk": "low", "reason": "collect evidence first"}],
            },
        }

    monkeypatch.setattr(repair_mod, "_run_codex_with_schema", fake_run_codex_with_schema)
    monkeypatch.setenv("CHATGPTREST_CODEX_AUTOFIX_ENABLE_MAINT_FALLBACK", "1")

    ex = repair_mod.RepairAutofixExecutor(cfg=cfg, tool_caller=None, tool_caller_init_error=None)
    result = asyncio.run(
        ex.run(
            job_id="repair-fallback-1",
            kind="repair.autofix",
            input={"symptom": "transport error: [Errno 111] Connection refused"},
            params={"timeout_seconds": 120, "apply_actions": True, "allow_actions": "capture_ui", "max_risk": "low"},
        )
    )
    assert result.status == "completed"
    assert len(calls) == 2
    assert all(call["model"] == "gpt-5.3-codex-spark" for call in calls)

    report_path = cfg.artifacts_dir / "jobs" / "repair-fallback-1" / "repair_autofix_report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["fallback"]["reason"] == "codex_maint_agent_fallback"
    assert payload["codex"]["ok"] is False
    assert payload["codex_fallback"]["ok"] is True


def test_repair_autofix_can_switch_gemini_proxy(monkeypatch, tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    state = {"now": "🇨🇳 中国 01"}

    def fake_run_codex_with_schema(**kwargs):  # noqa: ANN003
        return {
            "ok": True,
            "output": {
                "summary": "switch gemini proxy",
                "actions": [{"name": "switch_gemini_proxy", "risk": "medium", "reason": "region failover"}],
            },
        }

    def fake_get_proxy(group, timeout_seconds=5.0):  # noqa: ANN001, ARG001
        return {
            "ok": True,
            "group": group,
            "now": state["now"],
            "all": ["🇺🇲 美国 01", "🇯🇵 日本 03", "🇨🇳 中国 01"],
        }

    def fake_set_proxy(group, name, timeout_seconds=5.0):  # noqa: ANN001, ARG001
        state["now"] = str(name)
        return {"ok": True, "group": group, "name": name}

    monkeypatch.setattr(repair_mod, "_run_codex_with_schema", fake_run_codex_with_schema)
    monkeypatch.setattr(repair_mod, "_mihomo_get_proxy", fake_get_proxy)
    monkeypatch.setattr(repair_mod, "_mihomo_set_proxy", fake_set_proxy)
    monkeypatch.setattr(repair_mod, "_mihomo_find_connections", lambda **kwargs: {"ok": True, "matches": []})  # noqa: ARG005
    monkeypatch.setenv("CHATGPTREST_GEMINI_MIHOMO_PROXY_GROUP", "💻 Codex")
    monkeypatch.setenv("CHATGPTREST_GEMINI_MIHOMO_CANDIDATES", "🇺🇲 美国 01,🇯🇵 日本 03")

    ex = repair_mod.RepairAutofixExecutor(cfg=cfg, tool_caller=None, tool_caller_init_error=None)
    result = asyncio.run(
        ex.run(
            job_id="repair-gemini-proxy-1",
            kind="repair.autofix",
            input={
                "conversation_url": "https://gemini.google.com/app/abc123",
                "symptom": "Gemini is not available in this region.",
            },
            params={"timeout_seconds": 120, "apply_actions": True, "allow_actions": "switch_gemini_proxy", "max_risk": "medium"},
        )
    )
    assert result.status == "completed"
    report_path = cfg.artifacts_dir / "jobs" / "repair-gemini-proxy-1" / "repair_autofix_report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["applied_actions"][0]["name"] == "switch_gemini_proxy"
    assert payload["applied_actions"][0]["ok"] is True
    assert payload["applied_actions"][0]["details"]["confirmed"]["now"] == "🇺🇲 美国 01"


def test_repair_autofix_does_not_inject_stale_disable_features_by_default(monkeypatch, tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    captured: dict[str, object] = {}

    def fake_run_codex_with_schema(**kwargs):  # noqa: ANN003
        captured["disable_features"] = kwargs.get("disable_features")
        return {
            "ok": True,
            "output": {
                "summary": "capture first",
                "actions": [{"name": "capture_ui", "risk": "low", "reason": "collect evidence first"}],
            },
        }

    monkeypatch.delenv("CHATGPTREST_CODEX_AUTOFIX_DISABLE_FEATURES", raising=False)
    monkeypatch.setattr(repair_mod, "_run_codex_with_schema", fake_run_codex_with_schema)

    ex = repair_mod.RepairAutofixExecutor(cfg=cfg, tool_caller=None, tool_caller_init_error=None)
    result = asyncio.run(
        ex.run(
            job_id="repair-no-disable-feature",
            kind="repair.autofix",
            input={"symptom": "CDP connect failed"},
            params={"timeout_seconds": 120, "apply_actions": False, "allow_actions": "capture_ui", "max_risk": "low"},
        )
    )

    assert result.status == "completed"
    assert captured["disable_features"] == []


def test_repair_autofix_allows_env_default_model_override(monkeypatch, tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    captured: dict[str, object] = {}

    def fake_run_codex_with_schema(**kwargs):  # noqa: ANN003
        captured["model"] = kwargs.get("model")
        return {
            "ok": True,
            "output": {
                "summary": "capture first",
                "actions": [{"name": "capture_ui", "risk": "low", "reason": "collect evidence first"}],
            },
        }

    monkeypatch.setenv("CHATGPTREST_CODEX_AUTOFIX_MODEL_DEFAULT", "openai-codex/gpt-5.3-codex-spark")
    monkeypatch.setattr(repair_mod, "_run_codex_with_schema", fake_run_codex_with_schema)

    ex = repair_mod.RepairAutofixExecutor(cfg=cfg, tool_caller=None, tool_caller_init_error=None)
    result = asyncio.run(
        ex.run(
            job_id="repair-env-model-override",
            kind="repair.autofix",
            input={"symptom": "CDP connect failed"},
            params={"timeout_seconds": 120, "apply_actions": False, "allow_actions": "capture_ui", "max_risk": "low"},
        )
    )

    assert result.status == "completed"
    assert captured["model"] == "openai-codex/gpt-5.3-codex-spark"


def test_repair_autofix_injects_maintagent_memory_into_prompt(monkeypatch, tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    packet_path = tmp_path / "maintagent_memory_packet.json"
    packet_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-15T00:00:00Z",
                "machine": {"summary": {"memory_total_gb": 32}},
                "workspace": {"summary": {"repo_or_worktree_count": 73}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CHATGPTREST_MAINT_BOOTSTRAP_MEMORY_PACKET", str(packet_path))
    captured: dict[str, object] = {}

    def fake_run_codex_with_schema(**kwargs):  # noqa: ANN003
        captured["prompt"] = kwargs.get("prompt")
        return {
            "ok": True,
            "output": {
                "summary": "capture first",
                "actions": [{"name": "capture_ui", "risk": "low", "reason": "collect evidence first"}],
            },
        }

    monkeypatch.setattr(repair_mod, "_run_codex_with_schema", fake_run_codex_with_schema)

    ex = repair_mod.RepairAutofixExecutor(cfg=cfg, tool_caller=None, tool_caller_init_error=None)
    result = asyncio.run(
        ex.run(
            job_id="repair-memory-prompt",
            kind="repair.autofix",
            input={"symptom": "CDP connect failed"},
            params={"timeout_seconds": 120, "apply_actions": False, "allow_actions": "capture_ui", "max_risk": "low"},
        )
    )

    assert result.status == "completed"
    prompt = str(captured["prompt"] or "")
    assert "Maintagent Repo Memory" in prompt
    assert "Maintagent Bootstrap Memory" in prompt
    assert str(packet_path) in prompt


def test_call_tool_with_hard_timeout_stops_waiting() -> None:
    class BlockingCaller:
        def call_tool(self, *, tool_name, tool_args, timeout_sec=600.0):  # noqa: ANN001, ARG002
            time.sleep(0.2)
            return {"ok": True}

    started = time.time()
    with pytest.raises(TimeoutError):
        asyncio.run(
            repair_mod._call_tool_with_hard_timeout(
                tool_caller=BlockingCaller(),
                tool_name="capture_ui",
                tool_args={},
                timeout_sec=0.05,
                hard_timeout_sec=0.05,
            )
        )
    assert time.time() - started < 0.5
