from __future__ import annotations

import asyncio
import importlib
import importlib.util
import inspect
import sys
from pathlib import Path


def _load_driver_server_module():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "chatgptrest_driver_server.py"
    spec = importlib.util.spec_from_file_location("chatgptrest_driver_server_smoke", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_driver_entrypoint_import_smoke() -> None:
    mod = _load_driver_server_module()
    assert hasattr(mod, "main")


def test_driver_main_parses_args_and_dispatches(monkeypatch) -> None:
    mod = _load_driver_server_module()
    calls: dict[str, str] = {}

    class _DummyMcp:
        def run(self, *, transport: str) -> None:
            calls["run"] = str(transport)

    class _DummyImpl:
        mcp = _DummyMcp()

        @staticmethod
        def _acquire_server_singleton_lock_or_die(*, transport: str) -> None:
            calls["lock"] = str(transport)

    monkeypatch.setattr(mod, "_impl", _DummyImpl)
    monkeypatch.setattr(sys, "argv", ["chatgptrest_driver_server.py", "--transport", "stdio"])
    mod.main()
    assert calls["lock"] == "stdio"
    assert calls["run"] == "stdio"


def test_gemini_capture_ui_entrypoint_exists() -> None:
    mod = importlib.import_module("chatgpt_web_mcp.providers.gemini_web")
    out = asyncio.run(mod.gemini_web_capture_ui(mode="invalid-mode"))
    assert out["ok"] is False
    assert out["error_type"] == "ValueError"


def test_gemini_wait_keeps_deep_research_compat_param() -> None:
    wait_mod = importlib.import_module("chatgpt_web_mcp.providers.gemini.wait")
    sig = inspect.signature(wait_mod.gemini_web_wait)
    assert "deep_research" in sig.parameters
