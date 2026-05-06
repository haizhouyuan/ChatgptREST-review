from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_maint_daemon_module():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "ops" / "maint_daemon.py"
    spec = importlib.util.spec_from_file_location("chatgptrest_ops_maint_daemon_stuck_watchdog", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_kick_watchdog_uses_notify_socket_without_sdnotify(monkeypatch) -> None:
    md = _load_maint_daemon_module()
    captured: dict[str, object] = {}

    class _FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def connect(self, addr):
            captured["addr"] = addr

        def sendall(self, payload: bytes):
            captured["payload"] = payload

    monkeypatch.setenv("NOTIFY_SOCKET", "@watchdog-test")
    monkeypatch.setattr(md.socket, "socket", lambda *args, **kwargs: _FakeSocket())

    md._kick_watchdog(status="maint loop healthy")

    assert captured["addr"] == b"\0watchdog-test"
    assert captured["payload"] == b"WATCHDOG=1\nSTATUS=maint loop healthy"


def test_start_watchdog_heartbeat_sends_ready_and_reuses_thread(monkeypatch) -> None:
    md = _load_maint_daemon_module()
    notify_calls: list[tuple[str, ...]] = []
    started_names: list[str] = []

    monkeypatch.setattr(md, "_systemd_notify", lambda *lines: notify_calls.append(tuple(lines)) or True)

    class _FakeThread:
        def __init__(self, *, target, args, name, daemon):
            self._target = target
            self._args = args
            self.name = name
            self.daemon = daemon
            self._alive = False

        def start(self):
            started_names.append(self.name)
            self._alive = True

        def is_alive(self):
            return self._alive

        def join(self, timeout=None):
            self._alive = False

    monkeypatch.setattr(md.threading, "Thread", _FakeThread)

    md._watchdog_thread = None
    md._watchdog_thread_active = False
    md._start_watchdog_heartbeat(status="maint_daemon booted")
    md._start_watchdog_heartbeat(status="ignored second start")

    assert notify_calls[0] == ("READY=1", "STATUS=maint_daemon booted")
    assert started_names == ["maint-daemon-watchdog"]
    assert md._watchdog_thread_active is True

    md._stop_watchdog_heartbeat()
    assert md._watchdog_thread_active is False
