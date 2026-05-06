from __future__ import annotations

from chatgptrest.core.repair_gate import classify_repair_gate


def test_repair_gate_blocks_attachment_contract_errors() -> None:
    decision = classify_repair_gate(
        kind="gemini_web.ask",
        status="needs_followup",
        error_type="AttachmentContractMissing",
        error="attachments referenced in prompt but caller did not provide file contract",
    )

    assert decision.category == "caller_contract"
    assert decision.reason == "attachment_contract_missing"
    assert decision.terminal_action == "caller_fix_required"
    assert decision.allow_repair_check is False
    assert decision.allow_codex_sre is False
    assert decision.allow_codex_autofix is False
    assert decision.allow_repair_autofix_fallback is False


def test_repair_gate_blocks_external_gemini_prerequisites() -> None:
    decision = classify_repair_gate(
        kind="gemini_web.ask",
        status="error",
        error_type="GeminiUnsupportedRegion",
        error="Gemini is not available in your region",
    )

    assert decision.category == "external_prerequisite"
    assert decision.terminal_action == "external_prerequisite"
    assert decision.allow_codex_sre is False


def test_repair_gate_blocks_chatgpt_frontend_rate_limit() -> None:
    decision = classify_repair_gate(
        kind="chatgpt_web.ask",
        status="blocked",
        error_type="ChatGPTFrontendRateLimit",
        error="ChatGPT frontend rate-limit modal is visible",
    )

    assert decision.category == "external_prerequisite"
    assert decision.reason == "chatgptfrontendratelimit"
    assert decision.terminal_action == "external_prerequisite"
    assert decision.allow_codex_autofix is False


def test_repair_gate_blocks_same_session_repair_fail_closed_errors() -> None:
    decision = classify_repair_gate(
        kind="gemini_web.ask",
        status="needs_followup",
        error_type="GeminiConversationThreadMismatch",
        error="resolved sidebar thread A but landed on thread B",
        conversation_url="https://gemini.google.com/app/abc123456",
    )

    assert decision.category == "provider_fail_closed"
    assert decision.reason == "geminiconversationthreadmismatch"
    assert decision.terminal_action == "same_session_repair"
    assert decision.allow_repair_check is False


def test_repair_gate_blocks_wait_no_thread_without_thread_identity() -> None:
    decision = classify_repair_gate(
        kind="gemini_web.ask",
        status="needs_followup",
        error_type="WaitNoThreadUrlTimeout",
        error="wait phase timed out without stable conversation_url",
        conversation_url="https://gemini.google.com/app",
    )

    assert decision.category == "provider_fail_closed"
    assert decision.reason == "gemini_missing_thread_identity"
    assert decision.terminal_action == "same_session_repair"
    assert decision.allow_codex_sre is False


def test_repair_gate_blocks_max_attempts_when_underlying_issue_is_same_session_repair() -> None:
    decision = classify_repair_gate(
        kind="gemini_web.ask",
        status="error",
        error_type="MaxAttemptsExceeded",
        error="MaxAttemptsExceeded after GeminiBlankSendTimeout and same_session_repair handoff",
        conversation_url="https://gemini.google.com/app",
    )

    assert decision.category == "provider_fail_closed"
    assert decision.reason == "gemini_missing_thread_identity"
    assert decision.allow_codex_autofix is False


def test_repair_gate_blocks_chatgpt_send_same_session_repair_without_thread() -> None:
    decision = classify_repair_gate(
        kind="chatgpt_web.ask",
        status="error",
        phase="send",
        error_type="ToolCallError",
        error="mcp_http tool chatgpt_web_ask failed: McpHttpError: SSE stream timeout (deadline exceeded).",
        conversation_url="https://chatgpt.com",
    )

    assert decision.category == "provider_fail_closed"
    assert decision.reason == "send_phase_same_session_repair_without_thread"
    assert decision.terminal_action == "same_session_repair"
    assert decision.allow_codex_sre is False


def test_repair_gate_blocks_attachment_file_not_found() -> None:
    decision = classify_repair_gate(
        kind="chatgpt_web.ask",
        status="error",
        error_type="AttachmentFileNotFound",
        error="input.file_paths no longer exist on disk",
    )

    assert decision.category == "caller_contract"
    assert decision.reason == "attachment_contract_missing"
    assert decision.terminal_action == "caller_fix_required"
