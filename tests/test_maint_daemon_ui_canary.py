from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_maint_daemon_module():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "ops" / "maint_daemon.py"
    spec = importlib.util.spec_from_file_location("chatgptrest_ops_maint_daemon_ui_canary", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_ui_canary_providers_defaults_and_filtering() -> None:
    md = _load_maint_daemon_module()
    assert md._parse_ui_canary_providers("") == ["chatgpt", "gemini"]  # noqa: SLF001
    assert md._parse_ui_canary_providers("gemini,chatgpt,invalid,gemini") == ["gemini", "chatgpt"]  # noqa: SLF001
    md.os.environ["CHATGPTREST_QWEN_ENABLED"] = "1"  # noqa: SLF001
    assert md._parse_ui_canary_providers("") == ["chatgpt", "gemini", "qwen"]  # noqa: SLF001
    md.os.environ.pop("CHATGPTREST_QWEN_ENABLED", None)  # noqa: SLF001


def test_ui_canary_probe_summary_success_and_failure() -> None:
    md = _load_maint_daemon_module()

    ok_wrapped = {
        "ok": True,
        "result": {
            "ok": True,
            "status": "completed",
            "mode_text": "Pro",
            "conversation_url": "https://gemini.google.com/app/abc",
            "run_id": "run_ok",
        },
    }
    ok_summary = md._ui_canary_probe_summary(provider="gemini", wrapped=ok_wrapped)  # noqa: SLF001
    assert ok_summary["success"] is True
    assert ok_summary["status"] == "completed"
    assert ok_summary["mode_text"] == "Pro"

    fail_wrapped = {
        "ok": False,
        "error_type": "ToolCallError",
        "error": "boom",
    }
    fail_summary = md._ui_canary_probe_summary(provider="chatgpt", wrapped=fail_wrapped)  # noqa: SLF001
    assert fail_summary["success"] is False
    assert fail_summary["error_type"] == "ToolCallError"
    assert fail_summary["error"] == "boom"


def test_ui_canary_state_load_and_dump_roundtrip() -> None:
    md = _load_maint_daemon_module()
    state = {
        "ui_canary": {
            "gemini": {
                "last_run_ts": 1.0,
                "last_ok_ts": 0.0,
                "last_failure_ts": 1.0,
                "consecutive_failures": 2,
                "last_status": "error",
                "last_error_type": "GeminiModeSelectorNotFound",
                "last_error": "selector missing",
            }
        }
    }
    loaded = md._load_ui_canary_state(state)  # noqa: SLF001
    assert loaded["gemini"]["consecutive_failures"] == 2
    dumped = md._dump_ui_canary_state(loaded)  # noqa: SLF001
    assert dumped["gemini"]["last_error_type"] == "GeminiModeSelectorNotFound"
