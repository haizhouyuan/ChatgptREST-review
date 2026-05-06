from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str) -> str:
    raw = os.environ.get(name)
    return raw.strip() if raw is not None and raw.strip() else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return int(default)
    raw = raw.strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return float(default)
    raw = raw.strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


@dataclass(frozen=True)
class AppConfig:
    db_path: Path
    artifacts_dir: Path
    preview_chars: int
    lease_ttl_seconds: int
    max_attempts: int
    chatgpt_mcp_url: str
    driver_mode: str
    driver_url: str
    min_prompt_interval_seconds: int
    gemini_min_prompt_interval_seconds: int
    qwen_min_prompt_interval_seconds: int
    chatgpt_max_prompts_per_hour: int
    chatgpt_max_prompts_per_day: int
    wait_slice_seconds: int
    wait_slice_growth_factor: float
    pro_fallback_presets: tuple[str, ...]
    api_token: str | None
    ops_token: str | None


def load_config() -> AppConfig:
    db_path = Path(_env("CHATGPTREST_DB_PATH", "state/jobdb.sqlite3")).expanduser()
    artifacts_dir = Path(_env("CHATGPTREST_ARTIFACTS_DIR", "artifacts")).expanduser()
    preview_chars = _env_int("CHATGPTREST_PREVIEW_CHARS", 1200)
    lease_ttl_seconds = _env_int("CHATGPTREST_LEASE_TTL_SECONDS", 60)
    max_attempts = _env_int("CHATGPTREST_MAX_ATTEMPTS", 3)
    chatgpt_mcp_url = _env("CHATGPTREST_CHATGPT_MCP_URL", "http://127.0.0.1:18701/mcp")
    driver_mode = _env("CHATGPTREST_DRIVER_MODE", "external_mcp")
    driver_url = _env("CHATGPTREST_DRIVER_URL", chatgpt_mcp_url)
    min_prompt_interval_seconds = _env_int("CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS", 61)
    gemini_min_prompt_interval_seconds = _env_int("CHATGPTREST_GEMINI_MIN_PROMPT_INTERVAL_SECONDS", min_prompt_interval_seconds)
    qwen_min_prompt_interval_seconds = _env_int("CHATGPTREST_QWEN_MIN_PROMPT_INTERVAL_SECONDS", 0)
    chatgpt_max_prompts_per_hour = _env_int("CHATGPTREST_CHATGPT_MAX_PROMPTS_PER_HOUR", 0)
    chatgpt_max_prompts_per_day = _env_int("CHATGPTREST_CHATGPT_MAX_PROMPTS_PER_DAY", 0)
    wait_slice_seconds = _env_int("CHATGPTREST_WAIT_SLICE_SECONDS", 60)
    wait_slice_growth_factor = max(1.0, _env_float("CHATGPTREST_WAIT_SLICE_GROWTH_FACTOR", 1.0))
    pro_fallback_raw = _env("CHATGPTREST_PRO_FALLBACK_PRESETS", "thinking_heavy,auto")
    pro_fallback_presets = tuple([p.strip() for p in pro_fallback_raw.split(",") if p.strip()])
    api_token = os.environ.get("CHATGPTREST_API_TOKEN")
    api_token = api_token.strip() if api_token is not None and api_token.strip() else None
    ops_token = os.environ.get("CHATGPTREST_OPS_TOKEN")
    if ops_token is None:
        ops_token = os.environ.get("CHATGPTREST_ADMIN_TOKEN")
    ops_token = ops_token.strip() if ops_token is not None and ops_token.strip() else None
    return AppConfig(
        db_path=db_path,
        artifacts_dir=artifacts_dir,
        preview_chars=max(0, preview_chars),
        lease_ttl_seconds=max(5, lease_ttl_seconds),
        max_attempts=max(1, max_attempts),
        chatgpt_mcp_url=chatgpt_mcp_url,
        driver_mode=driver_mode,
        driver_url=driver_url,
        min_prompt_interval_seconds=max(0, min_prompt_interval_seconds),
        gemini_min_prompt_interval_seconds=max(0, gemini_min_prompt_interval_seconds),
        qwen_min_prompt_interval_seconds=max(0, qwen_min_prompt_interval_seconds),
        chatgpt_max_prompts_per_hour=max(0, chatgpt_max_prompts_per_hour),
        chatgpt_max_prompts_per_day=max(0, chatgpt_max_prompts_per_day),
        wait_slice_seconds=(0 if wait_slice_seconds <= 0 else max(30, wait_slice_seconds)),
        wait_slice_growth_factor=wait_slice_growth_factor,
        pro_fallback_presets=pro_fallback_presets,
        api_token=api_token,
        ops_token=ops_token,
    )
