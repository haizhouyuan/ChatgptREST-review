"""Provider-specific constants and tool resolution shared between maint daemon and repair executor."""

from __future__ import annotations

import os
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------


def provider_from_kind(kind: str | None) -> str | None:
    raw = str(kind or "").strip().lower()
    if not raw:
        return None
    if raw.startswith("chatgpt_web."):
        return "chatgpt"
    if raw.startswith("gemini_web."):
        return "gemini"
    if raw.startswith("qwen_web."):
        return "qwen"
    return None


# ---------------------------------------------------------------------------
# CDP URLs
# ---------------------------------------------------------------------------


def default_chatgpt_cdp_url() -> str:
    raw_port = (os.environ.get("CHROME_DEBUG_PORT") or "9222").strip() or "9222"
    try:
        port = int(raw_port)
    except Exception:
        port = 9222
    return f"http://127.0.0.1:{port}"


def provider_cdp_url(provider: str) -> str:
    p = str(provider or "").strip().lower()
    default_chatgpt_cdp = default_chatgpt_cdp_url()
    if p == "qwen":
        return (os.environ.get("QWEN_CDP_URL") or "http://127.0.0.1:9335").strip() or "http://127.0.0.1:9335"
    if p == "gemini":
        return (
            os.environ.get("GEMINI_CDP_URL")
            or os.environ.get("CHATGPT_CDP_URL")
            or default_chatgpt_cdp
        ).strip() or default_chatgpt_cdp
    return (os.environ.get("CHATGPT_CDP_URL") or default_chatgpt_cdp).strip() or default_chatgpt_cdp


# ---------------------------------------------------------------------------
# Chrome start/stop scripts
# ---------------------------------------------------------------------------


def provider_chrome_start_script(provider: str) -> Path:
    p = str(provider or "").strip().lower()
    if p == "qwen":
        raw = (os.environ.get("QWEN_CHROME_START_SCRIPT") or "").strip()
        if raw:
            return Path(raw).expanduser()
        return (_REPO_ROOT / "ops" / "qwen_chrome_start.sh").resolve()
    raw = (os.environ.get("CHROME_START_SCRIPT") or os.environ.get("CHATGPT_CHROME_START_SCRIPT") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return (_REPO_ROOT / "ops" / "chrome_start.sh").resolve()


def provider_chrome_stop_script(provider: str) -> Path:
    p = str(provider or "").strip().lower()
    if p == "qwen":
        raw = (os.environ.get("QWEN_CHROME_STOP_SCRIPT") or "").strip()
        if raw:
            return Path(raw).expanduser()
        return (_REPO_ROOT / "ops" / "qwen_chrome_stop.sh").resolve()
    raw = (os.environ.get("CHROME_STOP_SCRIPT") or os.environ.get("CHATGPT_CHROME_STOP_SCRIPT") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return (_REPO_ROOT / "ops" / "chrome_stop.sh").resolve()


# ---------------------------------------------------------------------------
# Provider tool mappings
# ---------------------------------------------------------------------------


def provider_tools(provider: str) -> dict[str, str | None]:
    p = str(provider or "").strip().lower()
    base: dict[str, str | None] = {
        "blocked_status": None,
        "rate_limit_status": None,
        "self_check": None,
        "capture_ui": None,
        "refresh": None,
        "regenerate": None,
        "clear_blocked": None,
        "tab_stats": "chatgpt_web_tab_stats",
    }
    if p == "chatgpt":
        base.update(
            {
                "blocked_status": "chatgpt_web_blocked_status",
                "rate_limit_status": "chatgpt_web_rate_limit_status",
                "self_check": "chatgpt_web_self_check",
                "capture_ui": "chatgpt_web_capture_ui",
                "refresh": "chatgpt_web_refresh",
                "regenerate": "chatgpt_web_regenerate",
                "clear_blocked": "chatgpt_web_clear_blocked",
            }
        )
    elif p == "gemini":
        base.update(
            {
                "self_check": "gemini_web_self_check",
                "capture_ui": "gemini_web_capture_ui",
            }
        )
    elif p == "qwen":
        base.update(
            {
                "blocked_status": "qwen_web_blocked_status",
                "self_check": "qwen_web_self_check",
                "capture_ui": "qwen_web_capture_ui",
            }
        )
    return base
