from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chatgptrest.providers.registry import looks_like_thread_url as provider_looks_like_thread_url
from chatgptrest.core.web_same_session_repair import send_phase_requires_same_session_repair_without_thread


_CALLER_CONTRACT_ERROR_TYPES = frozenset({
    "attachmentcontractmissing",
    "attachmentfilenotfound",
})

_EXTERNAL_PREREQUISITE_ERROR_TYPES = frozenset({
    "chatgptfrontendratelimit",
    "geminicaptcha",
    "geminigoogleverification",
    "gemininotloggedin",
    "geminiunsupportedregion",
})

_PROVIDER_FAIL_CLOSED_ERROR_TYPES = frozenset({
    "geminiblanksendtimeout",
    "geminiconversationthreadmismatch",
    "geminidriveattachunavailable",
})

_EXTERNAL_PREREQUISITE_MARKERS = (
    "modal-conversation-history-rate-limit",
    "conversation history rate limit",
    "frontend rate-limit modal",
    "captcha",
    "google verification",
    "human verification",
    "not logged in",
    "requires login",
    "unsupported region",
    "not available in your region",
)

_SAME_SESSION_REPAIR_HINT_MARKERS = (
    "geminiblanksendtimeout",
    "geminiconversationthreadmismatch",
    "geminidriveattachunavailable",
    "waitnothreadurltimeout",
    "same_session_repair",
)


@dataclass(frozen=True)
class RepairGateDecision:
    category: str
    reason: str
    allow_repair_check: bool
    allow_codex_sre: bool
    allow_codex_autofix: bool
    allow_repair_autofix_fallback: bool
    terminal_action: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "reason": self.reason,
            "allow_repair_check": self.allow_repair_check,
            "allow_codex_sre": self.allow_codex_sre,
            "allow_codex_autofix": self.allow_codex_autofix,
            "allow_repair_autofix_fallback": self.allow_repair_autofix_fallback,
            "terminal_action": self.terminal_action,
        }


def _default_allow() -> RepairGateDecision:
    return RepairGateDecision(
        category="allow",
        reason="generic_runtime_recovery",
        allow_repair_check=True,
        allow_codex_sre=True,
        allow_codex_autofix=True,
        allow_repair_autofix_fallback=True,
        terminal_action=None,
    )


def _deny_all(*, category: str, reason: str, terminal_action: str) -> RepairGateDecision:
    return RepairGateDecision(
        category=category,
        reason=reason,
        allow_repair_check=False,
        allow_codex_sre=False,
        allow_codex_autofix=False,
        allow_repair_autofix_fallback=False,
        terminal_action=terminal_action,
    )


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower()


def _combined_text(*parts: Any) -> str:
    return " ".join(_normalized(part) for part in parts if _normalized(part))


def _looks_like_same_session_repair_without_thread(*, kind: str, error_type: str, error: str, conversation_url: str | None) -> bool:
    normalized_kind = _normalized(kind)
    if not normalized_kind.startswith("gemini_web."):
        return False
    if provider_looks_like_thread_url(normalized_kind, conversation_url):
        return False
    if error_type == "waitnothreadurltimeout":
        return True
    combined = _combined_text(error_type, error)
    if error_type == "maxattemptsexceeded":
        return any(marker in combined for marker in _SAME_SESSION_REPAIR_HINT_MARKERS)
    return False


def classify_repair_gate(
    *,
    kind: str | None,
    status: str | None,
    error_type: str | None,
    error: str | None,
    phase: str | None = None,
    conversation_url: str | None = None,
    conversation_id: str | None = None,
) -> RepairGateDecision:
    del status  # reserved for future expansion; the current gate is error-family driven.
    normalized_kind = _normalized(kind)
    normalized_error_type = _normalized(error_type)
    combined = _combined_text(error_type, error)

    if normalized_error_type in _CALLER_CONTRACT_ERROR_TYPES:
        return _deny_all(
            category="caller_contract",
            reason="attachment_contract_missing",
            terminal_action="caller_fix_required",
        )

    if normalized_error_type in _EXTERNAL_PREREQUISITE_ERROR_TYPES or any(
        marker in combined for marker in _EXTERNAL_PREREQUISITE_MARKERS
    ):
        return _deny_all(
            category="external_prerequisite",
            reason=(normalized_error_type or "external_prerequisite"),
            terminal_action="external_prerequisite",
        )

    if normalized_error_type in _PROVIDER_FAIL_CLOSED_ERROR_TYPES:
        return _deny_all(
            category="provider_fail_closed",
            reason=normalized_error_type,
            terminal_action="same_session_repair",
        )

    if _looks_like_same_session_repair_without_thread(
        kind=normalized_kind,
        error_type=normalized_error_type,
        error=error or "",
        conversation_url=conversation_url,
    ):
        return _deny_all(
            category="provider_fail_closed",
            reason="gemini_missing_thread_identity",
            terminal_action="same_session_repair",
        )

    if send_phase_requires_same_session_repair_without_thread(
        phase=str(phase or ""),
        conversation_url=str(conversation_url or ""),
        conversation_id=str(conversation_id or ""),
        last_error_type=str(error_type or ""),
        last_error=str(error or ""),
    ):
        return _deny_all(
            category="provider_fail_closed",
            reason="send_phase_same_session_repair_without_thread",
            terminal_action="same_session_repair",
        )

    return _default_allow()
