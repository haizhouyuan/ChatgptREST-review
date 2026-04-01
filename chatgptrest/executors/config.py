"""Unified executor configuration.

Centralizes environment-variable reads into typed config objects so
executor code can reference `cfg.thought_guard_min_seconds` instead of
scattering `os.environ.get(...)` calls throughout business logic.
"""

from __future__ import annotations

import os
from functools import cached_property
from typing import Any


def _env(key: str, default: str = "") -> str:
    return (os.environ.get(key) or "").strip() or default


def _env_int(key: str, default: int = 0) -> int:
    try:
        return int(_env(key, str(default)))
    except (ValueError, TypeError):
        return default


def _env_float(key: str, default: float = 0.0) -> float:
    try:
        return float(_env(key, str(default)))
    except (ValueError, TypeError):
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    raw = _env(key, "").lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


class ChatGPTExecutorConfig:
    """Configuration for the ChatGPT Web executor."""

    @cached_property
    def mcp_root(self) -> str:
        return _env("CHATGPTREST_CHATGPTMCP_ROOT")

    @cached_property
    def default_send_timeout_seconds(self) -> int:
        return _env_int("CHATGPTREST_DEFAULT_SEND_TIMEOUT_SECONDS", 600)

    # ── Thought guard settings ──────────────────────────────────────
    @cached_property
    def thought_guard_min_seconds(self) -> float:
        return _env_float("CHATGPTREST_THOUGHT_GUARD_MIN_SECONDS", 300)

    @cached_property
    def thought_guard_auto_regenerate(self) -> bool:
        return _env_bool("CHATGPTREST_THOUGHT_GUARD_AUTO_REGENERATE", True)

    @cached_property
    def thought_guard_require_thought_for(self) -> bool:
        return _env_bool("CHATGPTREST_THOUGHT_GUARD_REQUIRE_THOUGHT_FOR", False)

    @cached_property
    def thought_guard_trigger_too_short(self) -> bool:
        return _env_bool("CHATGPTREST_THOUGHT_GUARD_TRIGGER_TOO_SHORT", True)

    @cached_property
    def thought_guard_trigger_skipping(self) -> bool:
        return _env_bool("CHATGPTREST_THOUGHT_GUARD_TRIGGER_SKIPPING", True)

    @cached_property
    def thought_guard_trigger_answer_now(self) -> bool:
        return _env_bool("CHATGPTREST_THOUGHT_GUARD_TRIGGER_ANSWER_NOW", True)

    # ── MCP tool call timeouts ──────────────────────────────────────
    @cached_property
    def preflight_timeout_seconds(self) -> float:
        return _env_float("CHATGPTREST_CHATGPT_PREFLIGHT_TIMEOUT_SECONDS", 15.0)

    @cached_property
    def idempotency_get_timeout_seconds(self) -> float:
        return _env_float("CHATGPTREST_CHATGPT_IDEMPOTENCY_GET_TIMEOUT_SECONDS", 20.0)

    @cached_property
    def answer_get_timeout_seconds(self) -> float:
        return _env_float("CHATGPTREST_CHATGPT_ANSWER_GET_TIMEOUT_SECONDS", 30.0)


class GeminiExecutorConfig:
    """Configuration for the Gemini Web executor."""

    @cached_property
    def mcp_root(self) -> str:
        return _env("CHATGPTREST_GEMINIMCP_ROOT")

    @cached_property
    def default_send_timeout_seconds(self) -> int:
        return _env_int("CHATGPTREST_DEFAULT_SEND_TIMEOUT_SECONDS", 600)

    # ── Attachment preprocess ───────────────────────────────────────
    @cached_property
    def max_files_per_prompt(self) -> int:
        return _env_int("CHATGPTREST_GEMINI_MAX_FILES_PER_PROMPT", 10)

    @cached_property
    def attachment_preprocess_enabled(self) -> bool:
        return _env_bool("CHATGPTREST_GEMINI_ATTACHMENT_PREPROCESS_ENABLED", True)

    @cached_property
    def attachment_preprocess_dir(self) -> str:
        return _env("CHATGPTREST_GEMINI_ATTACHMENT_PREPROCESS_DIR", "/tmp/chatgptrest_gemini_inputs")

    @cached_property
    def zip_expand_max_members(self) -> int:
        return _env_int("CHATGPTREST_GEMINI_ZIP_EXPAND_MAX_MEMBERS", 30)

    @cached_property
    def bundle_per_file_max_bytes(self) -> int:
        return _env_int("CHATGPTREST_GEMINI_BUNDLE_PER_FILE_MAX_BYTES", 5_000_000)

    @cached_property
    def bundle_max_bytes(self) -> int:
        return _env_int("CHATGPTREST_GEMINI_BUNDLE_MAX_BYTES", 20_000_000)

    # ── Send retry ──────────────────────────────────────────────────
    @cached_property
    def send_max_retries(self) -> int:
        return _env_int("CHATGPTREST_GEMINI_SEND_MAX_RETRIES", 2)

    @cached_property
    def send_retry_delay(self) -> float:
        return _env_float("CHATGPTREST_GEMINI_SEND_RETRY_DELAY", 5.0)

    # ── Wait transient retry ────────────────────────────────────────
    @cached_property
    def wait_transient_failure_limit(self) -> int:
        return _env_int("CHATGPTREST_GEMINI_WAIT_TRANSIENT_FAILURE_LIMIT", 3)

    @cached_property
    def wait_transient_retry_after_seconds(self) -> float:
        return _env_float("CHATGPTREST_GEMINI_WAIT_TRANSIENT_RETRY_AFTER_SECONDS", 60.0)

    @cached_property
    def idempotency_get_timeout_seconds(self) -> float:
        return _env_float("CHATGPTREST_GEMINI_IDEMPOTENCY_GET_TIMEOUT_SECONDS", 20.0)

    # ── Deep research ───────────────────────────────────────────────
    @cached_property
    def deep_research_expand_zip(self) -> bool:
        return _env_bool("CHATGPTREST_GEMINI_DEEP_RESEARCH_EXPAND_ZIP", True)

    @cached_property
    def expand_zip_always(self) -> bool:
        """Expand .zip attachments for ALL Gemini requests, not just deep_research.

        Fixes: Gemini Drive picker may not handle .zip files — uploading raw
        zips to Drive succeeds but the Gemini UI automation fails to attach
        them from the Drive picker.  Expanding into readable text files and
        bundling avoids this entirely.
        """
        return _env_bool("CHATGPTREST_GEMINI_EXPAND_ZIP_ALWAYS", True)

    @cached_property
    def deep_research_self_check(self) -> bool:
        return _env_bool("CHATGPTREST_GEMINI_DEEP_RESEARCH_SELF_CHECK", True)

    @cached_property
    def deep_research_self_check_timeout_seconds(self) -> int:
        return _env_int("CHATGPTREST_GEMINI_DEEP_RESEARCH_SELF_CHECK_TIMEOUT_SECONDS", 120)

    @cached_property
    def needs_followup_retry_after_seconds(self) -> float:
        return _env_float("CHATGPTREST_GEMINI_NEEDS_FOLLOWUP_RETRY_AFTER_SECONDS", 120.0)

    # ── Answer quality guard ────────────────────────────────────────
    @cached_property
    def answer_quality_guard(self) -> bool:
        return _env_bool("CHATGPTREST_GEMINI_ANSWER_QUALITY_GUARD", True)

    @cached_property
    def semantic_consistency_guard(self) -> bool:
        return _env_bool("CHATGPTREST_GEMINI_SEMANTIC_CONSISTENCY_GUARD", False)

    @cached_property
    def answer_quality_retry_after_seconds(self) -> float:
        return _env_float("CHATGPTREST_GEMINI_ANSWER_QUALITY_RETRY_AFTER_SECONDS", 60.0)

    @cached_property
    def deep_think_auto_fallback(self) -> bool:
        return _env_bool("CHATGPTREST_GEMINI_DEEP_THINK_AUTO_FALLBACK", True)

    @cached_property
    def deep_research_auto_followup(self) -> bool:
        return _env_bool("CHATGPTREST_GEMINI_DEEP_RESEARCH_AUTO_FOLLOWUP", True)

    # ── GDoc fallback ───────────────────────────────────────────────
    @cached_property
    def dr_gdoc_fallback_enabled(self) -> bool:
        return _env_bool("CHATGPTREST_GEMINI_DR_GDOC_FALLBACK_ENABLED", True)

    @cached_property
    def dr_gdoc_fallback_timeout_seconds(self) -> int:
        return _env_int("CHATGPTREST_GEMINI_DR_GDOC_FALLBACK_TIMEOUT_SECONDS", 120)

    @cached_property
    def dr_gdoc_fallback_max_chars(self) -> int:
        return _env_int("CHATGPTREST_GEMINI_DR_GDOC_FALLBACK_MAX_CHARS", 500_000)

    # ── Google Drive / Rclone ───────────────────────────────────────
    @cached_property
    def gdrive_mount_dir(self) -> str:
        return _env("CHATGPTREST_GDRIVE_MOUNT_DIR", "/vol1/1000/gdrive")

    @cached_property
    def gdrive_upload_subdir(self) -> str:
        return _env("CHATGPTREST_GDRIVE_UPLOAD_SUBDIR", "chatgptrest_uploads")

    @cached_property
    def gdrive_rclone_remote(self) -> str:
        return _env("CHATGPTREST_GDRIVE_RCLONE_REMOTE", "gdrive")

    @cached_property
    def gdrive_max_file_bytes(self) -> int:
        return _env_int("CHATGPTREST_GDRIVE_MAX_FILE_BYTES", 100_000_000)

    @cached_property
    def gdrive_cleanup_mode(self) -> str:
        return _env("CHATGPTREST_GDRIVE_CLEANUP_MODE", "move").lower()

    @cached_property
    def gdrive_sync_timeout_seconds(self) -> int:
        return _env_int("CHATGPTREST_GDRIVE_SYNC_TIMEOUT_SECONDS", 120)

    @cached_property
    def gdrive_retry_seconds(self) -> float:
        return _env_float("CHATGPTREST_GDRIVE_RETRY_SECONDS", 10.0)

    @cached_property
    def rclone_bin(self) -> str:
        return _env("CHATGPTREST_RCLONE_BIN", "rclone")

    @cached_property
    def rclone_config(self) -> str:
        return _env("CHATGPTREST_RCLONE_CONFIG") or _env("RCLONE_CONFIG")

    @cached_property
    def rclone_timeout_seconds(self) -> int:
        return _env_int("CHATGPTREST_RCLONE_TIMEOUT_SECONDS", 120)

    @cached_property
    def rclone_copyto_timeout_seconds(self) -> int:
        return _env_int("CHATGPTREST_RCLONE_COPYTO_TIMEOUT_SECONDS", 180)

    @cached_property
    def rclone_delete_timeout_seconds(self) -> int:
        return _env_int("CHATGPTREST_RCLONE_DELETE_TIMEOUT_SECONDS", 60)

    @cached_property
    def rclone_contimeout_seconds(self) -> int:
        return _env_int("CHATGPTREST_RCLONE_CONTIMEOUT_SECONDS", 30)

    @cached_property
    def rclone_io_timeout_seconds(self) -> int:
        return _env_int("CHATGPTREST_RCLONE_IO_TIMEOUT_SECONDS", 60)

    @cached_property
    def rclone_retries(self) -> int:
        return _env_int("CHATGPTREST_RCLONE_RETRIES", 3)

    @cached_property
    def rclone_low_level_retries(self) -> int:
        return _env_int("CHATGPTREST_RCLONE_LOW_LEVEL_RETRIES", 10)

    @cached_property
    def rclone_retries_sleep_seconds(self) -> float:
        return _env_float("CHATGPTREST_RCLONE_RETRIES_SLEEP_SECONDS", 5.0)

    # ── Deep think retry ────────────────────────────────────────────
    @cached_property
    def deep_think_send_retry_enabled(self) -> bool:
        return _env_bool("CHATGPTREST_GEMINI_DEEP_THINK_SEND_RETRY", True)


class QwenExecutorConfig:
    """Configuration for the Qwen Web executor."""

    @cached_property
    def mcp_root(self) -> str:
        return _env("CHATGPTREST_QWENMCP_ROOT")


class LocalLLMExecutorConfig:
    """Configuration for the local OpenAI-compatible LLM executor."""

    @cached_property
    def endpoint_url(self) -> str:
        return _env("CHATGPTREST_LOCAL_LLM_ENDPOINT_URL", "http://127.0.0.1:11434/v1")

    @cached_property
    def model_name(self) -> str:
        return _env("CHATGPTREST_LOCAL_LLM_MODEL", "qwen3:latest")

    @cached_property
    def default_temperature(self) -> float:
        return _env_float("CHATGPTREST_LOCAL_LLM_TEMPERATURE", 0.3)

    @cached_property
    def default_max_tokens(self) -> int:
        return _env_int("CHATGPTREST_LOCAL_LLM_MAX_TOKENS", 4096)

    @cached_property
    def request_timeout_seconds(self) -> int:
        return _env_int("CHATGPTREST_LOCAL_LLM_REQUEST_TIMEOUT_SECONDS", 300)
