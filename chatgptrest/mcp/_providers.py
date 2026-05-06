"""Provider detection & routing utilities for MCP tools."""

from __future__ import annotations

PROVIDER_TO_KIND = {
    "chatgpt": "chatgpt_web.ask",
    "gemini": "gemini_web.ask",
}

KIND_TO_PROVIDER = {v: k for k, v in PROVIDER_TO_KIND.items()}


def detect_provider(url: str | None) -> str | None:
    """Detect provider from conversation URL. Returns 'chatgpt', 'gemini', 'qwen', or None."""
    raw = str(url or "").strip().lower()
    if not raw:
        return None
    if "chatgpt.com" in raw or "chat.openai.com" in raw:
        return "chatgpt"
    if "gemini.google.com" in raw:
        return "gemini"
    if "qianwen.com" in raw:
        return "qwen"
    return None


def looks_like_chatgpt_conversation_url(url: str | None) -> bool:
    return detect_provider(url) == "chatgpt"


def looks_like_gemini_conversation_url(url: str | None) -> bool:
    return detect_provider(url) == "gemini"


def looks_like_qwen_conversation_url(url: str | None) -> bool:
    return detect_provider(url) == "qwen"


def resolve_provider(
    *,
    provider: str | None = None,
    conversation_url: str | None = None,
    parent_job: dict | None = None,
) -> str:
    """Resolve provider from explicit value, conversation URL, or parent job kind."""
    if provider:
        p = str(provider).strip().lower()
        if p == "qwen":
            raise ValueError("Unknown provider 'qwen'. Supported: chatgpt, gemini (qwen has been retired)")
        if p in PROVIDER_TO_KIND:
            return p
        raise ValueError(f"Unknown provider '{provider}'. Supported: chatgpt, gemini")
    if conversation_url:
        detected = detect_provider(conversation_url)
        if detected == "qwen":
            raise ValueError("Qwen thread URLs are no longer supported; use chatgpt or gemini instead.")
        if detected:
            return detected
    if parent_job and isinstance(parent_job, dict):
        kind = str(parent_job.get("kind") or "").strip().lower()
        if kind == "qwen_web.ask":
            raise ValueError("Qwen follow-up threads are no longer supported; use chatgpt or gemini instead.")
        if kind in KIND_TO_PROVIDER:
            return KIND_TO_PROVIDER[kind]
    return "chatgpt"  # default
