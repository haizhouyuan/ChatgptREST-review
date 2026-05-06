from __future__ import annotations

from chatgpt_web_mcp.providers.gemini_helpers import _looks_like_gemini_infra_error

from chatgptrest.core.job_store import (
    _chatgpt_is_base_app_url,
    _gemini_is_base_app_url,
)

_MANUAL_REPAIR_COOLDOWN_ERROR_TYPES = frozenset({
    "blocked",
    "geminiconversationthreadmismatch",
    "verificationrequired",
})

_MANUAL_REPAIR_COOLDOWN_MARKERS = (
    "cloudflare",
    "verification",
    "captcha",
    "just a moment",
    "upload menu button not found",
    "sse stream timeout",
    "sse stream ended without a json-rpc response",
)


def has_provider_thread_evidence(*, conversation_url: str, conversation_id: str) -> bool:
    normalized_conversation_id = str(conversation_id or "").strip()
    if normalized_conversation_id:
        return True
    normalized_conversation_url = str(conversation_url or "").strip()
    if not normalized_conversation_url:
        return False
    if _gemini_is_base_app_url(normalized_conversation_url) or _chatgpt_is_base_app_url(normalized_conversation_url):
        return False
    return True


def send_phase_requires_same_session_repair_without_thread(
    *,
    phase: str,
    conversation_url: str,
    conversation_id: str,
    last_error_type: str,
    last_error: str,
) -> bool:
    if str(phase or "").strip().lower() != "send":
        return False
    if has_provider_thread_evidence(
        conversation_url=conversation_url,
        conversation_id=conversation_id,
    ):
        return False
    error_type = str(last_error_type or "").strip().lower()
    error_text = str(last_error or "").strip().lower()
    normalized_conversation_url = str(conversation_url or "").strip()
    if not normalized_conversation_url:
        if error_type in _MANUAL_REPAIR_COOLDOWN_ERROR_TYPES:
            return True
        return any(marker in error_text for marker in _MANUAL_REPAIR_COOLDOWN_MARKERS)
    if not _gemini_is_base_app_url(normalized_conversation_url):
        if _chatgpt_is_base_app_url(normalized_conversation_url):
            if error_type in _MANUAL_REPAIR_COOLDOWN_ERROR_TYPES:
                return True
            return any(marker in error_text for marker in _MANUAL_REPAIR_COOLDOWN_MARKERS)
        return False
    if error_type in _MANUAL_REPAIR_COOLDOWN_ERROR_TYPES:
        return True
    if error_type == "infraerror" and _looks_like_gemini_infra_error(str(last_error or "")):
        return True
    return any(marker in error_text for marker in _MANUAL_REPAIR_COOLDOWN_MARKERS)


def queued_pause_requires_same_session_repair(
    *,
    phase: str,
    retry_after: object,
    pause_mode: str,
    pause_reason: str,
    conversation_url: str,
    conversation_id: str,
) -> bool:
    if str(phase or "").strip().lower() != "send":
        return False
    if not isinstance(retry_after, int) or retry_after <= 0:
        return False
    normalized_conversation_id = str(conversation_id or "").strip()
    normalized_conversation_url = str(conversation_url or "").strip()
    if normalized_conversation_id:
        return False
    if not normalized_conversation_url or not _gemini_is_base_app_url(normalized_conversation_url):
        return False
    mode = str(pause_mode or "").strip().lower()
    if mode not in {"send", "all"}:
        return False
    reason = str(pause_reason or "").strip().lower()
    if not reason:
        return False
    if reason.startswith("auto_blocked:"):
        return True
    return any(marker in reason for marker in _MANUAL_REPAIR_COOLDOWN_MARKERS)


def cooldown_requires_same_session_repair(
    *,
    phase: str,
    conversation_url: str,
    conversation_id: str,
    last_error_type: str,
    last_error: str,
) -> bool:
    return send_phase_requires_same_session_repair_without_thread(
        phase=phase,
        conversation_url=conversation_url,
        conversation_id=conversation_id,
        last_error_type=last_error_type,
        last_error=last_error,
    )


def error_requires_same_session_repair(
    *,
    phase: str,
    conversation_url: str,
    conversation_id: str,
    last_error_type: str,
    last_error: str,
) -> bool:
    if send_phase_requires_same_session_repair_without_thread(
        phase=phase,
        conversation_url=conversation_url,
        conversation_id=conversation_id,
        last_error_type=last_error_type,
        last_error=last_error,
    ):
        return True
    error_type = str(last_error_type or "").strip().lower()
    if error_type == "geminiblanksendtimeout":
        return True
    has_thread = has_provider_thread_evidence(
        conversation_url=conversation_url,
        conversation_id=conversation_id,
    )
    if not has_thread:
        return False
    if error_type == "geminiconversationthreadmismatch":
        return True
    error_text = str(last_error or "").strip().lower()
    return "different gemini thread than requested" in error_text
