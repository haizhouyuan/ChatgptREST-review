from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


def _load_maint_daemon_module():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "ops" / "maint_daemon.py"
    spec = importlib.util.spec_from_file_location("chatgptrest_ops_maint_daemon_provider_tools", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_provider_tools_include_gemini_self_check_and_capture() -> None:
    md = _load_maint_daemon_module()
    tools = md._provider_tools("gemini")  # noqa: SLF001
    assert tools.get("self_check") == "gemini_web_self_check"
    assert tools.get("capture_ui") == "gemini_web_capture_ui"
    assert tools.get("blocked_status") is None
    assert tools.get("rate_limit_status") is None


def test_provider_tools_keep_chatgpt_and_qwen_defaults() -> None:
    md = _load_maint_daemon_module()

    chatgpt_tools = md._provider_tools("chatgpt")  # noqa: SLF001
    assert chatgpt_tools.get("self_check") == "chatgpt_web_self_check"
    assert chatgpt_tools.get("capture_ui") == "chatgpt_web_capture_ui"

    qwen_tools = md._provider_tools("qwen")  # noqa: SLF001
    assert qwen_tools.get("self_check") == "qwen_web_self_check"
    assert qwen_tools.get("capture_ui") == "qwen_web_capture_ui"


def test_provider_cdp_url_respects_chrome_debug_port(monkeypatch) -> None:
    md = _load_maint_daemon_module()
    monkeypatch.delenv("CHATGPT_CDP_URL", raising=False)
    monkeypatch.delenv("GEMINI_CDP_URL", raising=False)
    monkeypatch.setenv("CHROME_DEBUG_PORT", "9226")

    args = SimpleNamespace(cdp_url="")
    assert md._provider_cdp_url(provider="chatgpt", args=args) == "http://127.0.0.1:9226"  # noqa: SLF001
    assert md._provider_cdp_url(provider="gemini", args=args) == "http://127.0.0.1:9226"  # noqa: SLF001


def test_provider_cdp_url_falls_back_when_configured_loopback_port_is_closed(monkeypatch) -> None:
    md = _load_maint_daemon_module()
    monkeypatch.setenv("CHATGPT_CDP_URL", "http://127.0.0.1:9222")
    monkeypatch.delenv("GEMINI_CDP_URL", raising=False)
    monkeypatch.delenv("CHROME_DEBUG_PORT", raising=False)
    monkeypatch.setattr(
        md,
        "port_open",
        lambda host, port, timeout_seconds=0.2: int(port) == 9226,  # noqa: ARG005
    )

    args = SimpleNamespace(cdp_url="http://127.0.0.1:9222")
    assert md._provider_cdp_url(provider="chatgpt", args=args) == "http://127.0.0.1:9226"  # noqa: SLF001
    assert md._provider_cdp_url(provider="gemini", args=args) == "http://127.0.0.1:9226"  # noqa: SLF001


def test_provider_cdp_url_gemini_prefers_args_over_chatgpt_env(monkeypatch) -> None:
    md = _load_maint_daemon_module()
    monkeypatch.delenv("GEMINI_CDP_URL", raising=False)
    monkeypatch.setenv("CHATGPT_CDP_URL", "http://127.0.0.1:9222")
    monkeypatch.setattr(md, "port_open", lambda host, port, timeout_seconds=0.2: int(port) == 9444)  # noqa: ARG005

    args = SimpleNamespace(cdp_url="http://127.0.0.1:9444")
    assert md._provider_cdp_url(provider="gemini", args=args) == "http://127.0.0.1:9444"  # noqa: SLF001


def test_resolve_loopback_cdp_url_keeps_non_local_host(monkeypatch) -> None:
    md = _load_maint_daemon_module()
    monkeypatch.setattr(md, "port_open", lambda host, port, timeout_seconds=0.2: False)  # noqa: ARG005
    assert md._resolve_loopback_cdp_url("http://10.0.0.8:9222") == "http://10.0.0.8:9222"  # noqa: SLF001


def test_resolve_loopback_cdp_url_keeps_configured_port_when_already_open(monkeypatch) -> None:
    md = _load_maint_daemon_module()
    monkeypatch.setattr(md, "port_open", lambda host, port, timeout_seconds=0.2: int(port) == 9222)  # noqa: ARG005
    assert md._resolve_loopback_cdp_url("http://127.0.0.1:9222") == "http://127.0.0.1:9222"  # noqa: SLF001


def test_resolve_loopback_cdp_url_prefers_chrome_debug_port_over_default_fallback(monkeypatch) -> None:
    md = _load_maint_daemon_module()
    monkeypatch.setenv("CHROME_DEBUG_PORT", "9333")
    monkeypatch.setattr(
        md,
        "port_open",
        lambda host, port, timeout_seconds=0.2: int(port) in {9333, 9226},  # noqa: ARG005
    )
    assert md._resolve_loopback_cdp_url("http://127.0.0.1:9222") == "http://127.0.0.1:9333"  # noqa: SLF001


def test_resolve_loopback_cdp_url_keeps_original_when_no_fallback_port_open(monkeypatch) -> None:
    md = _load_maint_daemon_module()
    monkeypatch.delenv("CHROME_DEBUG_PORT", raising=False)
    monkeypatch.setattr(md, "port_open", lambda host, port, timeout_seconds=0.2: False)  # noqa: ARG005
    assert md._resolve_loopback_cdp_url("http://127.0.0.1:9222") == "http://127.0.0.1:9222"  # noqa: SLF001


def test_resolve_loopback_cdp_url_probes_0_0_0_0_via_loopback(monkeypatch) -> None:
    md = _load_maint_daemon_module()
    seen_calls: list[tuple[str, int]] = []

    def _fake_port_open(host, port, timeout_seconds=0.2):  # noqa: ANN001, ARG001
        seen_calls.append((str(host), int(port)))
        return str(host) == "127.0.0.1" and int(port) == 9226

    monkeypatch.delenv("CHROME_DEBUG_PORT", raising=False)
    monkeypatch.setattr(md, "port_open", _fake_port_open)
    out = md._resolve_loopback_cdp_url("http://0.0.0.0:9222")  # noqa: SLF001
    assert out == "http://0.0.0.0:9226"
    assert ("127.0.0.1", 9222) in seen_calls
    assert ("127.0.0.1", 9226) in seen_calls


def test_replace_url_port_accepts_host_without_scheme() -> None:
    md = _load_maint_daemon_module()
    assert md._replace_url_port("127.0.0.1:9222", port=9226) == "http://127.0.0.1:9226"  # noqa: SLF001
