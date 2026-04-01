from __future__ import annotations

from pathlib import Path

from chatgptrest.core.control_plane import (
    parse_host_port_from_url,
    preferred_api_python_bin,
    resolve_chatgptrest_api_host_port,
    start_local_api,
)


def test_preferred_api_python_bin_prefers_repo_venv(tmp_path: Path) -> None:
    venv_bin = tmp_path / ".venv" / "bin" / "python"
    venv_bin.parent.mkdir(parents=True, exist_ok=True)
    venv_bin.write_text("#!/bin/sh\n", encoding="utf-8")

    got = preferred_api_python_bin(repo_root=tmp_path, fallback_python="/usr/bin/python3")
    assert got == venv_bin.resolve(strict=False)


def test_resolve_chatgptrest_api_host_port_prefers_base_url(monkeypatch) -> None:
    monkeypatch.setenv("CHATGPTREST_HOST", "127.0.0.1")
    monkeypatch.setenv("CHATGPTREST_PORT", "18711")
    assert resolve_chatgptrest_api_host_port(base_url="http://0.0.0.0:19999") == ("0.0.0.0", 19999)


def test_parse_host_port_from_url_requires_host() -> None:
    assert parse_host_port_from_url("not-a-url") is None


def test_start_local_api_refuses_non_local_host(tmp_path: Path) -> None:
    ok, meta = start_local_api(
        repo_root=tmp_path,
        host="10.0.0.5",
        port=18711,
        action_log=tmp_path / "api.autostart.log",
        wait_seconds=0.0,
    )

    assert ok is False
    assert meta["error"] == "non-local host; refusing to autostart api"
