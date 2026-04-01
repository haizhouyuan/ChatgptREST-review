from __future__ import annotations

from pathlib import Path

from chatgptrest.executors import repair as repair_mod


def test_qwen_provider_detection_from_kind_and_url() -> None:
    assert repair_mod._provider_from_kind("qwen_web.ask") == "qwen"
    assert repair_mod._conversation_platform("https://www.qianwen.com/chat/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa") == "qwen"


def test_qwen_provider_tools_support_selfcheck_and_capture() -> None:
    tools = repair_mod._provider_tools("qwen")
    assert tools.get("self_check") is None
    assert tools.get("capture_ui") is None
    assert tools.get("clear_blocked") is None
    assert tools.get("refresh") is None


def test_gemini_provider_tools_support_selfcheck_and_capture() -> None:
    tools = repair_mod._provider_tools("gemini")
    assert tools.get("self_check") == "gemini_web_self_check"
    assert tools.get("capture_ui") == "gemini_web_capture_ui"
    assert tools.get("blocked_status") is None
    assert tools.get("rate_limit_status") is None
    assert tools.get("clear_blocked") is None
    assert tools.get("refresh") is None


def test_qwen_provider_defaults(monkeypatch) -> None:
    monkeypatch.delenv("QWEN_CDP_URL", raising=False)
    cdp_url = repair_mod._provider_cdp_url("qwen")
    assert cdp_url == "http://127.0.0.1:9335"

    script = repair_mod._provider_chrome_start_script("qwen")
    assert isinstance(script, Path)
    assert script.as_posix().endswith("/ops/qwen_chrome_start.sh")


def test_chatgpt_provider_cdp_url_respects_chrome_debug_port(monkeypatch) -> None:
    monkeypatch.delenv("CHATGPT_CDP_URL", raising=False)
    monkeypatch.delenv("GEMINI_CDP_URL", raising=False)
    monkeypatch.setenv("CHROME_DEBUG_PORT", "9226")

    assert repair_mod._provider_cdp_url("chatgpt") == "http://127.0.0.1:9226"
    assert repair_mod._provider_cdp_url("gemini") == "http://127.0.0.1:9226"


def test_build_codex_autofix_prompt_includes_playbook() -> None:
    prompt = repair_mod._build_codex_autofix_prompt(
        agents_md="agents policy",
        playbook_md="playbook policy",
        repo_memory_text="",
        bootstrap_memory_text="",
        evidence={"job_id": "j1"},
    )
    assert "Repair Agent Playbook" in prompt
    assert "playbook policy" in prompt
    assert "agents policy" in prompt


def test_build_codex_autofix_fallback_prompt_includes_prior_error() -> None:
    prompt = repair_mod._build_codex_autofix_fallback_prompt(  # noqa: SLF001
        evidence={"target_job": {"job_id": "j1"}, "allowed_actions": ["capture_ui"]},
        prior_error="primary codex timeout",
    )
    assert "maint fallback agent" in prompt
    assert "primary codex timeout" in prompt


def test_extract_actions_payload_requires_actions_list() -> None:
    assert repair_mod._extract_actions_payload({"output": {"actions": []}}) == {"actions": []}  # noqa: SLF001
    assert repair_mod._extract_actions_payload({"output": {"summary": "only"}}) is None  # noqa: SLF001
