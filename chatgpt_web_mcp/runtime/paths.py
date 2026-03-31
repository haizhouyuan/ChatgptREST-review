from __future__ import annotations

import os
from pathlib import Path


def _debug_dir() -> Path | None:
    raw = (
        os.environ.get("MCP_DEBUG_DIR")
        or os.environ.get("CHATGPT_DEBUG_DIR")
        or os.environ.get("GEMINI_DEBUG_DIR")
        or ""
    ).strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _ui_snapshot_base_dir() -> Path:
    raw = (os.environ.get("CHATGPT_UI_SNAPSHOT_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    debug_dir = _debug_dir()
    if debug_dir is not None:
        return debug_dir / "ui_snapshots"
    return Path("artifacts/ui_snapshots")


def _ui_snapshot_doc_path() -> Path:
    raw = (os.environ.get("CHATGPT_UI_SNAPSHOT_DOC") or "docs/chatgpt_web_ui_reference.md").strip()
    return Path(raw).expanduser()


def _qwen_ui_snapshot_base_dir() -> Path:
    raw = (os.environ.get("QWEN_UI_SNAPSHOT_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    debug_dir = _debug_dir()
    if debug_dir is not None:
        return debug_dir / "qwen_ui_snapshots"
    return Path("artifacts/qwen_ui_snapshots")


def _qwen_ui_snapshot_doc_path() -> Path:
    raw = (os.environ.get("QWEN_UI_SNAPSHOT_DOC") or "docs/qwen_web_ui_reference.md").strip()
    return Path(raw).expanduser()


def _gemini_ui_snapshot_base_dir() -> Path:
    raw = (os.environ.get("GEMINI_UI_SNAPSHOT_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    debug_dir = _debug_dir()
    if debug_dir is not None:
        return debug_dir / "gemini_ui_snapshots"
    return Path("artifacts/gemini_ui_snapshots")


def _gemini_ui_snapshot_doc_path() -> Path:
    raw = (os.environ.get("GEMINI_UI_SNAPSHOT_DOC") or "docs/gemini_web_ui_reference.md").strip()
    return Path(raw).expanduser()
