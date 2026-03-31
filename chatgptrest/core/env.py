"""Central environment variable registry with validation, defaults, and documentation.

Every CHATGPTREST_* env var should be registered here.  Accessor functions
(get_str, get_int, get_bool, get_float) enforce range bounds and return the
registered default when the raw value is missing or invalid.

dump_all() produces a redacted snapshot suitable for ``/v1/ops/config``:

    Redaction priority (fail-safe):
      1. ``_NON_SENSITIVE_ALLOWLIST`` → never redacted  (explicit audit)
      2. ``spec.sensitive == True``   → always redacted  (explicit flag)
      3. ``_is_sensitive_name()``     → auto-redacted    (name pattern match)

    Unregistered env vars never appear in the output.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Type enum
# ---------------------------------------------------------------------------

class EnvType(Enum):
    STRING = "string"
    INT = "int"
    BOOL = "bool"
    FLOAT = "float"


# ---------------------------------------------------------------------------
# Spec dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EnvVar:
    name: str
    type: EnvType
    default: Any
    description: str
    category: str  # "core", "chatgpt", "gemini", "qwen", "repair", "mcp", "maint", "rclone", "gdrive"
    sensitive: bool = False
    min_value: int | float | None = None
    max_value: int | float | None = None


# ---------------------------------------------------------------------------
# Auto-redact helpers (fail-safe)
# ---------------------------------------------------------------------------

_SENSITIVE_NAME_RE = re.compile(
    r"(TOKEN|SECRET|KEY|PASSWORD|PASSWD|PROXY|CREDENTIAL|AUTH)",
    re.I,
)

# Audited exceptions: vars whose *name* matches _SENSITIVE_NAME_RE but are
# known non-sensitive.  Keep this empty by default (fail-safe).
_NON_SENSITIVE_ALLOWLIST: frozenset[str] = frozenset()


def _is_sensitive_name(name: str) -> bool:
    """Auto-redact: name contains TOKEN/SECRET/KEY/PASSWORD/PROXY etc."""
    return bool(_SENSITIVE_NAME_RE.search(name))


def _effective_sensitive(spec: EnvVar) -> bool:
    """allowlist(audited) > explicit/name-match.  Default is fail-safe."""
    if spec.name in _NON_SENSITIVE_ALLOWLIST:
        return False
    return spec.sensitive or _is_sensitive_name(spec.name)


# ---------------------------------------------------------------------------
# Complete registry
# ---------------------------------------------------------------------------

REGISTRY: tuple[EnvVar, ...] = (
    # ── core ──────────────────────────────────────────────────────────────
    EnvVar("CHATGPTREST_DB_PATH", EnvType.STRING, "state/jobdb.sqlite3",
           "SQLite database file path", "core"),
    EnvVar("CHATGPTREST_ARTIFACTS_DIR", EnvType.STRING, "artifacts",
           "Directory for job artifacts", "core"),
    EnvVar("CHATGPTREST_API_TOKEN", EnvType.STRING, "",
           "API bearer token (Authorization header)", "core", sensitive=True),
    EnvVar("CHATGPTREST_OPS_TOKEN", EnvType.STRING, "",
           "Ops bearer token for admin/ops endpoints", "core", sensitive=True),
    EnvVar("CHATGPTREST_ADMIN_TOKEN", EnvType.STRING, "",
           "Legacy alias for OPS_TOKEN", "core", sensitive=True),
    EnvVar("CHATGPTREST_HOST", EnvType.STRING, "0.0.0.0",
           "API server bind host", "core"),
    EnvVar("CHATGPTREST_PORT", EnvType.INT, 18711,
           "API server bind port", "core"),
    EnvVar("CHATGPTREST_BASE_URL", EnvType.STRING, "",
           "External base URL for link generation", "core"),
    EnvVar("CHATGPTREST_PREVIEW_CHARS", EnvType.INT, 1200,
           "Max chars for answer preview in list endpoints", "core", min_value=0),
    EnvVar("CHATGPTREST_LEASE_TTL_SECONDS", EnvType.INT, 60,
           "Worker lease expiration time", "core", min_value=5),
    EnvVar("CHATGPTREST_MAX_ATTEMPTS", EnvType.INT, 3,
           "Default max retry attempts per job", "core", min_value=1),
    EnvVar("CHATGPTREST_WAIT_SLICE_SECONDS", EnvType.INT, 60,
           "Wait-phase polling slice duration", "core", min_value=0),
    EnvVar("CHATGPTREST_WAIT_SLICE_GROWTH_FACTOR", EnvType.FLOAT, 1.0,
           "Multiplicative growth factor for adaptive wait slice", "core",
           min_value=1.0, max_value=5.0),
    EnvVar("CHATGPTREST_REQUEST_ID_PREFIX", EnvType.STRING, "",
           "Prefix for generated request IDs", "core"),
    EnvVar("CHATGPTREST_GIT_SHA", EnvType.STRING, "",
           "Build git SHA (injected at deploy)", "core"),
    EnvVar("CHATGPTREST_GIT_DIRTY", EnvType.STRING, "",
           "Build git dirty flag (injected at deploy)", "core"),
    EnvVar("CHATGPTREST_DRIVER_MODE", EnvType.STRING, "external_mcp",
           "Driver mode: external_mcp | internal_mcp | embedded", "core"),
    EnvVar("CHATGPTREST_DRIVER_URL", EnvType.STRING, "",
           "Driver MCP URL (defaults to CHATGPT_MCP_URL)", "core"),
    EnvVar("CHATGPTREST_DRIVER_ROOT", EnvType.STRING, "",
           "Driver filesystem root for artifact resolution", "core"),
    EnvVar("CHATGPTREST_CHATGPT_MCP_URL", EnvType.STRING, "http://127.0.0.1:18701/mcp",
           "ChatGPT MCP server endpoint", "core"),

    # ── job submission & validation ───────────────────────────────────────
    EnvVar("CHATGPTREST_BLOCK_PRO_SMOKE_TEST", EnvType.BOOL, True,
           "Block smoke-test prompts on Pro presets", "chatgpt"),
    EnvVar("CHATGPTREST_BLOCK_TRIVIAL_PRO_PROMPT", EnvType.BOOL, True,
           "Block trivially short prompts on Pro presets", "chatgpt"),
    EnvVar("CHATGPTREST_BLOCK_SMOKETEST_PREFIX", EnvType.BOOL, False,
           "Block prompts starting with smoketest prefix", "chatgpt"),
    EnvVar("CHATGPTREST_CONVERSATION_SINGLE_FLIGHT", EnvType.BOOL, True,
           "Prevent concurrent jobs on same conversation", "core"),
    EnvVar("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", EnvType.BOOL, False,
           "Require X-Trace-* headers for write operations", "core"),
    EnvVar("CHATGPTREST_REQUIRE_CANCEL_REASON", EnvType.BOOL, False,
           "Require reason text for cancel requests", "core"),
    EnvVar("CHATGPTREST_CANCEL_REASON_MAX_CHARS", EnvType.INT, 240,
           "Max length for cancel reason text", "core", min_value=40, max_value=2000),
    EnvVar("CHATGPTREST_CANCEL_REASON_DEFAULT", EnvType.STRING, "",
           "Default cancel reason when not provided", "core"),
    EnvVar("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", EnvType.STRING, "",
           "CSV of allowed client names (empty = allow all)", "core"),
    EnvVar("CHATGPTREST_FALLBACK_CLIENT_NAME_ALLOWLIST_WHEN_MCP_DOWN", EnvType.STRING, "",
           "CSV of client names allowed when MCP is down", "core"),
    EnvVar("CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST", EnvType.STRING, "",
           "CSV of client names allowed to cancel", "core"),
    EnvVar("CHATGPTREST_ALLOW_FALLBACK_WHEN_MCP_DOWN", EnvType.BOOL, False,
           "Allow job submission fallback when MCP is down", "core"),
    EnvVar("CHATGPTREST_CLIENT_NAME", EnvType.STRING, "chatgptrest",
           "Client name for outgoing MCP calls", "core"),
    EnvVar("CHATGPTREST_CLIENT_INSTANCE", EnvType.STRING, "",
           "Client instance identifier", "core"),

    # ── rate limiting ─────────────────────────────────────────────────────
    EnvVar("CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS", EnvType.INT, 61,
           "Minimum seconds between ChatGPT prompts", "chatgpt", min_value=0),
    EnvVar("CHATGPTREST_GEMINI_MIN_PROMPT_INTERVAL_SECONDS", EnvType.INT, 61,
           "Minimum seconds between Gemini prompts (defaults to ChatGPT value)", "gemini", min_value=0),
    EnvVar("CHATGPTREST_QWEN_MIN_PROMPT_INTERVAL_SECONDS", EnvType.INT, 0,
           "Minimum seconds between Qwen prompts", "qwen", min_value=0),
    EnvVar("CHATGPTREST_QWEN_ENABLED", EnvType.BOOL, False,
           "Enable Qwen provider for job processing", "qwen"),
    EnvVar("CHATGPTREST_CHATGPT_MAX_PROMPTS_PER_HOUR", EnvType.INT, 0,
           "Max ChatGPT prompts per hour (0 = unlimited)", "chatgpt", min_value=0),
    EnvVar("CHATGPTREST_CHATGPT_MAX_PROMPTS_PER_DAY", EnvType.INT, 0,
           "Max ChatGPT prompts per day (0 = unlimited)", "chatgpt", min_value=0),

    # ── ChatGPT executor ──────────────────────────────────────────────────
    EnvVar("CHATGPTREST_CHATGPTMCP_ROOT", EnvType.STRING, "",
           "chatgptMCP repo root for artifact resolution", "chatgpt"),
    EnvVar("CHATGPTREST_DEFAULT_SEND_TIMEOUT_SECONDS", EnvType.INT, 180,
           "Default cap for send-phase timeout (0 = no cap)", "chatgpt", min_value=0),
    EnvVar("CHATGPTREST_PRO_FALLBACK_PRESETS", EnvType.STRING, "thinking_heavy,auto",
           "CSV of fallback presets for pro_extended", "chatgpt"),
    EnvVar("CHATGPTREST_THOUGHT_GUARD_MIN_SECONDS", EnvType.INT, 300,
           "Minimum acceptable thinking duration", "chatgpt", min_value=0),
    EnvVar("CHATGPTREST_THOUGHT_GUARD_AUTO_REGENERATE", EnvType.BOOL, True,
           "Auto-regenerate on abnormal thinking", "chatgpt"),
    EnvVar("CHATGPTREST_THOUGHT_GUARD_REQUIRE_THOUGHT_FOR", EnvType.BOOL, False,
           "Require thinking observation presence (strict mode)", "chatgpt"),
    EnvVar("CHATGPTREST_THOUGHT_GUARD_TRIGGER_TOO_SHORT", EnvType.BOOL, True,
           "Trigger guard on too-short thinking", "chatgpt"),
    EnvVar("CHATGPTREST_THOUGHT_GUARD_TRIGGER_SKIPPING", EnvType.BOOL, True,
           "Trigger guard on thinking skipping", "chatgpt"),
    EnvVar("CHATGPTREST_THOUGHT_GUARD_TRIGGER_ANSWER_NOW", EnvType.BOOL, True,
           "Trigger guard on answer-now visible", "chatgpt"),

    # ── Gemini executor ───────────────────────────────────────────────────
    EnvVar("CHATGPTREST_GEMINI_ANSWER_QUALITY_GUARD", EnvType.BOOL, True,
           "Enable Gemini answer quality guard (UI noise strip)", "gemini"),
    EnvVar("CHATGPTREST_GEMINI_SEMANTIC_CONSISTENCY_GUARD", EnvType.BOOL, False,
           "Strict semantic consistency guard for Gemini", "gemini"),
    EnvVar("CHATGPTREST_GEMINI_ANSWER_QUALITY_RETRY_AFTER_SECONDS", EnvType.INT, 180,
           "Retry delay after quality guard rejection", "gemini", min_value=30, max_value=1800),
    EnvVar("CHATGPTREST_GEMINI_NEEDS_FOLLOWUP_RETRY_AFTER_SECONDS", EnvType.INT, 180,
           "Retry delay after needs_followup status", "gemini", min_value=30),
    EnvVar("CHATGPTREST_GEMINI_WAIT_TRANSIENT_FAILURE_LIMIT", EnvType.INT, 2,
           "Max transient wait failures before giving up", "gemini", min_value=1, max_value=8),
    EnvVar("CHATGPTREST_GEMINI_WAIT_TRANSIENT_RETRY_AFTER_SECONDS", EnvType.INT, 20,
           "Retry delay after transient wait error", "gemini", min_value=5, max_value=300),
    EnvVar("CHATGPTREST_GEMINI_DR_GDOC_FALLBACK_ENABLED", EnvType.BOOL, True,
           "Enable deep research GDoc export fallback", "gemini"),
    EnvVar("CHATGPTREST_GEMINI_DR_GDOC_FALLBACK_TIMEOUT_SECONDS", EnvType.INT, 120,
           "Timeout for GDoc fallback export", "gemini", min_value=20, max_value=900),
    EnvVar("CHATGPTREST_GEMINI_DR_GDOC_FALLBACK_MAX_CHARS", EnvType.INT, 400_000,
           "Max chars for GDoc fallback content", "gemini", min_value=2_000, max_value=2_000_000),

    # ── GDrive / rclone ───────────────────────────────────────────────────
    EnvVar("CHATGPTREST_GDRIVE_MOUNT_DIR", EnvType.STRING, "/vol1/1000/gdrive",
           "Local GDrive mount point", "gdrive"),
    EnvVar("CHATGPTREST_GDRIVE_UPLOAD_SUBDIR", EnvType.STRING, "chatgptrest_uploads",
           "Subdirectory in GDrive for uploads", "gdrive"),
    EnvVar("CHATGPTREST_GDRIVE_RCLONE_REMOTE", EnvType.STRING, "gdrive",
           "rclone remote name for GDrive ops", "gdrive"),
    EnvVar("CHATGPTREST_GDRIVE_MAX_FILE_BYTES", EnvType.INT, 200 * 1024 * 1024,
           "Max file size for GDrive uploads", "gdrive", min_value=0),
    EnvVar("CHATGPTREST_GDRIVE_CLEANUP_MODE", EnvType.STRING, "never",
           "GDrive file cleanup mode: never|on_success|always", "gdrive"),
    EnvVar("CHATGPTREST_GDRIVE_RETRY_SECONDS", EnvType.INT, 0,
           "GDrive retry interval", "gdrive", min_value=0),
    EnvVar("CHATGPTREST_GDRIVE_SYNC_TIMEOUT_SECONDS", EnvType.INT, 0,
           "GDrive sync timeout", "gdrive", min_value=0),
    EnvVar("CHATGPTREST_RCLONE_BIN", EnvType.STRING, "",
           "Path to rclone binary", "rclone"),
    EnvVar("CHATGPTREST_RCLONE_CONFIG", EnvType.STRING, "",
           "Path to rclone config file", "rclone"),
    EnvVar("CHATGPTREST_RCLONE_TIMEOUT_SECONDS", EnvType.FLOAT, 20.0,
           "rclone command timeout", "rclone", min_value=5.0, max_value=120.0),
    EnvVar("CHATGPTREST_RCLONE_COPYTO_TIMEOUT_SECONDS", EnvType.FLOAT, 180.0,
           "rclone copyto timeout", "rclone", min_value=10.0, max_value=600.0),
    EnvVar("CHATGPTREST_RCLONE_DELETE_TIMEOUT_SECONDS", EnvType.FLOAT, 30.0,
           "rclone delete timeout", "rclone", min_value=5.0, max_value=300.0),
    EnvVar("CHATGPTREST_RCLONE_CONTIMEOUT_SECONDS", EnvType.FLOAT, 10.0,
           "rclone connect timeout", "rclone", min_value=1.0, max_value=120.0),
    EnvVar("CHATGPTREST_RCLONE_IO_TIMEOUT_SECONDS", EnvType.FLOAT, 30.0,
           "rclone I/O timeout", "rclone", min_value=5.0, max_value=600.0),
    EnvVar("CHATGPTREST_RCLONE_RETRIES", EnvType.INT, 1,
           "rclone retry count", "rclone", min_value=0, max_value=10),
    EnvVar("CHATGPTREST_RCLONE_LOW_LEVEL_RETRIES", EnvType.INT, 1,
           "rclone low-level retry count", "rclone", min_value=0, max_value=10),
    EnvVar("CHATGPTREST_RCLONE_RETRIES_SLEEP_SECONDS", EnvType.FLOAT, 0.0,
           "rclone retry sleep", "rclone", min_value=0.0, max_value=30.0),
    EnvVar("CHATGPTREST_RCLONE_PROXY", EnvType.STRING, "",
           "Explicit HTTP proxy for rclone", "rclone", sensitive=True),

    # ── retryable send ────────────────────────────────────────────────────
    EnvVar("CHATGPTREST_RETRYABLE_SEND_EXTEND_MAX_ATTEMPTS", EnvType.BOOL, True,
           "Auto-extend max_attempts on retryable send failures", "core"),
    EnvVar("CHATGPTREST_RETRYABLE_SEND_ATTEMPTS_CAP", EnvType.INT, 20,
           "Hard cap on retryable send attempt count", "core", min_value=1),
    EnvVar("CHATGPTREST_RETRYABLE_SEND_MAX_EXTENSIONS", EnvType.INT, 3,
           "Max times max_attempts can be extended", "core", min_value=0),

    # ── conversation export ───────────────────────────────────────────────
    EnvVar("CHATGPTREST_SAVE_CONVERSATION_EXPORT", EnvType.BOOL, True,
           "Save conversation export after completion", "core"),
    EnvVar("CHATGPTREST_EXPORT_MISSING_REPLY_RETRIES", EnvType.INT, 0,
           "Retry count for missing reply in exports", "core", min_value=0),
    EnvVar("CHATGPTREST_EXPORT_MISSING_REPLY_RETRY_SLEEP_SECONDS", EnvType.INT, 0,
           "Sleep between missing-reply export retries", "core", min_value=0),
    EnvVar("CHATGPTREST_EXPAND_ZIP_ATTACHMENTS", EnvType.BOOL, False,
           "Auto-expand ZIP attachments in conversation export", "core"),
    EnvVar("CHATGPTREST_CONVERSATION_EXPORT_OK_COOLDOWN_SECONDS", EnvType.INT, 120,
           "Cooldown after successful export", "core", min_value=0),
    EnvVar("CHATGPTREST_CONVERSATION_EXPORT_FAIL_BACKOFF_BASE_SECONDS", EnvType.INT, 60,
           "Base backoff after export failure", "core", min_value=1),
    EnvVar("CHATGPTREST_CONVERSATION_EXPORT_FAIL_BACKOFF_MAX_SECONDS", EnvType.INT, 600,
           "Max backoff after export failure", "core", min_value=60),
    EnvVar("CHATGPTREST_CONVERSATION_EXPORT_GLOBAL_MIN_INTERVAL_SECONDS", EnvType.INT, 30,
           "Global minimum interval between exports", "core", min_value=0),
    EnvVar("CHATGPTREST_CONVERSATION_EXPORT_FORCE_MAX_WAIT_SECONDS", EnvType.INT, 5,
           "Force wait cap for export", "core", min_value=0, max_value=30),

    # ── worker ────────────────────────────────────────────────────────────
    EnvVar("CHATGPTREST_WORKER_ROLE", EnvType.STRING, "",
           "Worker role identifier", "core"),
    EnvVar("CHATGPTREST_WORKER_KIND_PREFIX", EnvType.STRING, "",
           "Kind prefix filter for worker claim", "core"),
    EnvVar("CHATGPTREST_WORKER_FATAL_DB_ACTION", EnvType.STRING, "",
           "Action on fatal DB errors: exit | ignore", "core"),
    EnvVar("CHATGPTREST_WORKER_FATAL_DB_BACKOFF_SECONDS", EnvType.INT, 30,
           "Backoff after fatal DB error", "core", min_value=5),
    EnvVar("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX", EnvType.BOOL, False,
           "Enable worker auto-triggering of Codex autofix", "core"),
    EnvVar("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_APPLY_ACTIONS", EnvType.BOOL, True,
           "Allow Codex autofix to apply actions automatically", "core"),
    EnvVar("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_MAX_RISK", EnvType.STRING, "",
           "Max risk level for auto Codex autofix", "core"),
    EnvVar("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_MODEL", EnvType.STRING, "",
           "Model override for worker Codex autofix", "core"),
    EnvVar("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_WINDOW_SECONDS", EnvType.INT, 1800,
           "Window for auto-codex autofix rate limit", "core", min_value=60),
    EnvVar("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_MIN_INTERVAL_SECONDS", EnvType.INT, 300,
           "Min interval between auto-codex autofix runs", "core", min_value=0),
    EnvVar("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_TIMEOUT_SECONDS", EnvType.INT, 600,
           "Timeout for auto-codex autofix run", "core", min_value=30),
    EnvVar("CHATGPTREST_WORK_CYCLE_SECONDS", EnvType.INT, 7200,
           "Worker maintenance cycle interval", "core", min_value=0),
    EnvVar("CHATGPTREST_WORK_SLEEP_MIN_SECONDS", EnvType.INT, 900,
           "Minimum worker sleep between cycles", "core", min_value=0),
    EnvVar("CHATGPTREST_WORK_SLEEP_MAX_SECONDS", EnvType.INT, 1800,
           "Maximum worker sleep between cycles", "core", min_value=0),
    EnvVar("CHATGPTREST_WAIT_NO_PROGRESS_GUARD", EnvType.BOOL, True,
           "Enable wait-phase no-progress guard", "core"),
    EnvVar("CHATGPTREST_WAIT_NO_PROGRESS_STATUS", EnvType.STRING, "",
           "Status to set on no-progress timeout", "core"),
    EnvVar("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", EnvType.INT, 7200,
           "No-progress guard timeout", "core", min_value=60),
    EnvVar("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", EnvType.INT, 21600,
           "No-progress guard timeout for deep research jobs", "core", min_value=60),
    EnvVar("CHATGPTREST_WAIT_NO_PROGRESS_RETRY_AFTER_SECONDS", EnvType.INT, 600,
           "Retry delay after no-progress guard fires", "core", min_value=10),
    EnvVar("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", EnvType.INT, 1800,
           "Timeout for no thread URL during wait phase", "core", min_value=60),
    EnvVar("CHATGPTREST_INFRA_RETRY_AFTER_SECONDS", EnvType.INT, 120,
           "Retry delay for infrastructure errors", "core", min_value=5),
    EnvVar("CHATGPTREST_UI_RETRY_AFTER_SECONDS", EnvType.INT, 30,
           "Retry delay for UI errors", "core", min_value=5),
    EnvVar("CHATGPTREST_WAIT_INFRA_RETRY_AFTER_SECONDS", EnvType.INT, 20,
           "Retry delay for wait-phase infra errors", "core", min_value=5),
    EnvVar("CHATGPTREST_WAIT_UI_RETRY_AFTER_SECONDS", EnvType.INT, 12,
           "Retry delay for wait-phase UI errors", "core", min_value=5),
    EnvVar("CHATGPTREST_RESCUE_FOLLOWUP_GUARD", EnvType.BOOL, True,
           "Enable rescue followup guard", "core"),
    EnvVar("CHATGPTREST_RESCUE_FOLLOWUP_GRACE_SECONDS", EnvType.INT, 3,
           "Grace period for rescue followup", "core", min_value=0),
    EnvVar("CHATGPTREST_DB_WRITE_AUTOFIX", EnvType.BOOL, False,
           "Auto-fix DB write errors", "core"),
    EnvVar("CHATGPTREST_DEBUG_ARTIFACTS_MAX_PER_JOB", EnvType.INT, 0,
           "Max debug artifacts per job (0 = unlimited)", "core", min_value=0),
    EnvVar("CHATGPTREST_DEBUG_ARTIFACTS_MIN_INTERVAL_SECONDS", EnvType.INT, 0,
           "Min interval between debug artifact captures", "core", min_value=0),
    # ZIP bundle limits
    EnvVar("CHATGPTREST_ZIP_EXPAND_MAX_MEMBERS", EnvType.INT, 600,
           "Max members to expand in ZIP bundles", "core", min_value=1),
    EnvVar("CHATGPTREST_ZIP_BUNDLE_MAX_FILES", EnvType.INT, 250,
           "Max files in a ZIP bundle", "core", min_value=1),
    EnvVar("CHATGPTREST_ZIP_BUNDLE_PER_FILE_MAX_BYTES", EnvType.INT, 200_000,
           "Max bytes per file in ZIP bundle", "core", min_value=8_000),
    EnvVar("CHATGPTREST_ZIP_BUNDLE_MAX_BYTES", EnvType.INT, 5_000_000,
           "Max total bytes for ZIP bundle", "core", min_value=50_000),

    # ── MCP server (chatgpt_web_mcp) ──────────────────────────────────────
    EnvVar("CHATGPTREST_BLOCKED_STATE_FILE", EnvType.STRING, "",
           "Path to blocked state file", "mcp"),
    EnvVar("CHATGPTREST_MCP_PROBE_HOST", EnvType.STRING, "",
           "MCP probe host for health checks", "mcp"),
    EnvVar("CHATGPTREST_MCP_PROBE_PORT", EnvType.INT, 0,
           "MCP probe port", "mcp"),
    EnvVar("CHATGPTREST_MCP_PROBE_TIMEOUT_SECONDS", EnvType.INT, 0,
           "MCP probe timeout", "mcp", min_value=0),
    EnvVar("CHATGPTREST_MCP_PERSIST_RATE_LIMITS", EnvType.BOOL, False,
           "Persist MCP rate limit state to disk", "mcp"),
    EnvVar("CHATGPTREST_MCP_BACKGROUND_WAIT_RETENTION_SECONDS", EnvType.INT, 0,
           "Background wait result retention", "mcp", min_value=0),
    EnvVar("CHATGPTREST_MCP_WAIT_AUTO_BACKGROUND", EnvType.BOOL, False,
           "Auto-background long wait operations", "mcp"),
    EnvVar("CHATGPTREST_MCP_WAIT_AUTO_BACKGROUND_THRESHOLD_SECONDS", EnvType.INT, 0,
           "Threshold to auto-background waits", "mcp", min_value=0),
    EnvVar("CHATGPTREST_MCP_WAIT_BACKGROUND_AUTO_RESUME", EnvType.BOOL, False,
           "Auto-resume backgrounded waits", "mcp"),
    EnvVar("CHATGPTREST_MCP_WAIT_BACKGROUND_AUTO_RESUME_TIMEOUT_SECONDS", EnvType.INT, 0,
           "Auto-resume timeout", "mcp", min_value=0),
    EnvVar("CHATGPTREST_MCP_WAIT_MAX_FOREGROUND_SECONDS", EnvType.INT, 0,
           "Max foreground wait before backgrounding", "mcp", min_value=0),
    EnvVar("CHATGPTREST_MCP_WAIT_FOREGROUND_ENABLED", EnvType.BOOL, True,
           "Enable foreground wait mode", "mcp"),
    EnvVar("CHATGPTREST_DISABLE_FOREGROUND_WAIT", EnvType.BOOL, False,
           "Disable foreground wait globally", "mcp"),
    EnvVar("CHATGPTREST_MCP_AUTO_START_API", EnvType.BOOL, False,
           "Auto-start API from MCP server", "mcp"),
    EnvVar("CHATGPTREST_MCP_AUTO_START_API_MIN_INTERVAL_SECONDS", EnvType.INT, 0,
           "Min interval between API auto-starts", "mcp", min_value=0),
    EnvVar("CHATGPTREST_API_AUTOSTART_EVERY_SECONDS", EnvType.INT, 0,
           "API auto-start check interval", "mcp", min_value=0),
    EnvVar("CHATGPTREST_API_AUTOSTART_MIN_INTERVAL_SECONDS", EnvType.INT, 0,
           "Min interval between auto-starts", "mcp", min_value=0),

    # ── maint daemon ──────────────────────────────────────────────────────
    EnvVar("CHATGPTREST_AUTO_PAUSE_DEFAULT_SECONDS", EnvType.INT, 0,
           "Default auto-pause duration", "maint", min_value=0),
    EnvVar("CHATGPTREST_AUTO_PAUSE_MODE", EnvType.STRING, "",
           "Auto-pause mode: send | all", "maint"),
    EnvVar("CHATGPTREST_INCIDENT_AUTO_RESOLVE_AFTER_HOURS", EnvType.INT, 0,
           "Auto-resolve incidents after N hours", "maint", min_value=0),
    EnvVar("CHATGPTREST_INCIDENT_AUTO_RESOLVE_EVERY_SECONDS", EnvType.INT, 0,
           "Check interval for auto-resolve", "maint", min_value=0),
    EnvVar("CHATGPTREST_INCIDENT_AUTO_RESOLVE_MAX_PER_RUN", EnvType.INT, 0,
           "Max incidents to auto-resolve per run", "maint", min_value=0),
    EnvVar("CHATGPTREST_INCIDENT_MAX_JOB_IDS", EnvType.INT, 0,
           "Max job IDs to track per incident", "maint", min_value=0),

    # ── UI canary ─────────────────────────────────────────────────────────
    EnvVar("CHATGPTREST_ENABLE_UI_CANARY", EnvType.BOOL, False,
           "Enable UI canary probes", "maint"),
    EnvVar("CHATGPTREST_UI_CANARY_PROVIDERS", EnvType.STRING, "",
           "CSV of providers for UI canary (default: all)", "maint"),
    EnvVar("CHATGPTREST_UI_CANARY_EVERY_SECONDS", EnvType.INT, 0,
           "UI canary probe interval", "maint", min_value=0),
    EnvVar("CHATGPTREST_UI_CANARY_TIMEOUT_SECONDS", EnvType.INT, 0,
           "UI canary probe timeout", "maint", min_value=0),
    EnvVar("CHATGPTREST_UI_CANARY_FAIL_THRESHOLD", EnvType.INT, 0,
           "Consecutive failures before incident", "maint", min_value=0),
    EnvVar("CHATGPTREST_UI_CANARY_INCIDENT_SEVERITY", EnvType.STRING, "",
           "Incident severity for canary failures", "maint"),
    EnvVar("CHATGPTREST_UI_CANARY_CAPTURE_COOLDOWN_SECONDS", EnvType.INT, 0,
           "Cooldown between canary capture attempts", "maint", min_value=0),
    EnvVar("CHATGPTREST_UI_CANARY_CAPTURE_TIMEOUT_SECONDS", EnvType.INT, 0,
           "Timeout for canary capture", "maint", min_value=0),

    # ── repair / Codex ────────────────────────────────────────────────────
    EnvVar("CHATGPTREST_MCP_AUTO_REPAIR_CHECK_MAX_PER_WINDOW", EnvType.INT, 0,
           "Max repair check jobs per window", "repair", min_value=0),
    EnvVar("CHATGPTREST_MCP_AUTO_REPAIR_CHECK_WINDOW_SECONDS", EnvType.INT, 0,
           "Repair check window duration", "repair", min_value=0),
    EnvVar("CHATGPTREST_MCP_AUTO_AUTOFIX_MAX_PER_WINDOW", EnvType.INT, 0,
           "Max autofix jobs per window", "repair", min_value=0),
    EnvVar("CHATGPTREST_MCP_AUTO_AUTOFIX_MIN_INTERVAL_SECONDS", EnvType.INT, 0,
           "Min interval between autofix jobs", "repair", min_value=0),
    EnvVar("CHATGPTREST_MCP_AUTO_AUTOFIX_WINDOW_SECONDS", EnvType.INT, 0,
           "Autofix window duration", "repair", min_value=0),
    EnvVar("CHATGPTREST_CODEX_BIN", EnvType.STRING, "",
           "Path to codex binary", "repair"),
    EnvVar("CHATGPTREST_CODEX_AUTOFIX_CODEX_TIMEOUT_SECONDS", EnvType.INT, 0,
           "Codex process timeout for autofix", "repair", min_value=0),
    EnvVar("CHATGPTREST_CODEX_AUTOFIX_DISABLE_FEATURES", EnvType.STRING, "",
           "CSV of features to disable in codex autofix", "repair"),
    EnvVar("CHATGPTREST_CODEX_AUTOFIX_MODEL_DEFAULT", EnvType.STRING, "gpt-5.3-codex-spark",
           "Default model for repair.autofix when caller does not specify one", "repair"),
    EnvVar("CHATGPTREST_CODEX_AUTOFIX_MAX_RISK_DEFAULT", EnvType.STRING, "",
           "Default max risk for codex autofix", "repair"),
    EnvVar("CHATGPTREST_CODEX_AUTOFIX_REASONING_EFFORT", EnvType.STRING, "",
           "Reasoning effort for codex autofix", "repair"),
    EnvVar("CHATGPTREST_CODEX_AUTOFIX_ENABLE_MAINT_FALLBACK", EnvType.BOOL, False,
           "Enable maint daemon fallback for autofix", "repair"),
    EnvVar("CHATGPTREST_CODEX_AUTOFIX_FALLBACK_REASONING_EFFORT", EnvType.STRING, "",
           "Reasoning effort for fallback autofix", "repair"),
    EnvVar("CHATGPTREST_CODEX_AUTOFIX_FALLBACK_TIMEOUT_SECONDS", EnvType.INT, 0,
           "Timeout for fallback autofix", "repair", min_value=0),

    # ── Codex global memory ───────────────────────────────────────────────
    EnvVar("CHATGPTREST_ENABLE_CODEX_GLOBAL_MEMORY", EnvType.BOOL, False,
           "Enable Codex global memory feature", "repair"),
    EnvVar("CHATGPTREST_CODEX_GLOBAL_MEMORY_JSONL", EnvType.STRING, "",
           "Path to global memory JSONL file", "repair"),
    EnvVar("CHATGPTREST_CODEX_GLOBAL_MEMORY_MD", EnvType.STRING, "",
           "Path to global memory markdown file", "repair"),
    EnvVar("CHATGPTREST_CODEX_GLOBAL_MEMORY_MAX_BYTES", EnvType.INT, 0,
           "Max bytes for global memory file", "repair", min_value=0),
    EnvVar("CHATGPTREST_CODEX_GLOBAL_MEMORY_DIGEST_MAX_RECORDS", EnvType.INT, 0,
           "Max records for memory digest", "repair", min_value=0),
    EnvVar("CHATGPTREST_CODEX_GLOBAL_MEMORY_PROMPT_MAX_CHARS", EnvType.INT, 0,
           "Max chars for memory prompt", "repair", min_value=0),
    EnvVar("CHATGPTREST_MAINT_BOOTSTRAP_MEMORY_PACKET", EnvType.STRING, "",
           "Optional path to maintagent bootstrap memory packet JSON", "repair"),
    EnvVar("CHATGPTREST_MAINT_BOOTSTRAP_MEMORY_STALE_HOURS", EnvType.INT, 168,
           "Hours before maintagent bootstrap memory is marked stale", "repair", min_value=1),

    # ── Codex maint fallback ──────────────────────────────────────────────
    EnvVar("CHATGPTREST_ENABLE_CODEX_MAINT_FALLBACK", EnvType.BOOL, False,
           "Enable Codex maint fallback", "repair"),
    EnvVar("CHATGPTREST_CODEX_MAINT_FALLBACK_ALLOW_ACTIONS", EnvType.STRING, "",
           "CSV of allowed maint fallback actions", "repair"),
    EnvVar("CHATGPTREST_CODEX_MAINT_FALLBACK_MAX_PER_INCIDENT", EnvType.INT, 0,
           "Max fallback attempts per incident", "repair", min_value=0),
    EnvVar("CHATGPTREST_CODEX_MAINT_FALLBACK_MAX_PER_WINDOW", EnvType.INT, 0,
           "Max fallback attempts per window", "repair", min_value=0),
    EnvVar("CHATGPTREST_CODEX_MAINT_FALLBACK_MAX_RISK", EnvType.STRING, "",
           "Max risk for maint fallback", "repair"),
    EnvVar("CHATGPTREST_CODEX_MAINT_FALLBACK_TIMEOUT_SECONDS", EnvType.INT, 0,
           "Timeout for maint fallback", "repair", min_value=0),
    EnvVar("CHATGPTREST_CODEX_MAINT_FALLBACK_WINDOW_SECONDS", EnvType.INT, 0,
           "Window duration for maint fallback rate limit", "repair", min_value=0),
    EnvVar("CHATGPTREST_ENABLE_INFRA_HEALER", EnvType.BOOL, False,
           "Enable infrastructure self-healer", "repair"),

    # ── issues registry ───────────────────────────────────────────────────
    EnvVar("CHATGPTREST_ISSUE_AUTOREPORT_ENABLED", EnvType.BOOL, True,
           "Auto-report issues to incident tracking", "core"),
    EnvVar("CHATGPTREST_ISSUE_AUTOREPORT_STATUSES", EnvType.STRING, "",
           "CSV of job statuses that trigger auto-report", "core"),
    EnvVar("CHATGPTREST_ISSUE_DEFAULT_PROJECT", EnvType.STRING, "",
           "Default project for auto-reported issues", "core"),
    EnvVar("CHATGPTREST_ISSUE_REPORT_REQUIRE_ACTIVE_JOB", EnvType.BOOL, False,
           "Require active job for issue reporting", "core"),
    EnvVar("CHATGPTREST_ENABLE_ISSUES_REGISTRY_WATCH", EnvType.BOOL, False,
           "Enable issues registry file watch", "core"),
    EnvVar("CHATGPTREST_ISSUES_REGISTRY_PATH", EnvType.STRING, "",
           "Path to issues registry file", "core"),
    EnvVar("CHATGPTREST_ISSUES_REGISTRY_PROBE_EVERY_SECONDS", EnvType.INT, 0,
           "Issues registry probe interval", "core", min_value=0),
    EnvVar("CHATGPTREST_ISSUES_REGISTRY_SYNC_MAX_PER_LOOP", EnvType.INT, 0,
           "Max issues to sync per loop", "core", min_value=0),

    # ── advisor ───────────────────────────────────────────────────────────
    EnvVar("CHATGPTREST_ADVISOR_STATE_ROOT", EnvType.STRING, "",
           "Root directory for advisor state files", "core"),

    # ── Google Workspace ─────────────────────────────────────────────────
    EnvVar("OPENMIND_GOOGLE_CREDENTIALS_PATH", EnvType.STRING,
           "~/.openmind/google_credentials.json",
           "OAuth 2.0 credentials.json path", "google", sensitive=True),
    EnvVar("OPENMIND_GOOGLE_TOKEN_PATH", EnvType.STRING,
           "~/.openmind/google_token.json",
           "Cached OAuth token path", "google", sensitive=True),
    EnvVar("OPENMIND_GMAIL_DESTINATION", EnvType.STRING, "", "Target email address for AI-generated reports", "google"),
    EnvVar("OPENMIND_EVOMAP_SHEET_ID", EnvType.STRING, "", "Google Spreadsheet ID for EvoMap daily analytics dashboard", "google"),
    EnvVar("OPENMIND_GOOGLE_SERVICES", EnvType.STRING, "",
           "CSV of enabled services (drive,calendar,sheets,docs,gmail,tasks); empty=all",
           "google"),

    # ── Obsidian Integration ──────────────────────────────────────────────
    EnvVar("OPENMIND_OBSIDIAN_API_URL", EnvType.STRING, "https://127.0.0.1:27124", "Obsidian Local REST API URL", "obsidian"),
    EnvVar("OPENMIND_OBSIDIAN_API_KEY", EnvType.STRING, "", "Obsidian Local REST API Bearer Token", "obsidian", sensitive=True),
    EnvVar("OPENMIND_OBSIDIAN_VAULT_PATH", EnvType.STRING, "", "Local vault path for filesystem mode (bypasses REST API)", "obsidian"),
    EnvVar("OPENMIND_OBSIDIAN_SYNC_FOLDERS", EnvType.STRING, "", "Comma-separated folders to sync (empty=all)", "obsidian"),
    EnvVar("OPENMIND_OBSIDIAN_SYNC_TAGS", EnvType.STRING, "", "Comma-separated tags to filter by (empty=no filter)", "obsidian"),
)


# ---------------------------------------------------------------------------
# Lookup index
# ---------------------------------------------------------------------------

_BY_NAME: dict[str, EnvVar] = {v.name: v for v in REGISTRY}


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------

def get_str(name: str) -> str:
    """Return string value, falling back to spec default or empty string."""
    spec = _BY_NAME.get(name)
    raw = os.environ.get(name)
    if raw is not None and raw.strip():
        return raw.strip()
    if spec is not None:
        return str(spec.default)
    return ""


def get_int(name: str) -> int:
    """Return int value with optional min/max clamping."""
    spec = _BY_NAME.get(name)
    default = int(spec.default) if spec else 0
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        val = int(raw)
    except (ValueError, TypeError):
        return default
    if spec and spec.min_value is not None:
        val = max(int(spec.min_value), val)
    if spec and spec.max_value is not None:
        val = min(int(spec.max_value), val)
    return val


def get_bool(name: str) -> bool:
    """Match existing ``_truthy_env()`` behaviour: unrecognised → spec default."""
    spec = _BY_NAME.get(name)
    default = bool(spec.default) if spec else False
    raw = os.environ.get(name)
    if raw is None:
        return default
    raw = raw.strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default  # unrecognised → spec default, NOT False


def get_float(name: str) -> float:
    """Return float value with optional min/max clamping."""
    spec = _BY_NAME.get(name)
    default = float(spec.default) if spec else 0.0
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        val = float(raw)
    except (ValueError, TypeError):
        return default
    if spec and spec.min_value is not None:
        val = max(float(spec.min_value), val)
    if spec and spec.max_value is not None:
        val = min(float(spec.max_value), val)
    return val


def coerce_int(value: Any, default: int) -> int:
    """Coerce arbitrary value to int, returning *default* on failure."""
    try:
        return int(value)
    except Exception:
        return int(default)


def truthy_env(name: str, default: bool) -> bool:
    """Standalone bool env lookup — does NOT require registry entry.

    This is the canonical version of the ``_truthy_env`` helper that was
    previously copy-pasted across ``mcp/server.py``, ``routes_jobs.py``,
    ``routes_issues.py``, and ``write_guards.py``.
    """
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    raw = raw.strip().lower()
    if not raw:
        return bool(default)
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


# ---------------------------------------------------------------------------
# Dump (for /ops/config)
# ---------------------------------------------------------------------------

def dump_all() -> dict[str, dict]:
    """Produce a redacted snapshot of all registered env vars.

    Redaction priority (fail-safe):
      1. ``_NON_SENSITIVE_ALLOWLIST`` → never redacted
      2. ``spec.sensitive`` OR ``_is_sensitive_name()`` → redacted
      3. Unregistered env vars are excluded entirely
    """
    result: dict[str, dict] = {}
    for spec in REGISTRY:
        current_raw = os.environ.get(spec.name)

        # Compute effective value using the typed accessor
        effective: Any
        if spec.type == EnvType.STRING:
            effective = get_str(spec.name)
        elif spec.type == EnvType.INT:
            effective = get_int(spec.name)
        elif spec.type == EnvType.FLOAT:
            effective = get_float(spec.name)
        elif spec.type == EnvType.BOOL:
            effective = get_bool(spec.name)
        else:
            effective = get_str(spec.name)

        is_sensitive = _effective_sensitive(spec)

        if is_sensitive:
            current_display = "***" if current_raw else None
            effective_display = "***" if effective else None
            default_display: Any = "***"
        else:
            current_display = current_raw
            effective_display = effective
            default_display = spec.default

        result[spec.name] = {
            "type": spec.type.value,
            "default": default_display,
            "current": current_display,
            "effective": effective_display,
            "description": spec.description,
            "category": spec.category,
            "sensitive": is_sensitive,
        }
    return result
