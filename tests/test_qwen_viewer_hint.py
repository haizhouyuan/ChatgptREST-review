from __future__ import annotations

from pathlib import Path

from chatgpt_web_mcp.providers import qwen_web


def test_qwen_viewer_novnc_url_reads_bind_host_file(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "qwen_viewer"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "novnc_bind_host.txt").write_text("100.124.54.52\n", encoding="utf-8")

    monkeypatch.setenv("QWEN_VIEWER_RUN_DIR", str(run_dir))
    monkeypatch.delenv("QWEN_VIEWER_NOVNC_BIND_HOST", raising=False)
    monkeypatch.delenv("QWEN_VIEWER_NOVNC_PORT", raising=False)

    assert qwen_web._qwen_viewer_novnc_url() == "http://100.124.54.52:6085/vnc.html"


def test_qwen_viewer_novnc_url_port_override(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "qwen_viewer"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "novnc_bind_host.txt").write_text("127.0.0.1", encoding="utf-8")

    monkeypatch.setenv("QWEN_VIEWER_RUN_DIR", str(run_dir))
    monkeypatch.setenv("QWEN_VIEWER_NOVNC_PORT", "12345")

    assert qwen_web._qwen_viewer_novnc_url() == "http://127.0.0.1:12345/vnc.html"


def test_qwen_viewer_novnc_url_rewrites_wildcard_host(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "qwen_viewer"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "novnc_bind_host.txt").write_text("0.0.0.0", encoding="utf-8")

    monkeypatch.setenv("QWEN_VIEWER_RUN_DIR", str(run_dir))
    monkeypatch.delenv("QWEN_VIEWER_NOVNC_PORT", raising=False)

    assert qwen_web._qwen_viewer_novnc_url() == "http://127.0.0.1:6085/vnc.html"

