from __future__ import annotations

from pathlib import Path


def test_codex_bin_falls_back_to_home_install(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CHATGPTREST_CODEX_BIN", raising=False)
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.setenv("HOME", str(tmp_path))

    codex_path = tmp_path / ".home-codex-official" / ".local" / "bin" / "codex"
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    codex_path.chmod(0o755)

    from chatgptrest.core import codex_runner

    assert codex_runner._codex_bin() == str(codex_path)  # noqa: SLF001


def test_codex_bin_prefers_known_wrapper_over_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CHATGPTREST_CODEX_BIN", raising=False)
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    path_bin = tmp_path / "bin"
    path_bin.mkdir(parents=True, exist_ok=True)
    path_codex = path_bin / "codex"
    path_codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path_codex.chmod(0o755)
    monkeypatch.setenv("PATH", str(path_bin))

    wrapper_codex = tmp_path / ".home-codex-official" / ".local" / "bin" / "codex"
    wrapper_codex.parent.mkdir(parents=True, exist_ok=True)
    wrapper_codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper_codex.chmod(0o755)

    from chatgptrest.core import codex_runner

    assert codex_runner._codex_bin() == str(wrapper_codex)  # noqa: SLF001
