"""Legacy single-file implementation (kept for compatibility).

This module was moved into a package to enable incremental refactors without
breaking existing `python chatgpt_web_mcp_server.py ...` entrypoints.
"""

import argparse
import asyncio
import base64
import contextvars
import datetime
import hashlib
import html
import inspect
import json
import logging
import logging.handlers
import math
import os
import random
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid
import weakref
from contextlib import asynccontextmanager, contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import httpx
from mcp.server.fastmcp import Context
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

try:
    import fcntl  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - platform dependent
    fcntl = None

from chatgpt_web_mcp.config import ChatGPTWebConfig, _load_config
from chatgpt_web_mcp.env import _compile_env_regex, _env_float, _env_int, _env_int_range, _truthy_env


from chatgpt_web_mcp.locks import _acquire_server_singleton_lock_or_die, _flock_exclusive


from chatgpt_web_mcp.idempotency import _IdempotencyContext
from chatgpt_web_mcp.idempotency import _hash_request
from chatgpt_web_mcp.idempotency import _idempotency_begin, _idempotency_lookup, _idempotency_namespace, _idempotency_update
from chatgpt_web_mcp.idempotency import _normalize_idempotency_key, _result_has_full_answer_reference, _run_id


from chatgpt_web_mcp.proxy import _proxy_env_for_subprocess, _without_proxy_env



from chatgpt_web_mcp.runtime.util import _ctx_info, _coerce_error_text, _slugify
from chatgpt_web_mcp.runtime.locks import _ask_lock
from chatgpt_web_mcp.runtime.ratelimit import (
    _gemini_min_prompt_interval_seconds,
    _min_prompt_interval_seconds,
    _qwen_min_prompt_interval_seconds,
    _respect_prompt_interval,
)
from chatgpt_web_mcp.runtime.call_log import (
    _call_log_include_answers,
    _call_log_include_prompts,
    _call_log_path,
    _maybe_append_call_log,
)
from chatgpt_web_mcp.runtime.paths import (
    _debug_dir,
    _qwen_ui_snapshot_base_dir,
    _qwen_ui_snapshot_doc_path,
    _ui_snapshot_base_dir,
    _ui_snapshot_doc_path,
)

from chatgpt_web_mcp.runtime import concurrency as _concurrency
from chatgpt_web_mcp.runtime.concurrency import (
    _chatgpt_max_concurrent_pages,
    _gemini_max_concurrent_pages,
    _qwen_max_concurrent_pages,
    _chatgpt_page_semaphore,
    _gemini_page_semaphore,
    _qwen_page_semaphore,
    _normalize_web_kind,
    _page_slot,
    _is_tab_limit_error,
    _sema_in_use,
    _tab_limit_result,
)


from chatgpt_web_mcp.runtime.humanize import (
    _delay_range_ms,
    _random_log_enabled,
    _random_log,
    _human_pause,
    _type_delay_profile,
    _sample_key_delay_ms,
    _should_insert_think_pause,
    _sample_think_pause_ms,
    _type_delay_ms,
)

from chatgpt_web_mcp.runtime.answer_classification import (
    _classify_deep_research_answer,
    _classify_non_deep_research_answer,
    _deep_research_widget_failure_reason,
    _looks_like_transient_assistant_error,
)


from chatgpt_web_mcp.playwright.cdp import (
    _cdp_fallback_enabled,
    _ensure_local_cdp_chrome_running,
    _restart_local_cdp_chrome,
    _connect_over_cdp_resilient,
)


from chatgpt_web_mcp.playwright.navigation import (
    _navigation_timeout_ms,
    _prompt_action_timeout_ms,
    _goto_with_retry,
)

from chatgpt_web_mcp.playwright.evidence import (
    _capture_debug_artifacts,
    _ui_screenshot,
    _ui_screenshot_from_viewport,
    _ui_snapshot_link,
    _ui_snapshot_run_dir,
    _ui_write_snapshot_doc,
)

from chatgpt_web_mcp.playwright.input import _type_question
from chatgpt_web_mcp.playwright.io import _fetch_bytes_via_browser



def _retry_after_seconds_from_blocked_state(state: dict[str, Any] | None) -> int | None:
    if not isinstance(state, dict):
        return None
    until = state.get("blocked_until")
    try:
        blocked_until = float(until) if until is not None else 0.0
    except Exception:
        return None
    now = time.time()
    if blocked_until <= 0 or now >= blocked_until:
        return None
    # ceil
    remaining = int(blocked_until - now)
    return remaining if remaining > 0 else 1


def _blocked_status_from_state(state: dict[str, Any] | None) -> str:
    reason = str((state or {}).get("reason") or "").strip().lower()
    if reason in {"network", "unusual_activity", "verification_pending"}:
        return "cooldown"
    return "blocked"


@dataclass
class _BackgroundJob:
    key: tuple[str, str, str]  # (namespace, tool, idempotency_key)
    task: asyncio.Task[dict[str, Any]]
    created_at: float
    kind: str  # e.g. "send" | "resume_wait"


_ASK_JOBS: dict[tuple[str, str, str], _BackgroundJob] = {}
_ASK_JOBS_LOCK = asyncio.Lock()


async def _cleanup_job(job_key: tuple[str, str, str], task: asyncio.Task[dict[str, Any]]) -> None:
    async with _ASK_JOBS_LOCK:
        current = _ASK_JOBS.get(job_key)
        if current and current.task is task:
            _ASK_JOBS.pop(job_key, None)


async def _get_running_job(job_key: tuple[str, str, str]) -> _BackgroundJob | None:
    async with _ASK_JOBS_LOCK:
        job = _ASK_JOBS.get(job_key)
        if job and not job.task.done():
            return job
    return None


async def _get_or_start_job(
    job_key: tuple[str, str, str],
    *,
    kind: str,
    factory: Callable[[], Awaitable[dict[str, Any]]],
) -> _BackgroundJob:
    async with _ASK_JOBS_LOCK:
        existing = _ASK_JOBS.get(job_key)
        if existing and not existing.task.done():
            return existing
        if existing and existing.task.done():
            _ASK_JOBS.pop(job_key, None)

        task = asyncio.create_task(factory())
        job = _BackgroundJob(key=job_key, task=task, created_at=time.time(), kind=str(kind))
        _ASK_JOBS[job_key] = job

        def _on_done(done_task: asyncio.Task[dict[str, Any]]) -> None:
            try:
                asyncio.create_task(_cleanup_job(job_key, done_task))
            except Exception:
                return

        task.add_done_callback(_on_done)
        return job



# ── stealth / mouse (extracted to _stealth.py) ────────────────────────
from chatgpt_web_mcp._stealth import (  # noqa: E402, F401
    _CHATGPT_STEALTH_INIT_JS,
    _CHATGPT_DISABLE_ANSWER_NOW_INIT_JS,
    _MOUSE_POSITIONS,
    _apply_viewport_jitter,
    _bezier_point,
    _clamp_point,
    _human_click,
    _human_move_mouse,
    _human_move_to_locator,
    _install_stealth_init_script,
    _maybe_idle_interaction,
    _page_viewport_size,
    _viewport_jitter_px,
)






async def _open_plus_menu(page) -> Any:
    plus = page.locator(_CHATGPT_PLUS_BUTTON_SELECTOR).first
    await plus.click()
    await _human_pause(page)

    menus = page.locator("[role='menu']:visible")
    menu = menus.filter(has_text=re.compile(r"Add photos", re.I)).first
    if not await menu.count():
        menu = menus.filter(has_text=re.compile(r"Deep research", re.I)).first
    if not await menu.count():
        menu = menus.first
    await menu.wait_for(state="visible", timeout=10_000)
    return menu


async def _chatgpt_click_new_chat(page) -> bool:
    candidates = [
        "a:has-text('New chat')",
        "button:has-text('New chat')",
        "a:has-text('新对话')",
        "button:has-text('新对话')",
        "a:has-text('发起新对话')",
        "button:has-text('发起新对话')",
        "a[aria-label*='New chat']",
        "button[aria-label*='New chat']",
        "a[aria-label*='新对话']",
        "button[aria-label*='新对话']",
    ]
    for selector in candidates:
        locator = page.locator(selector).first
        try:
            if await locator.count() and await locator.is_visible():
                await locator.click()
                await _human_pause(page)
                return True
        except Exception:
            continue
    return False


def _composer_pills(page) -> Any:
    # ChatGPT Web A/B tests the composer "pill" UI.
    # - Older UI: `button.__composer-pill`
    # - Newer UI: regular buttons with `aria-haspopup='menu'` in the composer (e.g. "Extended thinking")
    #
    # Scope to the composer region to avoid matching message-level controls (notably the thinking panel's
    # "Answer now" affordance).
    return page.locator(
        "#thread-bottom button.__composer-pill, "
        "#thread-bottom button[aria-haspopup='menu'], "
        "form:has(#prompt-textarea) button[aria-haspopup='menu'], "
        "button.__composer-pill"
    )


def _deep_research_report_min_chars() -> int:
    raw = (os.environ.get("CHATGPT_DEEP_RESEARCH_REPORT_MIN_CHARS") or "").strip()
    if not raw:
        return 800
    try:
        return max(0, int(raw))
    except ValueError:
        return 800


def _deep_research_auto_followup_enabled() -> bool:
    # Default off: sending a prompt automatically is an active action; enable only after observation.
    return _truthy_env("CHATGPT_DEEP_RESEARCH_AUTO_FOLLOWUP", False)


def _deep_research_auto_followup_prompt(last_assistant_text: str) -> str:
    return (
        "OK\n\n"
        "请按我最初的提问直接开始深度调研并输出完整报告。"
        "若存在信息缺口，请做最小合理假设并在报告中明确标注（含不确定性和需我确认清单），不要再反问。"
    )





# ── netlog (extracted to _netlog.py) ───────────────────────────────────
from chatgpt_web_mcp._netlog import (  # noqa: E402, F401
    _chatgpt_install_netlog,
    _chatgpt_netlog_backup_count,
    _chatgpt_netlog_capture_model_route,
    _chatgpt_netlog_enabled,
    _chatgpt_netlog_extract_model_route_fields,
    _chatgpt_netlog_extract_model_route_fields_obj,
    _chatgpt_netlog_host_allowlist,
    _chatgpt_netlog_line_max_chars,
    _chatgpt_netlog_logger,
    _chatgpt_netlog_max_bytes,
    _chatgpt_netlog_path,
    _chatgpt_netlog_redact_ids,
    _chatgpt_netlog_redact_query,
    _chatgpt_netlog_redact_url,
    _chatgpt_netlog_resource_types,
    _chatgpt_netlog_sanitize_value,
    _chatgpt_netlog_write,
)



_CHATGPT_THOUGHT_FOR_RE = re.compile(
    r"thought\s*for\s*"
    r"(?:(?P<h>\d+)\s*h\s*)?"
    r"(?:(?P<m>\d+)\s*m\s*)?"
    r"(?:(?P<s>\d+)\s*s\s*)?",
    re.I,
)

_CHATGPT_THOUGHT_FOR_ZH_RE = re.compile(
    r"(?:思考(?:了|用时|时长)?|用时|耗时)\s*"
    r"(?:(?P<h>\d+)\s*(?:小时|h)\s*)?"
    r"(?:(?P<m>\d+)\s*(?:分钟|分|m)\s*)?"
    r"(?:(?P<s>\d+)\s*(?:秒钟|秒|s)\s*)?",
    re.I,
)


def _chatgpt_parse_thought_for_seconds(text: str) -> int | None:
    s = (text or "").strip()
    if not s:
        return None
    # Normalize mixed unit strings like "Thought for 10 秒" / "思考了 1m 20s" into a consistent unit set.
    # This keeps regex handling simple without broadening patterns too aggressively.
    s_norm = (
        s.replace("小时", "h")
        .replace("分钟", "m")
        .replace("分", "m")
        .replace("秒钟", "s")
        .replace("秒", "s")
    )
    m = _CHATGPT_THOUGHT_FOR_RE.search(s_norm) or _CHATGPT_THOUGHT_FOR_ZH_RE.search(s_norm)
    if not m:
        return None
    try:
        hours = int(m.group("h") or 0)
        minutes = int(m.group("m") or 0)
        seconds = int(m.group("s") or 0)
    except Exception:
        return None
    total = hours * 3600 + minutes * 60 + seconds
    return total if total > 0 else None


def _chatgpt_thought_guard_min_seconds() -> int:
    raw = (os.environ.get("CHATGPT_THOUGHT_GUARD_MIN_SECONDS") or "").strip()
    if not raw:
        return 300
    try:
        return max(0, int(raw))
    except Exception:
        return 300


_CHATGPT_THINKING_FOOTER_FIND_JS = r"""
() => {
  const patterns = [
    /reasoned\s*for/i,
    /reasoning/i,
    /pro\s+thinking/i,
    /thought\s*for/i,
    /thinking\s*time/i,
    /answer\s*now/i,
    /\bskipping\b/i,
    /(思考过程|推理过程)/,
    /(思考(?:了|用时|时长)?|用时|耗时)\s*\d/i,
    /跳过(?:思考|推理)/,
    /(立即回答|现在回答)/,
  ];
  const maxText = 25000;
  const maxLineLen = 140;

  const matches = (s) => {
    if (!s) return false;
    return patterns.some((re) => re.test(s));
  };

  const scan = (container) => {
    if (!container) return null;
    let text = "";
    try {
      text = String(container.innerText || container.textContent || "");
    } catch {
      text = "";
    }
    if (!text) return null;
    text = text.replace(/\r/g, "\n");
    // The footer tends to live near the bottom; avoid scanning huge pages.
    if (text.length > maxText) text = text.slice(-maxText);
    const lines = text
      .split("\n")
      .map((s) => String(s || "").trim())
      .filter(Boolean);
    const hits = [];
    const seen = new Set();
    for (let i = lines.length - 1; i >= 0 && hits.length < 8; i--) {
      const line = lines[i];
      if (!line) continue;
      if (line.length > maxLineLen) continue;
      if (!matches(line)) continue;
      if (seen.has(line)) continue;
      seen.add(line);
      hits.unshift(line);
    }
    return hits.length ? hits.join("\n") : null;
  };

  const collectUiText = (turn) => {
    if (!turn) return null;
    const hits = [];
    const seen = new Set();
    const add = (val) => {
      const s = String(val || "").replace(/\r/g, "\n").trim();
      if (!s) return;
      if (s.length > maxLineLen) return;
      if (!matches(s)) return;
      if (seen.has(s)) return;
      seen.add(s);
      hits.push(s);
    };

    const markdownSel = "div.markdown, div.prose, [data-testid='markdown'], div.qk-markdown";
    const candidates = Array.from(
      turn.querySelectorAll(
        "button, a, [role='button'], [role='link'], [aria-label], [title], [data-testid]"
      )
    );
    for (const el of candidates) {
      if (!(el instanceof Element)) continue;
      // Avoid matching user content inside the markdown answer body.
      if (el.closest(markdownSel)) continue;
      add(el.innerText);
      add(el.textContent);
      add(el.getAttribute("aria-label"));
      add(el.getAttribute("title"));
      add(el.getAttribute("data-tooltip"));
      const testid = el.getAttribute("data-testid");
      if (testid && matches(testid)) add(`data-testid:${testid}`);
    }
    return hits.length ? hits.slice(-8).join("\n") : null;
  };

  const assistants = Array.from(document.querySelectorAll("[data-message-author-role='assistant']"));
  const lastAssistant = assistants.length ? assistants[assistants.length - 1] : null;
  // Avoid scanning the whole document: reading `innerText` can trigger expensive reflow on huge threads.
  if (!lastAssistant) return null;
  const turn =
    lastAssistant.closest("article") ||
    lastAssistant.closest("[data-testid='conversation-turn']") ||
    lastAssistant;

  const uiHits = collectUiText(turn);
  if (uiHits) return { footer_text: uiHits, source: "ui" };

  const inner = scan(turn);
  return inner ? { footer_text: inner, source: "innerText" } : null;
};
"""


async def _chatgpt_best_effort_thinking_observation(page, *, ctx: Context | None) -> dict[str, Any] | None:
    """Extract a minimal, non-sensitive thinking footer summary (no chain-of-thought)."""
    footer = ""
    source = ""
    try:
        raw = await page.evaluate(_CHATGPT_THINKING_FOOTER_FIND_JS)
        if isinstance(raw, dict):
            footer = str(raw.get("footer_text") or "").strip()
            source = str(raw.get("source") or "").strip()
        else:
            footer = str(raw or "").strip()
    except Exception:
        footer = ""
    if not footer:
        return None

    # Guardrail: only treat a snippet as a "thinking footer" if it contains strong UI markers.
    # This avoids false positives when the assistant answer text itself contains words like “跳过”.
    if not re.search(
        r"reasoned\s*for|reasoning|pro\s+thinking|thought\s*for|thinking\s*time|answer\s*now|\bskipping\b|"
        r"(思考过程|推理过程)|(思考(?:了|用时|时长)?|用时|耗时)\s*\d|跳过(?:思考|推理)",
        footer,
        re.I,
    ):
        return None

    obs: dict[str, Any] = {"footer_text": footer}
    if source:
        obs["footer_source"] = source
    obs["skipping"] = bool(re.search(r"\bskipping\b|跳过(?:思考|推理)|已跳过(?:思考|推理)", footer, re.I))
    obs["answer_now_visible"] = bool(re.search(r"answer\s*now|(?:立即回答|现在回答)", footer, re.I))
    thought_seconds = _chatgpt_parse_thought_for_seconds(footer)
    obs["thought_for_present"] = bool(thought_seconds is not None)
    if thought_seconds is not None:
        obs["thought_for_present"] = True
        obs["thought_seconds"] = int(thought_seconds)
        min_seconds = int(_chatgpt_thought_guard_min_seconds())
        if min_seconds > 0:
            obs["thought_min_seconds"] = min_seconds
            obs["thought_too_short"] = bool(int(thought_seconds) < min_seconds)
    else:
        obs["thought_for_present"] = bool(
            re.search(
                r"thought\s*for|reasoned\s*for|(思考(?:了|用时|时长)?|用时|耗时)\s*\d",
                footer,
                re.I,
            )
        )

    try:
        clicks = await page.evaluate("() => window.__chatgptrest_answer_now_blocked_clicks || 0")
        last_ts = await page.evaluate("() => window.__chatgptrest_answer_now_blocked_last_ts || 0")
        if isinstance(clicks, (int, float)):
            obs["answer_now_blocked_clicks"] = int(clicks)
        if isinstance(last_ts, (int, float)):
            obs["answer_now_blocked_last_ts_ms"] = int(last_ts)
    except Exception:
        pass

    return obs


# ── thinking-trace capture ──────────────────────────────────────────────
#
# ChatGPT Pro renders a chain of "thinking steps" inside each assistant turn.
# Each step is a clickable element that, when activated, opens a side panel
# containing the detailed reasoning text.  This JS + helper pair extracts
# the full chain without clicking (reading the DOM-embedded content) when
# possible, falling back to labels-only when the content is not in the DOM.

_CHATGPT_THINKING_TRACE_JS = r"""
() => {
  const MAX_STEP_CHARS = 16000;

  /* Locate the last assistant turn container. */
  const assistants = Array.from(
    document.querySelectorAll("[data-message-author-role='assistant']")
  );
  if (!assistants.length) return null;
  const lastMsg = assistants[assistants.length - 1];
  const turn =
    lastMsg.closest("article") ||
    lastMsg.closest("[data-testid='conversation-turn']") ||
    lastMsg;

  /* ── Strategy 1: look for thinking-step containers ─────────────────
   * ChatGPT Pro renders thinking steps as clickable regions with
   * `data-testid` attributes like "thinking-step-*" or aria patterns
   * indicating reasoning blocks.
   */
  const steps = [];
  const seen = new Set();

  /* Broad selector targeting known thinking-step UI patterns.
   * ChatGPT evolves its DOM frequently so we check multiple markers. */
  const stepCandidates = [
    ...turn.querySelectorAll('[class*="thought"], [class*="thinking"], [class*="reasoning"]'),
    ...turn.querySelectorAll('button[aria-expanded]'),
    ...turn.querySelectorAll('[data-testid*="thought"], [data-testid*="thinking"]'),
  ];

  /* Also look for the "Reasoned for X seconds" type labels anywhere in the turn
   * that are NOT inside the markdown answer body. */
  const allButtons = turn.querySelectorAll("button, [role='button']");
  const markdownSel = "div.markdown, div.prose, [data-testid='markdown']";
  for (const btn of allButtons) {
    if (btn.closest(markdownSel)) continue;
    const txt = (btn.innerText || btn.textContent || "").trim();
    if (!txt) continue;
    if (
      /reasoned?\s*(for|about)/i.test(txt) ||
      /thought\s*for/i.test(txt) ||
      /thinking/i.test(txt) ||
      /(思考|推理)(了|过程|用时)/i.test(txt)
    ) {
      stepCandidates.push(btn);
    }
  }

  for (const el of stepCandidates) {
    const label = (el.innerText || el.textContent || "").trim().slice(0, 200);
    if (!label || seen.has(label)) continue;
    seen.add(label);

    /* Try to find adjacent/child content that might hold the thinking text.
     * Some ChatGPT renderings embed the full reasoning as a hidden sibling.
     */
    let content = "";
    const parent = el.parentElement;
    if (parent) {
      /* Check next siblings for hidden reasoning panels. */
      let sib = el.nextElementSibling;
      for (let i = 0; i < 3 && sib; i++, sib = sib.nextElementSibling) {
        const sibText = (sib.innerText || sib.textContent || "").trim();
        if (sibText.length > 20 && sibText.length < MAX_STEP_CHARS) {
          /* Likely a thinking content panel. */
          content = sibText;
          break;
        }
      }
      /* Also check aria-controls targets and grandparent descendants. */
      const controlsId = el.getAttribute("aria-controls");
      if (!content && controlsId) {
        const panel = document.getElementById(controlsId);
        if (panel) {
          content = (panel.innerText || panel.textContent || "").trim().slice(0, MAX_STEP_CHARS);
        }
      }
    }

    steps.push({ label, content: content.slice(0, MAX_STEP_CHARS), has_content: !!content });
  }

  if (!steps.length) return null;

  return {
    provider: "chatgpt",
    steps,
    total_steps: steps.length,
    total_content_chars: steps.reduce((s, st) => s + st.content.length, 0),
  };
};
"""


async def _chatgpt_capture_thinking_trace(
    page,
    *,
    ctx: Context | None = None,
) -> dict[str, Any] | None:
    """Best-effort capture of ChatGPT Pro thinking trace from the DOM.

    Returns a structured dict with steps/labels/content, or None if no
    thinking trace is detectable.
    """
    if not _truthy_env("CHATGPT_CAPTURE_THINKING_TRACE", True):
        return None
    try:
        raw = await page.evaluate(_CHATGPT_THINKING_TRACE_JS)
        if not raw or not isinstance(raw, dict):
            return None
        steps = raw.get("steps") or []
        if not steps:
            return None
        # Annotate with capture timestamp
        raw["captured_at"] = time.time()
        return raw
    except Exception:
        return None









# ── answers (extracted to _answers.py) ─────────────────────────────────
from chatgpt_web_mcp._answers import (  # noqa: E402, F401
    _chatgpt_answer_dir,
    _chatgpt_build_export_conversation_object_from_dom_messages,
    _chatgpt_conversation_dir,
    _chatgpt_conversation_id_from_url,
    _chatgpt_max_return_answer_chars,
    _chatgpt_maybe_offload_answer_result,
    _chatgpt_write_answer_file,
    _chatgpt_write_conversation_export_file,
)

def _chatgpt_blocked_events_log_path() -> Path:
    raw = (os.environ.get("CHATGPT_BLOCKED_EVENTS_LOG") or "").strip()
    if raw:
        return Path(raw).expanduser()
    debug_dir = _debug_dir()
    if debug_dir is not None:
        return debug_dir / "monitor" / "chatgpt_blocked_events.jsonl"
    return Path("artifacts/monitor/chatgpt_blocked_events.jsonl")


def _maybe_append_blocked_event(event: dict[str, Any]) -> None:
    try:
        path = _chatgpt_blocked_events_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(event)
        payload.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
        payload.setdefault("pid", os.getpid())
        with path.open("a", encoding="utf-8") as f:
            if fcntl is not None:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                except Exception:
                    pass
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            f.flush()
            if fcntl is not None:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
    except Exception:
        return


def _chatgpt_global_rate_limit_file() -> Path | None:
    raw = (os.environ.get("CHATGPT_GLOBAL_RATE_LIMIT_FILE") or "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _chatgpt_global_lock_file() -> Path | None:
    raw = (os.environ.get("CHATGPT_GLOBAL_LOCK_FILE") or "").strip()
    if raw:
        return Path(raw).expanduser()
    rate_limit = _chatgpt_global_rate_limit_file()
    if rate_limit is None:
        return None
    return Path(str(rate_limit) + ".lock")


def _chatgpt_global_last_sent_at(rate_limit_file: Path) -> float:
    try:
        text = rate_limit_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return 0.0
    except Exception:
        return 0.0
    if not text:
        return 0.0
    try:
        data = json.loads(text)
    except Exception:
        return 0.0
    if not isinstance(data, dict):
        return 0.0
    value = data.get("last_sent_at")
    try:
        return float(value) if value is not None else 0.0
    except Exception:
        return 0.0


def _chatgpt_global_write_last_sent_at(rate_limit_file: Path, last_sent_at: float) -> None:
    try:
        rate_limit_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"last_sent_at": float(last_sent_at)}
        rate_limit_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        return


def _chatgpt_wait_refresh_state_file() -> Path | None:
    """
    Optional persisted state to prevent wait() refresh storms across repeated polling calls.

    This is intentionally separate from the global *prompt send* rate limit.
    """
    raw = (os.environ.get("CHATGPT_WAIT_REFRESH_STATE_FILE") or "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _chatgpt_wait_refresh_lock_file(state_file: Path) -> Path:
    raw = (os.environ.get("CHATGPT_WAIT_REFRESH_LOCK_FILE") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(str(state_file) + ".lock")


def _chatgpt_wait_refresh_min_interval_seconds() -> int:
    raw = (os.environ.get("CHATGPT_WAIT_REFRESH_MIN_INTERVAL_SECONDS") or "").strip()
    if not raw:
        return 900
    try:
        return max(0, int(raw))
    except Exception:
        return 900


def _chatgpt_wait_refresh_window_seconds() -> int:
    raw = (os.environ.get("CHATGPT_WAIT_REFRESH_WINDOW_SECONDS") or "").strip()
    if not raw:
        return 86400
    try:
        return max(1, int(raw))
    except Exception:
        return 86400


def _chatgpt_wait_refresh_max_per_window() -> int:
    raw = (os.environ.get("CHATGPT_WAIT_REFRESH_MAX_PER_WINDOW") or "").strip()
    if not raw:
        return 12
    try:
        return max(0, int(raw))
    except Exception:
        return 12


def _chatgpt_regenerate_state_file() -> Path | None:
    """
    Optional persisted state to prevent regenerate storms.

    Regenerate triggers a new assistant generation without sending a new user prompt.
    It is still a side-effectful UI action and should be rate-limited conservatively.
    """
    raw = (os.environ.get("CHATGPT_REGENERATE_STATE_FILE") or "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _chatgpt_regenerate_lock_file(state_file: Path) -> Path:
    raw = (os.environ.get("CHATGPT_REGENERATE_LOCK_FILE") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(str(state_file) + ".lock")


def _chatgpt_regenerate_min_interval_seconds() -> int:
    raw = (os.environ.get("CHATGPT_REGENERATE_MIN_INTERVAL_SECONDS") or "").strip()
    if not raw:
        return 1800
    try:
        return max(0, int(raw))
    except Exception:
        return 1800


def _chatgpt_regenerate_window_seconds() -> int:
    raw = (os.environ.get("CHATGPT_REGENERATE_WINDOW_SECONDS") or "").strip()
    if not raw:
        return 86400
    try:
        return max(1, int(raw))
    except Exception:
        return 86400


def _chatgpt_regenerate_max_per_window() -> int:
    raw = (os.environ.get("CHATGPT_REGENERATE_MAX_PER_WINDOW") or "").strip()
    if not raw:
        return 3
    try:
        return max(0, int(raw))
    except Exception:
        return 3


async def _chatgpt_regenerate_reserve(
    *,
    conversation_id: str | None,
    reason: str,
    phase: str,
) -> dict[str, Any]:
    """
    Best-effort, persisted cooldown for regenerate actions.

    Returns a small dict that can be attached to tool result for observability:
      - allowed: bool
      - min_interval_seconds
      - last_regenerate_at
      - next_allowed_at
      - phase/reason (truncated)
    """
    cid = str(conversation_id or "").strip()
    state_file = _chatgpt_regenerate_state_file()
    min_interval = int(_chatgpt_regenerate_min_interval_seconds())
    window_seconds = int(_chatgpt_regenerate_window_seconds())
    max_per_window = int(_chatgpt_regenerate_max_per_window())
    now = float(time.time())

    # If no state file is configured (or no conversation id), keep legacy behavior.
    if state_file is None or not cid:
        return {
            "allowed": True,
            "min_interval_seconds": min_interval,
            "last_regenerate_at": None,
            "next_allowed_at": None,
            "window_seconds": window_seconds,
            "window_max": max_per_window,
            "window_count": None,
            "window_next_allowed_at": None,
            "phase": str(phase)[:80],
            "reason": str(reason)[:120],
        }

    lock_file = _chatgpt_regenerate_lock_file(state_file)
    async with _flock_exclusive(lock_file):
        state = _read_json_dict(state_file)
        convs = state.get("conversations")
        if not isinstance(convs, dict):
            convs = {}

        entry = convs.get(cid)
        if not isinstance(entry, dict):
            entry = {}

        last_at = 0.0
        try:
            last_at = float(entry.get("last_regenerate_at") or 0.0)
        except Exception:
            last_at = 0.0

        next_allowed = (last_at + float(min_interval)) if (last_at > 0.0 and min_interval > 0) else 0.0
        allowed_by_interval = bool(next_allowed <= 0.0 or now >= next_allowed)

        window_start = 0.0
        window_count = 0
        window_next_allowed = 0.0
        allowed_by_window = True
        if max_per_window > 0 and window_seconds > 0:
            try:
                window_start = float(entry.get("window_start") or 0.0)
            except Exception:
                window_start = 0.0
            try:
                window_count = int(entry.get("window_count") or 0)
            except Exception:
                window_count = 0

            current_window_start = now - (now % float(window_seconds))
            if window_start <= 0.0 or abs(window_start - current_window_start) > 1.0:
                window_start = current_window_start
                window_count = 0

            allowed_by_window = bool(window_count < max_per_window)
            window_next_allowed = (window_start + float(window_seconds)) if not allowed_by_window else 0.0

        allowed = bool(allowed_by_interval and allowed_by_window)
        window_count_after = (window_count + 1) if (allowed and max_per_window > 0) else window_count
        if allowed:
            convs[cid] = {
                "last_regenerate_at": now,
                "phase": str(phase)[:80],
                "reason": str(reason)[:200],
                "window_start": (window_start if (max_per_window > 0 and window_start > 0.0) else None),
                "window_count": (window_count_after if max_per_window > 0 else None),
            }
            # Keep the file compact: retain only the latest 200 conversations.
            if len(convs) > 220:
                try:
                    items = []
                    for k, v in convs.items():
                        ts = 0.0
                        if isinstance(v, dict):
                            try:
                                ts = float(v.get("last_regenerate_at") or 0.0)
                            except Exception:
                                ts = 0.0
                        items.append((k, ts))
                    items.sort(key=lambda x: x[1], reverse=True)
                    keep = {k for k, _ in items[:200]}
                    convs = {k: convs[k] for k in keep if k in convs}
                except Exception:
                    pass

        # Always update `updated_at` so external monitors can tell guardrails are running,
        # even when a request is denied by interval/window.
        state["conversations"] = convs
        state["updated_at"] = now
        try:
            _atomic_write_json(state_file, state)
        except Exception:
            pass

        return {
            "allowed": allowed,
            "min_interval_seconds": min_interval,
            "last_regenerate_at": (last_at if last_at > 0 else None),
            "next_allowed_at": (next_allowed if next_allowed > 0 else None),
            "window_seconds": window_seconds,
            "window_max": max_per_window,
            "window_count": (window_count_after if max_per_window > 0 else None),
            "window_next_allowed_at": (window_next_allowed if window_next_allowed > 0 else None),
            "phase": str(phase)[:80],
            "reason": str(reason)[:120],
        }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_json_dict(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


async def _chatgpt_wait_refresh_reserve(
    *,
    conversation_id: str | None,
    reason: str,
    phase: str,
) -> dict[str, Any]:
    """
    Best-effort, persisted cooldown for refreshes triggered by wait().

    Returns a small dict that can be attached to tool result for observability:
      - allowed: bool
      - min_interval_seconds
      - last_refresh_at
      - next_allowed_at
      - phase/reason (truncated)
    """
    cid = str(conversation_id or "").strip()
    state_file = _chatgpt_wait_refresh_state_file()
    min_interval = int(_chatgpt_wait_refresh_min_interval_seconds())
    window_seconds = int(_chatgpt_wait_refresh_window_seconds())
    max_per_window = int(_chatgpt_wait_refresh_max_per_window())
    now = float(time.time())

    # If no state file is configured (or no conversation id), keep legacy behavior.
    if state_file is None or not cid:
        return {
            "allowed": True,
            "min_interval_seconds": min_interval,
            "last_refresh_at": None,
            "next_allowed_at": None,
            "window_seconds": window_seconds,
            "window_max": max_per_window,
            "window_count": None,
            "window_next_allowed_at": None,
            "phase": str(phase or "")[:80],
            "reason": str(reason or "")[:200],
        }

    lock_file = _chatgpt_wait_refresh_lock_file(state_file)
    async with _flock_exclusive(lock_file):
        state = _read_json_dict(state_file)
        convs = state.get("conversations")
        if not isinstance(convs, dict):
            convs = {}

        entry = convs.get(cid)
        if not isinstance(entry, dict):
            entry = {}
        try:
            last_refresh_at = float(entry.get("last_refresh_at") or 0.0)
        except Exception:
            last_refresh_at = 0.0

        allowed_by_interval = True
        next_allowed_at = None
        if min_interval > 0 and last_refresh_at > 0:
            next_allowed_at = float(last_refresh_at) + float(min_interval)
            if now < next_allowed_at:
                allowed_by_interval = False

        window_start = 0.0
        window_count = 0
        window_next_allowed_at = None
        allowed_by_window = True
        if max_per_window > 0 and window_seconds > 0:
            try:
                window_start = float(entry.get("window_start") or 0.0)
            except Exception:
                window_start = 0.0
            try:
                window_count = int(entry.get("window_count") or 0)
            except Exception:
                window_count = 0

            current_window_start = now - (now % float(window_seconds))
            if window_start <= 0.0 or abs(window_start - current_window_start) > 1.0:
                window_start = current_window_start
                window_count = 0

            if window_count >= max_per_window:
                allowed_by_window = False
                window_next_allowed_at = float(window_start) + float(window_seconds)

        allowed = bool(allowed_by_interval and allowed_by_window)
        if allowed:
            entry["last_refresh_at"] = float(now)
            entry["last_refresh_phase"] = str(phase or "")[:80]
            entry["last_refresh_reason"] = str(reason or "")[:200]
            if max_per_window > 0 and window_seconds > 0:
                entry["window_start"] = float(window_start) if window_start > 0.0 else float(now - (now % float(window_seconds)))
                entry["window_count"] = int(window_count) + 1
            convs[cid] = entry

            # Prune old entries (best-effort): keep at most 200 recent conversations.
            try:
                items: list[tuple[str, dict[str, Any]]] = []
                for k, v in list(convs.items()):
                    if not isinstance(v, dict):
                        continue
                    try:
                        ts = float(v.get("last_refresh_at") or 0.0)
                    except Exception:
                        ts = 0.0
                    items.append((k, {"last_refresh_at": ts}))
                items.sort(key=lambda kv: kv[1]["last_refresh_at"], reverse=True)
                keep = set([k for k, _ in items[:200]])
                if len(convs) > 220:
                    convs = {k: v for k, v in convs.items() if k in keep}
            except Exception:
                pass

            state["version"] = int(state.get("version") or 1)
            state["updated_at"] = float(now)
            state["conversations"] = convs
            try:
                _atomic_write_json(state_file, state)
            except Exception:
                pass

        return {
            "allowed": bool(allowed),
            "min_interval_seconds": min_interval,
            "last_refresh_at": (last_refresh_at if last_refresh_at > 0 else None),
            "next_allowed_at": next_allowed_at,
            "window_seconds": window_seconds,
            "window_max": max_per_window,
            "window_count": (window_count if max_per_window > 0 else None),
            "window_next_allowed_at": window_next_allowed_at,
            "phase": str(phase or "")[:80],
            "reason": str(reason or "")[:200],
        }





@asynccontextmanager
async def _chatgpt_global_lock(ctx: Context | None) -> Any:
    lock_file = _chatgpt_global_lock_file()
    if lock_file is None:
        yield None
        return
    if fcntl is None:
        await _ctx_info(ctx, "CHATGPT_GLOBAL_* configured but file locking is unavailable; continuing without global lock.")
        yield None
        return
    async with _flock_exclusive(lock_file) as f:
        yield f


def _chatgpt_blocked_state_file() -> Path:
    raw = (os.environ.get("CHATGPT_BLOCKED_STATE_FILE") or ".run/chatgpt_blocked_state.json").strip()
    return Path(raw).expanduser()


def _chatgpt_blocked_lock_file(state_file: Path) -> Path:
    raw = (os.environ.get("CHATGPT_BLOCKED_LOCK_FILE") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(str(state_file) + ".lock")


def _chatgpt_blocked_cooldown_seconds() -> int:
    raw = (os.environ.get("CHATGPT_BLOCKED_COOLDOWN_SECONDS") or "").strip()
    if not raw:
        return 15 * 60
    try:
        return max(0, int(raw))
    except ValueError:
        return 15 * 60


def _chatgpt_verification_cooldown_seconds() -> int:
    raw = (os.environ.get("CHATGPT_VERIFICATION_COOLDOWN_SECONDS") or "").strip()
    if not raw:
        return max(60 * 60, _chatgpt_blocked_cooldown_seconds())
    try:
        return max(0, int(raw))
    except ValueError:
        return max(60 * 60, _chatgpt_blocked_cooldown_seconds())


def _chatgpt_verification_pending_cooldown_seconds() -> int:
    raw = (os.environ.get("CHATGPT_VERIFICATION_PENDING_COOLDOWN_SECONDS") or "").strip()
    if not raw:
        return 90
    try:
        return max(10, int(raw))
    except ValueError:
        return 90


def _chatgpt_auto_verification_click_enabled() -> bool:
    return _truthy_env("CHATGPT_AUTO_VERIFICATION_CLICK", True)


def _chatgpt_auto_verification_click_wait_ms() -> int:
    raw = (os.environ.get("CHATGPT_AUTO_VERIFICATION_CLICK_WAIT_MS") or "").strip()
    if not raw:
        return 2_500
    try:
        return max(500, int(raw))
    except ValueError:
        return 2_500


def _chatgpt_auto_verification_observe_seconds() -> float:
    raw = (os.environ.get("CHATGPT_AUTO_VERIFICATION_OBSERVE_SECONDS") or "").strip()
    if not raw:
        return 12.0
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 12.0


def _chatgpt_auto_verification_poll_ms() -> int:
    raw = (os.environ.get("CHATGPT_AUTO_VERIFICATION_POLL_MS") or "").strip()
    if not raw:
        return 1_000
    try:
        return max(250, int(raw))
    except ValueError:
        return 1_000


def _chatgpt_unusual_activity_cooldown_seconds() -> int:
    raw = (os.environ.get("CHATGPT_UNUSUAL_ACTIVITY_COOLDOWN_SECONDS") or "").strip()
    if not raw:
        return 20 * 60
    try:
        return max(0, int(raw))
    except ValueError:
        return 20 * 60


def _chatgpt_unusual_activity_backoff_max_seconds() -> int:
    raw = (os.environ.get("CHATGPT_UNUSUAL_ACTIVITY_BACKOFF_MAX_SECONDS") or "").strip()
    if not raw:
        return 2 * 60 * 60
    try:
        return max(0, int(raw))
    except ValueError:
        return 2 * 60 * 60


def _chatgpt_unusual_activity_backoff_window_seconds() -> int:
    raw = (os.environ.get("CHATGPT_UNUSUAL_ACTIVITY_BACKOFF_WINDOW_SECONDS") or "").strip()
    if not raw:
        return 6 * 60 * 60
    try:
        return max(0, int(raw))
    except ValueError:
        return 6 * 60 * 60


def _chatgpt_network_recovery_cooldown_seconds() -> int:
    raw = (os.environ.get("CHATGPT_NETWORK_RECOVERY_COOLDOWN_SECONDS") or "").strip()
    if not raw:
        return 90
    try:
        return max(0, int(raw))
    except ValueError:
        return 90


async def _chatgpt_read_blocked_state() -> dict[str, Any]:
    """
    Return the last known blocked state (best-effort).

    Schema (best-effort):
      - blocked_until: unix seconds (float)
      - reason: short string
      - detected_at: unix seconds (float)
    """
    state_file = _chatgpt_blocked_state_file()
    lock_file = _chatgpt_blocked_lock_file(state_file)

    async with _flock_exclusive(lock_file):
        try:
            text = state_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return {}
        except Exception:
            return {}
        if not text:
            return {}
        try:
            data = json.loads(text)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}


async def _chatgpt_write_blocked_state(state: dict[str, Any]) -> None:
    state_file = _chatgpt_blocked_state_file()
    lock_file = _chatgpt_blocked_lock_file(state_file)

    async with _flock_exclusive(lock_file):
        try:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        except Exception:
            return


async def _chatgpt_set_blocked(
    *,
    reason: str,
    cooldown_seconds: int,
    artifacts: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = time.time()
    adjusted_cooldown = max(0, int(cooldown_seconds))
    unusual_activity_count = 0
    if reason == "unusual_activity" and _truthy_env("CHATGPT_UNUSUAL_ACTIVITY_BACKOFF", True):
        try:
            prev_state = await _chatgpt_read_blocked_state()
        except Exception:
            prev_state = {}
        prev_reason = str((prev_state or {}).get("reason") or "")
        prev_detected = float((prev_state or {}).get("detected_at") or 0.0)
        window = float(_chatgpt_unusual_activity_backoff_window_seconds())
        if prev_reason == "unusual_activity" and prev_detected > 0 and (now - prev_detected) <= window:
            unusual_activity_count = int(prev_state.get("unusual_activity_count") or 0) + 1
        else:
            unusual_activity_count = 1
        max_backoff = max(0, int(_chatgpt_unusual_activity_backoff_max_seconds()))
        if adjusted_cooldown > 0 and max_backoff > 0:
            adjusted_cooldown = min(max_backoff, adjusted_cooldown * (2 ** max(0, unusual_activity_count - 1)))
    state: dict[str, Any] = {
        "detected_at": now,
        "blocked_until": now + adjusted_cooldown,
        "reason": str(reason or "blocked"),
    }
    if unusual_activity_count:
        state["unusual_activity_count"] = unusual_activity_count
    state["cooldown_seconds"] = adjusted_cooldown
    if artifacts:
        state["artifacts"] = dict(artifacts)
    if extra:
        try:
            for k, v in dict(extra).items():
                if k in state:
                    continue
                state[k] = v
        except Exception:
            pass
    await _chatgpt_write_blocked_state(state)
    _maybe_append_blocked_event(
        {
            "event": "chatgpt_blocked",
            "reason": state.get("reason"),
            "detected_at": state.get("detected_at"),
            "blocked_until": state.get("blocked_until"),
            "cooldown_seconds": state.get("cooldown_seconds"),
            "unusual_activity_count": state.get("unusual_activity_count"),
            "phase": state.get("phase"),
            "title": state.get("title"),
            "url": state.get("url"),
            "connection": state.get("connection"),
            "signals": state.get("signals"),
            "artifacts": state.get("artifacts"),
        }
    )
    return state


async def _chatgpt_clear_blocked_state() -> dict[str, Any]:
    prev = await _chatgpt_read_blocked_state()
    await _chatgpt_write_blocked_state({"blocked_until": 0.0, "cleared_at": time.time()})
    return prev


def _chatgpt_blocked_probe_actions() -> set[str]:
    return {"self_check", "capture_ui"}


def _chatgpt_action_allowed_during_blocked(*, action: str, reason: str) -> bool:
    normalized_action = str(action or "").strip().lower()
    normalized_reason = str(reason or "").strip().lower()
    if normalized_action in _chatgpt_blocked_probe_actions():
        return True
    return normalized_reason in {"network", "unusual_activity", "verification_pending"} and normalized_action in {
        "wait",
        "conversation_export",
    }


async def _chatgpt_enforce_not_blocked(*, ctx: Context | None, action: str) -> None:
    if _truthy_env("CHATGPT_IGNORE_BLOCKED_STATE", False):
        return
    state = await _chatgpt_read_blocked_state()
    until = state.get("blocked_until")
    try:
        blocked_until = float(until) if until is not None else 0.0
    except Exception:
        blocked_until = 0.0
    if blocked_until <= 0:
        return
    now = time.time()
    if now >= blocked_until:
        return

    reason = str(state.get("reason") or "blocked")
    if _chatgpt_action_allowed_during_blocked(action=action, reason=reason):
        return
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(blocked_until))
    await _ctx_info(ctx, f"ChatGPT blocked cooldown active ({reason}) until {when}.")
    raise RuntimeError(
        f"ChatGPT is in blocked cooldown ({reason}) until {when}. "
        "Fix the session in noVNC/Chrome, then retry "
        "(or call chatgpt_web_clear_blocked / remove the state file: "
        f"{_chatgpt_blocked_state_file()})."
    )





def _chatgpt_output_dir() -> Path:
    raw = (os.environ.get("CHATGPT_OUTPUT_DIR") or os.environ.get("CHATGPT_IMAGE_DIR") or "artifacts").strip()
    return Path(raw).expanduser()


def _chatgpt_upload_max_bytes() -> int | None:
    raw = (os.environ.get("CHATGPT_UPLOAD_MAX_BYTES") or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return max(0, value)


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_fingerprint_for_idempotency(path: Path) -> dict[str, Any]:
    """
    Stable fingerprint used only for idempotency hashing.

    Do NOT include absolute paths or mtimes here; those make retries/resumes unstable across
    temp dirs, mounts, and file re-writes even when the content is identical.
    """
    stat = path.stat()
    return {
        "name": str(path.name),
        "size_bytes": int(stat.st_size),
        "sha256": _file_sha256(path),
    }


def _file_fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "size_bytes": int(stat.st_size),
        "mtime": int(stat.st_mtime),
        "sha256": _file_sha256(path),
    }


def _file_fingerprint_for_idempotency(fp: dict[str, Any]) -> dict[str, Any]:
    """
    Stable fingerprint used for idempotency request hashes.

    Do NOT include absolute paths or mtimes here: retry loops (and zip expansion) can regenerate
    files with the same content but different paths/mtimes, which would otherwise trigger
    idempotency collisions even though we must resume/wait for the already-sent prompt.
    """
    raw_path = fp.get("path")
    try:
        name = Path(str(raw_path)).name if raw_path else ""
    except Exception:
        name = ""
    out: dict[str, Any] = {"name": name}
    if fp.get("size_bytes") is not None:
        try:
            out["size_bytes"] = int(fp.get("size_bytes") or 0)
        except Exception:
            out["size_bytes"] = int(fp.get("size_bytes") or 0)
    sha = fp.get("sha256")
    if isinstance(sha, str) and sha.strip():
        out["sha256"] = sha.strip()
    return out


def _resolve_upload_paths(file_paths: str | list[str] | None) -> list[Path]:
    if not file_paths:
        return []
    raw_paths: list[str]
    if isinstance(file_paths, str):
        raw_paths = [file_paths]
    else:
        raw_paths = list(file_paths)
    out: list[Path] = []
    max_bytes = _chatgpt_upload_max_bytes()
    for raw in raw_paths:
        if not raw or not str(raw).strip():
            continue
        p = Path(str(raw)).expanduser()
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve(strict=False)
        else:
            p = p.resolve(strict=False)
        if not p.exists():
            raise RuntimeError(f"upload file not found: {p}")
        if not p.is_file():
            raise RuntimeError(f"upload path is not a file: {p}")
        if max_bytes is not None and max_bytes > 0 and p.stat().st_size > max_bytes:
            raise RuntimeError(f"upload file too large: {p} ({p.stat().st_size} bytes > {max_bytes})")
        out.append(p)
    return out


def _chatgpt_image_min_area() -> int:
    raw = (os.environ.get("CHATGPT_IMAGE_MIN_AREA") or "").strip()
    if not raw:
        return 40_000
    try:
        return max(1_000, int(raw))
    except ValueError:
        return 40_000




_CHATGPT_CLOUDFLARE_TITLE_RE = _compile_env_regex(
    "CHATGPT_CLOUDFLARE_TITLE_REGEX",
    r"(Just a moment|Verifying)",
    re.I,
)
_CHATGPT_CLOUDFLARE_URL_RE = _compile_env_regex(
    "CHATGPT_CLOUDFLARE_URL_REGEX",
    r"(__cf_chl_|/cdn-cgi/challenge-platform/)",
    re.I,
)

_CHATGPT_LOGIN_URL_RE = _compile_env_regex(
    "CHATGPT_LOGIN_URL_REGEX",
    r"(auth\.openai\.com|/auth/|/login|/signin|/sign-in|/sign_up|/sign-up)",
    re.I,
)

_CHATGPT_LOGIN_TEXT_RE = _compile_env_regex(
    "CHATGPT_LOGIN_TEXT_REGEX",
    r"("
    r"\bLog\s*in\b|"
    r"\bSign\s*in\b|"
    r"\bSign\s*up\b|"
    r"Continue with Google|"
    r"Continue with Apple|"
    r"continue with google|"
    r"continue with apple|"
    r"登录|"
    r"注册"
    r")",
    re.I,
)

_CHATGPT_VERIFY_RE = _compile_env_regex(
    "CHATGPT_VERIFY_REGEX",
    r"("
    r"verify you are a human|"
    r"human verification|"
    r"captcha|"
    r"turnstile|"
    r"unusual traffic|"
    r"abnormal traffic|"
    r"异常流量|"
    r"人机验证|"
    r"请验证"
    r")",
    re.I,
)

_CHATGPT_UNUSUAL_ACTIVITY_RE = _compile_env_regex(
    "CHATGPT_UNUSUAL_ACTIVITY_REGEX",
    r"("
    r"unusual activity detected|"
    r"you('ve| have) sent a large number of messages|"
    r"doing a quick check to keep chatgpt safe|"
    r"you should get access to gpt-5 pro again soon|"
    r"检测到异常活动|"
    r"短时间.*(大量|很多).*(消息|请求)|"
    r"正在.*(快速检查|安全检查)|"
    r"你将.*(很快|稍后).*(再次|重新).*?(pro|GPT-5)"
    r")",
    re.I,
)

def _chatgpt_dom_risk_observation_enabled() -> bool:
    return _truthy_env("CHATGPT_DOM_RISK_OBSERVATION", True)


def _chatgpt_dom_risk_observation_max_chars() -> int:
    raw = (os.environ.get("CHATGPT_DOM_RISK_OBSERVATION_MAX_CHARS") or "").strip()
    if not raw:
        return 400
    try:
        return max(100, int(raw))
    except ValueError:
        return 400


def _compact_ws(text: str) -> str:
    return " ".join((text or "").split())


def _extract_match_context(*, hay: str, match: re.Match[str] | None, max_chars: int) -> str:
    if not match:
        return ""
    window = max(50, int(max_chars))
    start = max(0, match.start() - window // 2)
    end = min(len(hay), match.end() + window // 2)
    snippet = _compact_ws(hay[start:end])
    if len(snippet) > max_chars:
        snippet = snippet[: max(0, max_chars - 1)] + "…"
    return snippet


def _chatgpt_dom_risk_observation_from_snapshot(
    *,
    phase: str,
    title: str,
    url: str,
    body: str,
) -> dict[str, Any] | None:
    hay = "\n".join([title, url, body])
    signals: list[str] = []

    chosen: tuple[str, re.Match[str] | None] | None = None
    if _CHATGPT_UNUSUAL_ACTIVITY_RE.search(hay):
        chosen = ("unusual_activity", _CHATGPT_UNUSUAL_ACTIVITY_RE.search(hay))
        signals.append("unusual_activity")
    if _CHATGPT_VERIFY_RE.search(hay):
        chosen = chosen or ("verification", _CHATGPT_VERIFY_RE.search(hay))
        signals.append("verification")
    if _CHATGPT_LOGIN_URL_RE.search(url) or _CHATGPT_LOGIN_TEXT_RE.search(f"{title}\n{body}"):
        chosen = chosen or ("auth", _CHATGPT_LOGIN_TEXT_RE.search(f"{title}\n{body}"))
        signals.append("auth")
    if _CHATGPT_CLOUDFLARE_TITLE_RE.search(title) or _CHATGPT_CLOUDFLARE_URL_RE.search(url):
        chosen = chosen or ("cloudflare", _CHATGPT_CLOUDFLARE_URL_RE.search(url))
        signals.append("cloudflare")

    if not signals:
        return None

    max_chars = _chatgpt_dom_risk_observation_max_chars()
    snippet = ""
    matched = None
    if chosen is not None:
        sig, m = chosen
        matched = sig
        snippet = _extract_match_context(hay=hay, match=m, max_chars=max_chars)

    result: dict[str, Any] = {
        "phase": str(phase or "").strip(),
        "signals": signals,
        "matched": matched,
        "title": str(title or "").strip(),
        "url": str(url or "").strip(),
    }
    if snippet:
        result["snippet"] = snippet
    return result


async def _chatgpt_best_effort_dom_risk_observation(
    page,
    *,
    phase: str,
    ctx: Context | None,
) -> dict[str, Any] | None:
    if not _chatgpt_dom_risk_observation_enabled():
        return None

    try:
        title, url, body = await _chatgpt_page_snapshot(page)
    except Exception:
        return None
    return _chatgpt_dom_risk_observation_from_snapshot(phase=phase, title=title, url=url, body=body)


async def _chatgpt_page_snapshot(page) -> tuple[str, str, str]:
    title = ""
    try:
        title = (await page.title()).strip()
    except Exception:
        title = ""

    url = (page.url or "").strip()

    body = ""
    try:
        body = (await page.locator("body").inner_text(timeout=2_000)).strip()
    except Exception:
        body = ""
    return title, url, body


async def _chatgpt_cloudflare_signals(page, *, title: str, url: str, body: str) -> list[str]:
    signals: list[str] = []
    if _CHATGPT_CLOUDFLARE_TITLE_RE.search(title):
        signals.append("title")
    if _CHATGPT_CLOUDFLARE_URL_RE.search(url):
        signals.append("url")
    if signals:
        return signals

    # Some Cloudflare challenges render as a near-blank page (often just a logo),
    # without clear title/body text. Probe a couple of DOM-level hints.
    try:
        scripts = page.locator("script[src*='/cdn-cgi/'], script[src*='challenge-platform']")
        if await scripts.count():
            signals.append("dom_script:/cdn-cgi/")
    except Exception:
        pass
    try:
        meta = page.locator("meta[http-equiv='refresh' i]")
        if await meta.count():
            signals.append("dom_meta:refresh")
    except Exception:
        pass
    try:
        href = await page.evaluate("() => String(window.location && window.location.href || '')")
        if _CHATGPT_CLOUDFLARE_URL_RE.search(str(href or "")):
            signals.append("href")
    except Exception:
        pass

    # As a last resort, look for Cloudflare-specific tokens in the visible body snapshot.
    if (not signals) and _CHATGPT_CLOUDFLARE_URL_RE.search(body or ""):
        signals.append("body")
    return signals


async def _chatgpt_verification_pending_signals(
    page,
    *,
    title: str,
    url: str,
    body: str,
) -> list[str]:
    signals: list[str] = []
    hay = "\n".join([title, url, body])
    if re.search(r"\bVerifying(?:\.\.\.)?\b", hay, re.I):
        signals.append("snapshot:verifying")

    try:
        observed = await page.evaluate(
            """() => {
                const html = String((document.body && document.body.innerHTML) || (document.documentElement && document.documentElement.innerHTML) || "");
                const text = String((document.body && document.body.innerText) || "");
                const markers = [];
                if (/Verification successful\\. Waiting for chatgpt\\.com to respond/i.test(html)) {
                    markers.push("html:verification_success_waiting");
                }
                if (/loading-verifying/i.test(html)) {
                    markers.push("html:loading_verifying");
                }
                if (/\\bVerifying(?:\\.\\.\\.)?\\b/i.test(html) || /\\bVerifying(?:\\.\\.\\.)?\\b/i.test(text)) {
                    markers.push("dom:verifying");
                }
                return markers;
            }"""
        )
        if isinstance(observed, list):
            for marker in observed:
                if isinstance(marker, str) and marker and marker not in signals:
                    signals.append(marker)
    except Exception:
        pass
    return signals


async def _chatgpt_try_auto_verification_click(
    page,
    *,
    ctx: Context | None,
    phase: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "enabled": _chatgpt_auto_verification_click_enabled(),
        "attempted": False,
        "clicks": 0,
        "steps": [],
        "errors": [],
        "resolved": False,
        "pending": False,
        "pending_signals": [],
        "phase": phase,
    }
    if not result["enabled"]:
        return result

    wait_ms = _chatgpt_auto_verification_click_wait_ms()

    async def _try_click(locator, *, label: str) -> bool:
        try:
            if await locator.count() <= 0:
                return False
            target = locator.first
            try:
                await target.scroll_into_view_if_needed(timeout=1_000)
            except Exception:
                pass
            await target.click(timeout=1_500, force=True)
            result["attempted"] = True
            result["clicks"] = int(result["clicks"]) + 1
            result["steps"].append(label)
            await page.wait_for_timeout(wait_ms)
            return True
        except Exception as exc:
            result["errors"].append(f"{label}: {type(exc).__name__}")
            return False

    top_level_targets = [
        ("input[type='checkbox']", "page:checkbox"),
        ("button:has-text('Verify')", "page:button_verify"),
        ("button:has-text('human')", "page:button_human"),
        ("button:has-text('验证')", "page:button_verify_zh"),
        ("[role='button']:has-text('Verify')", "page:role_button_verify"),
        ("[role='button']:has-text('验证')", "page:role_button_verify_zh"),
    ]
    for selector, label in top_level_targets:
        await _try_click(page.locator(selector), label=label)

    frame_targets = [
        "iframe[src*='challenges.cloudflare.com']",
        "iframe[src*='challenge-platform']",
        "iframe[title*='Cloudflare']",
        "iframe[title*='challenge']",
        "iframe[title*='captcha']",
    ]
    frame_inner_targets = [
        ("input[type='checkbox']", "frame:checkbox"),
        ("[role='checkbox']", "frame:role_checkbox"),
        ("label", "frame:label"),
        ("button:has-text('Verify')", "frame:button_verify"),
        ("button:has-text('human')", "frame:button_human"),
        ("button:has-text('验证')", "frame:button_verify_zh"),
        ("[role='button']:has-text('Verify')", "frame:role_button_verify"),
        ("[role='button']:has-text('验证')", "frame:role_button_verify_zh"),
    ]
    for frame_selector in frame_targets:
        frame = page.frame_locator(frame_selector)
        for inner_selector, suffix in frame_inner_targets:
            await _try_click(frame.locator(inner_selector), label=f"{frame_selector}:{suffix}")

    async def _try_click_box(
        box: dict[str, Any] | None,
        *,
        label: str,
        y_bias_top: bool = False,
        x_bias_left: bool = False,
    ) -> bool:
        if not isinstance(box, dict):
            return False
        try:
            x = float(box.get("x") or 0.0)
            y = float(box.get("y") or 0.0)
            width = float(box.get("width") or 0.0)
            height = float(box.get("height") or 0.0)
        except Exception:
            return False
        if width <= 1 or height <= 1:
            return False
        click_x = x + (min(24.0, max(18.0, width * 0.08)) if x_bias_left else (width / 2.0))
        click_y = y + (min(420.0, height / 2.0) if y_bias_top else (height / 2.0))
        try:
            await page.mouse.click(click_x, click_y)
            result["attempted"] = True
            result["clicks"] = int(result["clicks"]) + 1
            result["steps"].append(label)
            await page.wait_for_timeout(wait_ms)
            return True
        except Exception as exc:
            result["errors"].append(f"{label}: {type(exc).__name__}")
            return False

    async def _turnstile_fallback_box() -> tuple[dict[str, Any] | None, str | None, bool, bool]:
        for frame in getattr(page, "frames", []):
            try:
                frame_url = str(getattr(frame, "url", "") or "").lower()
            except Exception:
                frame_url = ""
            if "challenges.cloudflare.com" not in frame_url or "turnstile" not in frame_url:
                continue
            try:
                box = await frame.locator("body").bounding_box()
            except Exception as exc:
                result["errors"].append(f"fallback:turnstile_frame:{type(exc).__name__}")
                box = None
            if box:
                return box, "fallback:turnstile_frame_center", False, False
        try:
            hidden_input = page.locator("input[name='cf-turnstile-response']").first
            if await hidden_input.count() > 0:
                box = await hidden_input.evaluate(
                    """(el) => {
                        let cur = el;
                        while (cur) {
                            if (cur.nodeType === 1) {
                                const rect = cur.getBoundingClientRect();
                                const style = window.getComputedStyle(cur);
                                const visible = style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
                                if (visible && rect.width > 1 && rect.height > 1) {
                                    return {x: rect.x, y: rect.y, width: rect.width, height: rect.height};
                                }
                            }
                            cur = cur.parentElement;
                        }
                        const body = document.body.getBoundingClientRect();
                        return {x: body.x, y: body.y, width: body.width, height: body.height};
                    }"""
                )
                return box, "fallback:hidden_turnstile_ancestor", False, True
        except Exception as exc:
            result["errors"].append(f"fallback:hidden_turnstile:{type(exc).__name__}")
        try:
            body_box = await page.locator("body").bounding_box()
        except Exception as exc:
            result["errors"].append(f"fallback:page_body:{type(exc).__name__}")
            body_box = None
        if body_box:
            return body_box, "fallback:page_center", True, False
        return None, None, False, False

    if not result["attempted"]:
        fallback_box, fallback_label, y_bias_top, x_bias_left = await _turnstile_fallback_box()
        if fallback_box is not None and fallback_label:
            await _try_click_box(
                fallback_box,
                label=fallback_label,
                y_bias_top=y_bias_top,
                x_bias_left=x_bias_left,
            )

    observe_deadline = time.time() + _chatgpt_auto_verification_observe_seconds()
    poll_ms = _chatgpt_auto_verification_poll_ms()
    while True:
        try:
            title2, url2, body2 = await _chatgpt_page_snapshot(page)
            signals2 = await _chatgpt_cloudflare_signals(page, title=title2, url=url2, body=body2)
            verify2 = bool(_CHATGPT_VERIFY_RE.search(" ".join([title2, url2, body2])))
            pending2 = await _chatgpt_verification_pending_signals(page, title=title2, url=url2, body=body2)
            result["post_title"] = title2
            result["post_url"] = url2
            result["post_signals"] = signals2
            result["pending_signals"] = pending2
            result["resolved"] = bool((not signals2) and (not verify2) and (not pending2))
            if result["resolved"]:
                break
            if pending2:
                result["pending"] = True
            if (not result["attempted"]) or time.time() >= observe_deadline or not pending2:
                break
            await page.wait_for_timeout(poll_ms)
            continue
        except Exception as exc:
            result["errors"].append(f"post_check: {type(exc).__name__}")
            break

    if result["attempted"]:
        await _ctx_info(
            ctx,
            (
                "Auto verification click attempted "
                f"(clicks={result['clicks']}, resolved={result['resolved']})."
            ),
        )
    return result


async def _raise_if_chatgpt_blocked(
    page,
    *,
    ctx: Context | None,
    phase: str,
    connection: str | None = None,
) -> None:
    title, url, body = await _chatgpt_page_snapshot(page)
    # Safety: if ChatGPT automation is pointed at a Gemini conversation URL (or other non-ChatGPT page),
    # do not mark global ChatGPT blocked-state. This typically indicates a caller mixed up
    # `chatgpt_web.*` vs `gemini_web.*` (e.g. passing a Gemini conversation_url to ChatGPT tools).
    if "gemini.google.com" in str(url or "").lower():
        artifacts = await _capture_debug_artifacts(page, label=f"chatgpt_{phase}_wrong_host")
        msg = f"ChatGPT automation is on a Gemini URL ({url}); refusing to classify as ChatGPT blocked."
        if artifacts:
            msg += f" Debug artifacts: {artifacts}"
        raise RuntimeError(msg)

    cloudflare_signals = await _chatgpt_cloudflare_signals(page, title=title, url=url, body=body)
    if cloudflare_signals:
        # Cloudflare challenges can show up briefly during redirects (especially when CDP-attaching
        # to a long-lived Chrome with many tabs). Avoid false-positive cooldowns by re-checking
        # once when the signal is weak (URL token only) and the page title isn't yet conclusive.
        try:
            weak_signals = set(cloudflare_signals).issubset({"url", "href", "body"})
            weak_title = not _CHATGPT_CLOUDFLARE_TITLE_RE.search(title or "")
            if weak_signals and weak_title:
                await page.wait_for_timeout(1500)
                title2, url2, body2 = await _chatgpt_page_snapshot(page)
                cloudflare_signals2 = await _chatgpt_cloudflare_signals(page, title=title2, url=url2, body=body2)
                if not cloudflare_signals2:
                    return
                title, url, body, cloudflare_signals = title2, url2, body2, cloudflare_signals2
        except Exception:
            pass

        auto_verification = await _chatgpt_try_auto_verification_click(page, ctx=ctx, phase=phase)
        if auto_verification.get("resolved"):
            return

        pending_verification = bool(auto_verification.get("pending"))

        artifacts = await _capture_debug_artifacts(page, label=f"chatgpt_{phase}_cloudflare")
        state = await _chatgpt_set_blocked(
            reason="verification_pending" if pending_verification else "cloudflare",
            cooldown_seconds=(
                _chatgpt_verification_pending_cooldown_seconds()
                if pending_verification
                else _chatgpt_verification_cooldown_seconds()
            ),
            artifacts=artifacts,
            extra={
                "phase": phase,
                "title": title,
                "url": url,
                "signals": cloudflare_signals,
                "connection": connection,
                "auto_verification": auto_verification,
            },
        )
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(state.get("blocked_until") or 0.0)))
        hint = (
            "Open ChatGPT in the same Chrome via noVNC, complete the verification manually, then retry."
            if (not connection) or connection == "cdp"
            else (
                "CDP Chrome appears unavailable; the server is using Playwright-managed Chromium. "
                "Start the noVNC Chrome (ops/chrome_start.sh), ensure CHATGPT_CDP_URL is reachable, "
                "complete the verification manually, then retry."
            )
        )
        if pending_verification:
            msg = (
                "ChatGPT verification appears to be in progress after the auto-click. "
                "Wait briefly for the challenge to finish, then retry. "
                f"{hint}"
            )
        else:
            msg = f"Blocked by Cloudflare/verification page ({title}). {hint}"
        if artifacts:
            msg += f" Debug artifacts: {artifacts}"
        msg += f" Signals: {cloudflare_signals}."
        if auto_verification.get("attempted"):
            msg += (
                " Auto-click attempted"
                f" (clicks={auto_verification.get('clicks')}, resolved={auto_verification.get('resolved')})."
            )
        if auto_verification.get("pending_signals"):
            msg += f" Pending signals: {auto_verification.get('pending_signals')}."
        msg += f" Cooldown until {when}."
        raise RuntimeError(msg)

    if _CHATGPT_LOGIN_URL_RE.search(url) or _CHATGPT_LOGIN_TEXT_RE.search(f"{title}\n{body}"):
        artifacts = await _capture_debug_artifacts(page, label=f"chatgpt_{phase}_login")
        state = await _chatgpt_set_blocked(
            reason="auth",
            cooldown_seconds=_chatgpt_blocked_cooldown_seconds(),
            artifacts=artifacts,
            extra={"connection": connection},
        )
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(state.get("blocked_until") or 0.0)))
        msg = (
            "ChatGPT appears to require login or re-authentication. "
            "Log in to ChatGPT in the Chrome instance used by CDP, then retry."
        )
        if artifacts:
            msg += f" Debug artifacts: {artifacts}"
        msg += f" Cooldown until {when}."
        raise RuntimeError(msg)

    hay = " ".join([title, url, body])
    if _CHATGPT_UNUSUAL_ACTIVITY_RE.search(hay):
        artifacts = await _capture_debug_artifacts(page, label=f"chatgpt_{phase}_unusual_activity")
        state = await _chatgpt_set_blocked(
            reason="unusual_activity",
            cooldown_seconds=_chatgpt_unusual_activity_cooldown_seconds(),
            artifacts=artifacts,
            extra={
                "phase": phase,
                "title": title,
                "url": url,
                "connection": connection,
            },
        )
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(state.get("blocked_until") or 0.0)))
        msg = (
            "ChatGPT temporarily limited the session due to unusual activity (likely high message frequency). "
            "Wait for the cooldown to expire, reduce concurrency / increase CHATGPT_MIN_PROMPT_INTERVAL_SECONDS, then retry. "
        )
        if artifacts:
            msg += f" Debug artifacts: {artifacts}"
        msg += f" Cooldown until {when}."
        raise RuntimeError(msg)

    if _CHATGPT_VERIFY_RE.search(hay):
        auto_verification = await _chatgpt_try_auto_verification_click(page, ctx=ctx, phase=phase)
        if auto_verification.get("resolved"):
            return
        pending_verification = bool(auto_verification.get("pending"))
        artifacts = await _capture_debug_artifacts(page, label=f"chatgpt_{phase}_verify")
        state = await _chatgpt_set_blocked(
            reason="verification_pending" if pending_verification else "verification",
            cooldown_seconds=(
                _chatgpt_verification_pending_cooldown_seconds()
                if pending_verification
                else _chatgpt_verification_cooldown_seconds()
            ),
            artifacts=artifacts,
            extra={
                "connection": connection,
                "auto_verification": auto_verification,
            },
        )
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(state.get("blocked_until") or 0.0)))
        if pending_verification:
            msg = (
                "ChatGPT verification appears to be in progress after the auto-click. "
                "Wait briefly for the challenge to finish, then retry."
            )
        else:
            msg = (
                "ChatGPT is blocked by a verification/captcha page. "
                "Open ChatGPT in the same Chrome via noVNC, complete the verification manually, then retry."
            )
        if artifacts:
            msg += f" Debug artifacts: {artifacts}"
        if auto_verification.get("attempted"):
            msg += (
                " Auto-click attempted"
                f" (clicks={auto_verification.get('clicks')}, resolved={auto_verification.get('resolved')})."
            )
        if auto_verification.get("pending_signals"):
            msg += f" Pending signals: {auto_verification.get('pending_signals')}."
        msg += f" Cooldown until {when}."
        raise RuntimeError(msg)


_DEEP_RESEARCH_PILL_RE = re.compile(r"(Deep\s*research|Research|研究)", re.I)



_TRANSIENT_PLAYWRIGHT_ERROR_TOKENS = (
    "Execution context was destroyed",
    "Target closed",
    "Target crashed",
    "Browser closed",
    "page, context or browser has been closed",
    "Navigation failed",
    "net::ERR_",
    "ERR_CONNECTION_RESET",
    "ERR_CONNECTION_CLOSED",
    "ERR_NETWORK_CHANGED",
    "ECONNRESET",
    "NS_ERROR_NET_RESET",
    "CDP connect failed",
    "connect_over_cdp",
    "BrowserType.connect_over_cdp",
    "ws://127.0.0.1:9222/",
)


def _looks_like_transient_playwright_error(exc: Exception) -> bool:
    if isinstance(exc, PlaywrightTimeoutError):
        return True
    if isinstance(exc, TimeoutError):
        return True
    msg = str(exc) or ""
    msg_l = msg.lower()
    return any(token.lower() in msg_l for token in _TRANSIENT_PLAYWRIGHT_ERROR_TOKENS)


def _looks_like_upload_page_closed_error(exc: Exception) -> bool:
    msg = str(exc) or ""
    msg_l = msg.lower()
    if "target page, context or browser has been closed" in msg_l:
        return True
    if "set_input_files" in msg_l and "closed" in msg_l:
        return True
    if ("file chooser" in msg_l or "filechooser" in msg_l) and "closed" in msg_l:
        return True
    return False


async def _chatgpt_wait_for_conversation_url(page, *, timeout_seconds: float = 8.0) -> str:
    deadline = time.time() + max(0.2, timeout_seconds)
    last = (page.url or "").strip()
    started_at = time.time()
    tried_best_effort = False
    best_effort: str = ""
    while time.time() < deadline:
        url = (page.url or "").strip()
        if url and url != last:
            last = url
        if "/c/" in (url or ""):
            return url
        try:
            for frame in page.frames:
                f_url = (getattr(frame, "url", "") or "").strip()
                if "/c/" in f_url:
                    return f_url
        except Exception:
            pass
        try:
            href = await page.evaluate("() => window.location && window.location.href ? String(window.location.href) : ''")
            href = (str(href or "").strip() if href is not None else "")
            if href and href != last:
                last = href
            if "/c/" in (href or ""):
                return href
        except Exception:
            pass
        if not tried_best_effort and (time.time() - started_at) >= 1.0:
            tried_best_effort = True
            try:
                alt = await _best_effort_conversation_url(page)
                if alt:
                    best_effort = alt
            except Exception:
                pass
        await page.wait_for_timeout(250)

    if "/c/" not in (last or ""):
        try:
            alt = await _best_effort_conversation_url(page)
            if alt:
                last = alt
        except Exception:
            pass

    if "/c/" not in (last or "") and best_effort:
        last = best_effort
    return last


async def _best_effort_conversation_url(page) -> str:
    url = (page.url or "").strip()
    if "/c/" in url:
        return url
    try:
        for frame in page.frames:
            f_url = (getattr(frame, "url", "") or "").strip()
            if "/c/" in f_url:
                return f_url
    except Exception:
        pass

    try:
        href = await page.evaluate("() => window.location && window.location.href ? String(window.location.href) : ''")
        href = (str(href or "").strip() if href is not None else "")
        if "/c/" in href:
            return href
    except Exception:
        pass

    try:
        href = await page.evaluate(
            """() => {
  const candidates = [];
  for (const el of document.querySelectorAll('link[rel=\"canonical\"], link[rel=\"alternate\"]')) {
    const href = el.href || el.getAttribute('href') || '';
    if (href) candidates.push(href);
  }
  for (const el of document.querySelectorAll('meta[property=\"og:url\"], meta[name=\"og:url\"], meta[name=\"twitter:url\"]')) {
    const content = el.content || el.getAttribute('content') || '';
    if (content) candidates.push(content);
  }
  for (const v of candidates) {
    if (v.includes('/c/')) return v;
  }
  return '';
}"""
        )
        href = (str(href or "").strip() if href is not None else "")
        if "/c/" in href:
            return href
    except Exception:
        pass

    try:
        html = await page.content()
    except Exception:
        return url

    if not html:
        return url

    m = re.search(r"https?://chatgpt\\.com/c/[a-z0-9-]{16,}", html, re.I)
    if m:
        return m.group(0)
    m = re.search(r'href=\"(/c/[a-z0-9-]{16,})\"', html, re.I)
    if m:
        return f"https://chatgpt.com{m.group(1)}"
    return url




async def _chatgpt_refresh_page(
    page,
    *,
    ctx: Context | None,
    reason: str,
    phase: str,
    preferred_url: str | None = None,
) -> None:
    await _ctx_info(ctx, f"Refreshing ChatGPT page (recovery): {reason}")
    target_url = str(preferred_url or "").strip()
    current_url = str(page.url or "").strip()
    current_conv_id = _chatgpt_conversation_id_from_url(current_url)
    target_conv_id = _chatgpt_conversation_id_from_url(target_url)
    should_navigate = False
    if target_url:
        if target_conv_id:
            should_navigate = current_conv_id != target_conv_id
        else:
            should_navigate = current_url.rstrip("/") != target_url.rstrip("/")
    try:
        if should_navigate:
            await _ctx_info(ctx, f"Refreshing ChatGPT page via navigation to {target_url}")
            await _goto_with_retry(page, target_url, ctx=ctx)
        else:
            await page.reload(wait_until="commit", timeout=_navigation_timeout_ms())
    except Exception:
        try:
            fallback_url = target_url or current_url or _load_config().url
            await _goto_with_retry(page, fallback_url, ctx=ctx)
        except Exception:
            pass
    await _human_pause(page)
    await _raise_if_chatgpt_blocked(page, ctx=ctx, phase=phase)




def _normalize_model_key(model: str) -> str:
    normalized = re.sub(r"[^a-z0-9.]+", "", model.strip().lower())
    if normalized in {"auto", "default"}:
        return "gpt-5-2"
    if "thinking" in normalized:
        return "gpt-5-2-thinking"
    if "instant" in normalized:
        return "gpt-5-2-instant"
    if "pro" in normalized:
        return "gpt-5-2-pro"
    if "52" in normalized or "5.2" in normalized:
        return "gpt-5-2"
    raise ValueError(f"Unsupported model: {model}")


_MODEL_TESTID_BY_KEY: dict[str, str] = {
    "gpt-5-2": "model-switcher-gpt-5-2",
    "gpt-5-2-instant": "model-switcher-gpt-5-2-instant",
    "gpt-5-2-thinking": "model-switcher-gpt-5-2-thinking",
    "gpt-5-2-pro": "model-switcher-gpt-5-2-pro",
}


async def _current_model_text(page) -> str:
    selector = page.locator("button[aria-label^='Model selector']").first
    if await selector.count() and await selector.is_visible():
        text = (await selector.inner_text()).strip()
        if text:
            return " ".join(text.split())
        aria = await selector.get_attribute("aria-label")
        return aria or ""
    header = page.locator("header").first
    if await header.count():
        return " ".join((await header.inner_text()).split())
    return ""

def _model_text_matches_key(model_key: str, current_model_text: str) -> bool:
    current = " ".join((current_model_text or "").split())
    if not current:
        return False

    if model_key.endswith("-pro"):
        return bool(re.search(r"\bPro\b", current, re.I))
    if model_key.endswith("-thinking"):
        return bool(re.search(r"\bThinking\b", current, re.I))
    if model_key.endswith("-instant"):
        return bool(re.search(r"\bInstant\b", current, re.I))

    # Base model: accept either "Auto" or "ChatGPT 5.2" without a mode suffix.
    if re.search(r"\bAuto\b", current, re.I):
        return True
    if re.search(r"\bChatGPT\s*5\.2\b", current, re.I) and not re.search(r"\b(Pro|Thinking|Instant)\b", current, re.I):
        return True
    return False


def _chatgpt_model_switch_fail_open() -> bool:
    # Fail-open by default: when the UI refuses to switch models (disabled option / A/B),
    # continue with the currently selected model instead of erroring the whole job.
    return _truthy_env("CHATGPT_MODEL_SWITCH_FAIL_OPEN", True)


async def _ensure_model(page, *, model: str, ctx: Context | None) -> None:
    model_key = _normalize_model_key(model)
    wanted_testid = _MODEL_TESTID_BY_KEY.get(model_key)
    if not wanted_testid:
        raise RuntimeError(f"Unsupported model key: {model_key}")

    current = await _current_model_text(page)
    if _model_text_matches_key(model_key, current):
        return

    await _ctx_info(ctx, f"Switching model → {model_key}")

    selector = page.locator("button[aria-label^='Model selector']").first
    try:
        selector_visible = bool(await selector.count()) and await selector.is_visible()
    except Exception:
        selector_visible = False
    if not selector_visible:
        if _chatgpt_model_switch_fail_open():
            await _ctx_info(ctx, f"Model selector not visible; continuing without switching (wanted={model_key}, current={current!r}).")
            return
        raise RuntimeError(f"Model selector not visible (wanted={model_key}, current={current!r}).")

    try:
        await selector.click()
        await _human_pause(page)
    except Exception as exc:
        if _chatgpt_model_switch_fail_open():
            await _ctx_info(ctx, f"Model selector click failed; continuing without switching (wanted={model_key}, current={current!r}): {exc}")
            return
        raise

    menu = page.locator("[role='menu']").first
    await menu.wait_for(state="visible", timeout=10_000)

    # Preferred: stable testid (when available).
    item = page.locator(f"[data-testid='{wanted_testid}']").first
    if await item.count():
        await item.wait_for(state="visible", timeout=10_000)
        aria_disabled = ((await item.get_attribute("aria-disabled")) or "").strip().lower()
        data_disabled = await item.get_attribute("data-disabled")
        if aria_disabled == "true" or data_disabled is not None:
            title, url, body = await _chatgpt_page_snapshot(page)
            hay = " ".join([title, url, body])
            if _CHATGPT_UNUSUAL_ACTIVITY_RE.search(hay):
                artifacts = await _capture_debug_artifacts(page, label="chatgpt_model_unusual_activity")
                state = await _chatgpt_set_blocked(
                    reason="unusual_activity",
                    cooldown_seconds=_chatgpt_unusual_activity_cooldown_seconds(),
                    artifacts=artifacts,
                    extra={"phase": "model", "wanted_model": model_key, "title": title, "url": url},
                )
                when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(state.get("blocked_until") or 0.0)))
                raise RuntimeError(
                    "ChatGPT temporarily limited the session due to unusual activity (model option is disabled). "
                    f"Cooldown until {when}."
                )

            if _chatgpt_model_switch_fail_open():
                await _ctx_info(
                    ctx,
                    "ChatGPT model option is present but disabled; continuing without switching "
                    f"(wanted={model_key}, current={current!r}).",
                )
                try:
                    await page.keyboard.press("Escape")
                except Exception:
                    pass
                await _human_pause(page)
                return

            raise RuntimeError(
                "ChatGPT model option is present but disabled (cannot switch). "
                f"wanted={model_key} current={current!r}"
            )
        await item.click()
    else:
        # Fallback: match by visible label (UI A/B tests sometimes remove/rename data-testid values).
        if model_key.endswith("-pro"):
            label_re = re.compile(r"\bPro\b", re.I)
        elif model_key.endswith("-thinking"):
            label_re = re.compile(r"\bThinking\b", re.I)
        elif model_key.endswith("-instant"):
            label_re = re.compile(r"\bInstant\b", re.I)
        else:
            label_re = re.compile(r"\bAuto\b|\bChatGPT\s*5\.2\b", re.I)

        radios = menu.locator("[role='menuitemradio']")
        clicked = False
        for i in range(await radios.count()):
            radio = radios.nth(i)
            text = " ".join(((await radio.inner_text()) or "").split())
            if label_re.search(text):
                await radio.click()
                clicked = True
                break
        if not clicked:
            # Last resort: scan any buttons inside the menu.
            buttons = menu.locator("button")
            for i in range(await buttons.count()):
                btn = buttons.nth(i)
                text = " ".join(((await btn.inner_text()) or "").split())
                if label_re.search(text):
                    await btn.click()
                    clicked = True
                    break
        if not clicked:
            await page.keyboard.press("Escape")
            await _human_pause(page)
            if _chatgpt_model_switch_fail_open():
                await _ctx_info(
                    ctx,
                    "Model option not found in selector menu; continuing without switching "
                    f"(wanted={model_key}, current={current!r}, testid={wanted_testid}).",
                )
                return
            raise RuntimeError(
                f"Model option not found in selector menu (wanted={model_key}, testid={wanted_testid}). "
                f"Menu text: {((await menu.inner_text()) or '').strip()[:500]}"
            )

    await _human_pause(page)
    await page.keyboard.press("Escape")
    await _human_pause(page)

    # Verify the model actually switched (ChatGPT may ignore the click in some conversation modes).
    last_seen = ""
    for _ in range(12):
        last_seen = await _current_model_text(page)
        if _model_text_matches_key(model_key, last_seen):
            return
        await page.wait_for_timeout(250)
    if _chatgpt_model_switch_fail_open():
        await _ctx_info(ctx, f"Model switch did not apply; continuing without switching (wanted={model_key}, current={last_seen!r}).")
        return
    raise RuntimeError(f"Model switch did not apply (wanted={model_key}, current={last_seen!r}).")


_THINKING_TIME_LABEL_BY_KEY: dict[str, str] = {
    "light": "Light",
    "standard": "Standard",
    "extended": "Extended",
    "heavy": "Heavy",
}

# Deep research "pill" text varies across UI experiments; keep this regex non-anchored so we still match
# when additional screen-reader text (or icons) are present in the same button.
_DEEP_RESEARCH_PILL_RE = re.compile(r"(Research|Deep\s*research|研究|深度研究|深度调研|深入研究)", re.I)


def _normalize_thinking_time_key(value: str) -> str:
    normalized = re.sub(r"[^a-z]+", "", value.strip().lower())
    if normalized in {"light", "standard", "extended", "heavy"}:
        return normalized
    raise ValueError(f"Unsupported thinking_time: {value}")

def _chatgpt_pro_default_thinking_time() -> str:
    """
    Default thinking_time when model=Pro and caller didn't specify thinking_time.

    Best-effort: some modes (e.g. Research) may hide the thinking-time UI. In that case
    we log and continue rather than failing the entire tool call.
    """
    raw = (os.environ.get("CHATGPT_PRO_DEFAULT_THINKING_TIME") or "").strip()
    return raw or "extended"


async def _current_thinking_time_key(page) -> str | None:
    pills = _composer_pills(page).filter(has_text=re.compile(r"(thinking\b|^Pro$)", re.I))
    if not await pills.count():
        return None

    pill = pills.first
    await pill.click()
    await _human_pause(page)

    menu = page.locator("[role='menu']").first
    await menu.wait_for(state="visible", timeout=10_000)

    radios = menu.locator("[role='menuitemradio']")
    radio_count = await radios.count()
    selected_label = None
    for i in range(radio_count):
        radio = radios.nth(i)
        aria_checked = (await radio.get_attribute("aria-checked")) or ""
        if aria_checked.strip().lower() == "true":
            selected_label = " ".join(((await radio.inner_text()) or "").split())
            break

    await page.keyboard.press("Escape")
    await _human_pause(page)

    if not selected_label:
        return None
    for key, label in _THINKING_TIME_LABEL_BY_KEY.items():
        if re.search(rf"\b{re.escape(label)}\b", selected_label, re.I):
            return key
    return None


async def _ensure_thinking_time(page, *, thinking_time: str, ctx: Context | None) -> None:
    wanted_key = _normalize_thinking_time_key(thinking_time)
    pills = _composer_pills(page).filter(has_text=re.compile(r"(thinking\b|^Pro$)", re.I))
    label = _THINKING_TIME_LABEL_BY_KEY[wanted_key]

    if not await pills.count():
        # The thinking-time control has been A/B-tested and can be absent in some modes
        # (notably Research/Deep Research) or UI variants. Proceed best-effort so
        # callers can still send/await the prompt instead of failing hard.
        try:
            research = _composer_pills(page).filter(has_text=_DEEP_RESEARCH_PILL_RE).first
            if await research.count() and await research.is_visible():
                await _ctx_info(ctx, f"Thinking time not configurable in Research mode (wanted: {wanted_key})")
                return
        except Exception:
            pass
        await _ctx_info(ctx, f"Thinking time control not found (wanted: {wanted_key}); continuing best-effort.")
        return

    try:
        pill = pills.first
        await pill.click()
        await _human_pause(page)

        menu = page.locator("[role='menu']").first
        await menu.wait_for(state="visible", timeout=10_000)

        option = menu.locator("[role='menuitemradio']").filter(has_text=re.compile(rf"^{re.escape(label)}$", re.I)).first
        if not await option.count():
            await page.keyboard.press("Escape")
            await _human_pause(page)
            await _ctx_info(
                ctx,
                f"Thinking time option not available (wanted: {wanted_key}, label: {label}); continuing best-effort.",
            )
            return

        aria_checked = (await option.get_attribute("aria-checked")) or ""
        if aria_checked.strip().lower() != "true":
            await option.click()
            await _human_pause(page)
        await page.keyboard.press("Escape")
        await _human_pause(page)

        await _ctx_info(ctx, f"Thinking time → {wanted_key}")
    except Exception as exc:
        try:
            await page.keyboard.press("Escape")
            await _human_pause(page)
        except Exception:
            pass
        await _ctx_info(ctx, f"Thinking time not applied (wanted: {wanted_key}, label: {label}): {exc}")
        return


async def _ensure_deep_research(page, *, ctx: Context | None) -> None:
    pill = _composer_pills(page).filter(has_text=_DEEP_RESEARCH_PILL_RE).first
    if await pill.count() and await pill.is_visible():
        return

    deep_item_re = re.compile(r"^\s*(Deep\s*research|深度研究|深度调研|深入研究)\s*$", re.I)

    # 1) Best-effort: older UI exposes Deep research under the "+" composer menu.
    try:
        menu = await _open_plus_menu(page)

        # Best-effort: some UI variants localize or nest this under More/更多.
        wanted = re.compile(r"^\s*(Deep\s*research|Research|研究|深度研究|深入研究|深度调研|深入调研)\s*$", re.I)

        query = menu.locator("input[placeholder^='Search'], input[placeholder*='搜索']").first
        if await query.count():
            try:
                await query.click()
                await _human_pause(page)
                await query.fill("research")
                await _human_pause(page)
            except Exception:
                pass

        item = menu.locator("[role='menuitemradio'], [role='menuitem']").filter(has_text=wanted).first
        if not await item.count():
            more = menu.locator("[role='menuitem']:visible").filter(has_text=re.compile(r"^(More|更多)$", re.I)).first
            if await more.count():
                try:
                    await more.wait_for(state="visible", timeout=10_000)
                except Exception:
                    pass

                # A/B tests: some builds open submenus on click (not hover). Try hover first, then click.
                try:
                    handle = await more.element_handle()
                    if handle is not None:
                        await handle.hover()
                        await page.wait_for_timeout(300)
                        await _human_pause(page)
                except Exception:
                    pass
                try:
                    expanded = ((await more.get_attribute("aria-expanded")) or "").strip().lower() == "true"
                except Exception:
                    expanded = False
                if not expanded:
                    try:
                        await more.click()
                        await _human_pause(page)
                    except Exception:
                        pass

                submenus = page.locator("[role='menu']:visible")
                subitem = submenus.locator("[role='menuitemradio'], [role='menuitem']").filter(has_text=wanted).first
                if await subitem.count():
                    item = subitem

        if not await item.count():
            raise RuntimeError("Cannot find Deep research in the + menu.")

        await item.wait_for(state="visible", timeout=10_000)
        try:
            await item.locator("xpath=ancestor-or-self::*[@role='menuitemradio' or @role='menuitem'][1]").click(timeout=10_000)
        except Exception:
            await item.click(timeout=10_000)
        await _human_pause(page)

        pill = _composer_pills(page).filter(has_text=_DEEP_RESEARCH_PILL_RE).first
        await pill.wait_for(state="visible", timeout=10_000)
        await _ctx_info(ctx, "Enabled Deep research")
        return
    except Exception as exc:
        await _ctx_info(ctx, f"Deep research not enabled via + menu (best-effort): {type(exc).__name__}: {exc}")
    finally:
        # Close any open menus (best-effort) before trying other navigation paths.
        try:
            await page.keyboard.press("Escape")
            await _human_pause(page)
        except Exception:
            pass

    # 2) Newer UI exposes Deep research as a sidebar entry (and/or a dedicated route).
    await _ctx_info(ctx, "Deep research not found in + menu; trying sidebar/route…")
    clicked = False
    for selector in [
        "a[data-testid='deep-research-sidebar-item']",
        "button[data-testid='deep-research-sidebar-item']",
        "a[href='/deep-research']",
        "a[href*='deep-research']",
        "button[aria-label='Deep research']",
        "a[aria-label='Deep research']",
    ]:
        loc = page.locator(selector).first
        try:
            if await loc.count() and await loc.is_visible():
                await loc.click()
                await _human_pause(page)
                clicked = True
                break
        except Exception:
            continue

    if not clicked:
        try:
            await _goto_with_retry(page, "https://chatgpt.com/deep-research", ctx=ctx)
            await _human_pause(page)
        except Exception as exc:
            raise RuntimeError(f"Cannot navigate to Deep research page: {type(exc).__name__}: {exc}") from exc

    # Ensure composer is ready again after navigation.
    await _find_prompt_box(page, timeout_ms=60_000)
    pill = _composer_pills(page).filter(has_text=_DEEP_RESEARCH_PILL_RE).first
    await pill.wait_for(state="visible", timeout=10_000)
    await _ctx_info(ctx, "Enabled Deep research")


async def _ensure_web_search(page, *, ctx: Context | None) -> None:

    pill = _composer_pills(page).filter(has_text=re.compile(r"^(Web search|Search|网页搜索|联网搜索)$", re.I)).first
    if await pill.count() and await pill.is_visible():
        return

    menu = await _open_plus_menu(page)

    query = menu.locator("input[placeholder^='Search'], input[placeholder*='搜索']").first
    if await query.count():
        await query.click()
        await _human_pause(page)
        await query.fill("search")
        await _human_pause(page)

    wanted = re.compile(r"(Web\s*search|Search\s+the\s+web|Browse\s+the\s+web|网页搜索|联网搜索)", re.I)
    item = menu.locator("[role='menuitemradio'], [role='menuitem']").filter(has_text=wanted).first
    if await item.count():
        await item.wait_for(state="visible", timeout=10_000)
        await item.click()
        await _human_pause(page)
    else:
        more = menu.locator("[role='menuitem']:visible").filter(has_text=re.compile(r"^(More|更多)$", re.I)).first
        if await more.count():
            try:
                await more.wait_for(state="visible", timeout=10_000)
            except Exception:
                pass

            # A/B tests: some builds open submenus on click (not hover). Try hover first, then click.
            try:
                handle = await more.element_handle()
                if handle is not None:
                    await handle.hover()
                    await page.wait_for_timeout(300)
                    await _human_pause(page)
            except Exception:
                pass
            try:
                expanded = ((await more.get_attribute("aria-expanded")) or "").strip().lower() == "true"
            except Exception:
                expanded = False
            if not expanded:
                try:
                    await more.click()
                    await _human_pause(page)
                except Exception:
                    pass

            submenus = page.locator("[role='menu']:visible")
            subitem = submenus.locator("[role='menuitemradio'], [role='menuitem']").filter(has_text=wanted).first
            if await subitem.count():
                await subitem.wait_for(state="visible", timeout=10_000)
                await subitem.click()
                await _human_pause(page)

    pill = _composer_pills(page).filter(has_text=re.compile(r"^(Web search|Search|网页搜索|联网搜索)$", re.I)).first
    await pill.wait_for(state="visible", timeout=10_000)
    await _ctx_info(ctx, "Enabled Web search")


async def _ensure_agent_mode(page, *, ctx: Context | None) -> None:
    pill = _composer_pills(page).filter(
        has_text=re.compile(r"(Agent\s*mode|Agent|代理模式|代理)", re.I)
    ).first
    if await pill.count() and await pill.is_visible():
        return

    menu = await _open_plus_menu(page)

    wanted = re.compile(r"(Agent\s*mode|Agent|代理模式|代理)", re.I)
    item = menu.locator("[role='menuitemradio'], [role='menuitem']").filter(has_text=wanted).first
    if not await item.count():
        more = menu.locator("[role='menuitem']:visible").filter(has_text=re.compile(r"^(More|更多)$", re.I)).first
        if await more.count():
            try:
                await more.wait_for(state="visible", timeout=10_000)
            except Exception:
                pass
            try:
                handle = await more.element_handle()
                if handle is not None:
                    await handle.hover()
                    await page.wait_for_timeout(300)
                    await _human_pause(page)
            except Exception:
                pass
            try:
                expanded = ((await more.get_attribute("aria-expanded")) or "").strip().lower() == "true"
            except Exception:
                expanded = False
            if not expanded:
                try:
                    await more.click()
                    await _human_pause(page)
                except Exception:
                    pass

            submenus = page.locator("[role='menu']:visible")
            subitem = submenus.locator("[role='menuitemradio'], [role='menuitem']").filter(has_text=wanted).first
            if await subitem.count():
                item = subitem

    if not await item.count():
        await page.keyboard.press("Escape")
        await _human_pause(page)
        raise RuntimeError("Cannot find Agent mode (代理模式) in the + menu.")

    await item.wait_for(state="visible", timeout=10_000)
    await item.click()
    await _human_pause(page)

    pill = _composer_pills(page).filter(
        has_text=re.compile(r"(Agent\s*mode|Agent|代理模式|代理)", re.I)
    ).first
    await pill.wait_for(state="visible", timeout=10_000)
    await _ctx_info(ctx, "Enabled Agent mode")


async def _ensure_create_image(page, *, ctx: Context | None) -> None:
    menu = await _open_plus_menu(page)

    create = menu.locator("[role='menuitemradio']").filter(has_text=re.compile(r"^Create image$", re.I)).first
    if not await create.count():
        create = menu.locator("[role='menuitem']").filter(has_text=re.compile(r"^Create image$", re.I)).first
    if not await create.count():
        create = menu.locator("[role='menuitemradio'], [role='menuitem']").filter(has_text=re.compile(r"Create image", re.I)).first
    await create.wait_for(state="visible", timeout=10_000)
    await create.click()
    await _human_pause(page)
    await _ctx_info(ctx, "Enabled Create image")


async def _find_upload_menu_item(page, menu) -> Any:
    wanted = re.compile(r"(Upload|Add|Attach).{0,24}(file|files)|上传文件|添加文件|附件", re.I)
    items = menu.locator("[role='menuitemradio'], [role='menuitem'], [role='menuitemcheckbox']").filter(has_text=wanted)
    count = await items.count()
    for idx in range(min(5, count)):
        cand = items.nth(idx)
        try:
            if await cand.is_visible():
                return cand
        except Exception:
            continue
    if count:
        return items.first

    more = menu.locator("[role='menuitem']:visible").filter(has_text=re.compile(r"^(More|更多)$", re.I)).first
    if await more.count():
        handle = await more.element_handle()
        if handle is not None:
            try:
                await handle.hover()
                await page.wait_for_timeout(300)
                await _human_pause(page)
            except PlaywrightTimeoutError:
                pass
        submenus = page.locator("[role='menu']:visible")
        subitem = (
            submenus.locator("[role='menuitemradio'], [role='menuitem'], [role='menuitemcheckbox']")
            .filter(has_text=wanted)
            .first
        )
        if await subitem.count():
            return subitem

    raise RuntimeError("Cannot find Upload file in the + menu.")


def _upload_filename_matchers(filename: str) -> list[object]:
    """
    Return a list of get_by_text matchers (strings or regex patterns) for a filename
    as rendered by the ChatGPT composer.

    ChatGPT often truncates long filenames and may insert ellipsis characters, so
    matching the full filename string is unreliable.
    """
    name = str(filename or "").strip()
    if not name:
        return []

    # Always try the full name (works when DOM keeps full text but visually ellipsizes).
    out: list[object] = [name]

    stem, ext = os.path.splitext(name)
    stem = stem.strip()
    ext = ext.strip()

    if stem:
        out.append(stem)
        # Some UIs keep only the extension (".pdf") or only a suffix/prefix.
        if ext:
            out.append(stem + ext)

        # Truncation-aware patterns: prefix … suffix (optionally with extension).
        # Keep the regex bounded to avoid accidental huge matches.
        if len(stem) >= 12:
            prefix_len = min(12, len(stem))
            suffix_len = min(12, len(stem))
            prefix = stem[:prefix_len]
            suffix = stem[-suffix_len:]
            mid = r".{0,120}"
            candidates: list[re.Pattern[str]] = [
                re.compile(re.escape(prefix) + mid + re.escape(suffix) + re.escape(ext), re.I),
                re.compile(re.escape(prefix) + mid + re.escape(suffix), re.I),
                re.compile(re.escape(prefix) + mid + re.escape(ext), re.I) if ext else re.compile(re.escape(prefix) + mid, re.I),
                re.compile(re.escape(suffix) + re.escape(ext), re.I) if ext else re.compile(re.escape(suffix), re.I),
            ]
            out.extend(candidates)
        elif len(stem) >= 6:
            # Shorter names: try partial prefix/suffix.
            prefix = stem[: min(8, len(stem))]
            suffix = stem[-min(8, len(stem)) :]
            out.append(prefix)
            out.append(suffix + ext if ext else suffix)

    # De-dup while preserving order.
    seen: set[str] = set()
    unique: list[object] = []
    for m in out:
        key = repr(m)
        if key in seen:
            continue
        seen.add(key)
        unique.append(m)
    return unique


async def _composer_shows_uploaded_file(page, *, file_path: Path, timeout_ms: int, ctx: Context | None) -> bool:
    """
    Best-effort confirmation that the composer UI registered an uploaded file.

    This is intentionally tolerant: if we can confirm via the file input element but
    can't locate a UI chip reliably (A/B tests), we return False and let the send
    path's disabled-send-button wait absorb the remaining upload time.
    """
    wanted = str(file_path.name or "").strip()
    if not wanted:
        return False

    # Quick signal: confirm via *composer-scoped* file inputs only.
    # (Avoid false positives from unrelated hidden file inputs elsewhere on the page.)
    try:
        selected = await page.evaluate(
            """(wantedName) => {
  try {
    const scopes = [];

    // Find the nearest <form> containing the prompt textarea.
    const prompt = document.querySelector('#prompt-textarea');
    if (prompt) {
      let el = prompt;
      while (el && el.parentElement) {
        if (el.tagName && el.tagName.toLowerCase() === 'form') {
          scopes.push(el);
          break;
        }
        el = el.parentElement;
      }
    }

    const unified = document.querySelector('[data-type=\"unified-composer\"]');
    if (unified) scopes.push(unified);

    const bottom = document.querySelector('#thread-bottom');
    if (bottom) scopes.push(bottom);

    const seen = new Set();
    for (const scope of scopes) {
      if (!scope) continue;
      if (seen.has(scope)) continue;
      seen.add(scope);
      const inputs = Array.from(scope.querySelectorAll('input[type=\"file\"]'));
      for (const input of inputs) {
        try {
          const files = input && input.files;
          if (!files) continue;
          for (const f of files) {
            if (f && f.name === wantedName) return true;
          }
        } catch {}
      }
    }
  } catch {}
  return false;
}""",
            wanted,
        )
        if bool(selected):
            return True
    except Exception:
        pass

    scopes = [
        page.locator("#thread-bottom"),
        page.locator("form:has(#prompt-textarea)"),
        page.locator("[data-type='unified-composer']"),
    ]
    matchers = _upload_filename_matchers(wanted)
    deadline = time.time() + max(0.5, float(timeout_ms) / 1000.0)
    while time.time() < deadline:
        for scope in scopes:
            try:
                if not await scope.count():
                    continue
            except Exception:
                continue
            for m in matchers:
                try:
                    loc = scope.get_by_text(m, exact=False).first
                    if await loc.count() and await loc.is_visible():
                        return True
                except Exception:
                    continue
        await page.wait_for_timeout(300)

    await _ctx_info(ctx, f"Upload confirmation not found in UI for: {wanted}")
    return False


async def _upload_file_via_menu(page, *, file_path: Path, ctx: Context | None) -> bool:
    # Prefer direct composer input on modern ChatGPT UI (more stable than the "+" menu).
    # The "+" menu frequently A/B tests and may not contain an "Upload file" entry for generic attachments.
    try:
        existing = page.get_by_text(file_path.name, exact=False).first
        if await existing.count() and await existing.is_visible():
            return True
    except Exception:
        pass

    is_image = file_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"}
    set_files_timeout_ms = max(30_000, _env_int("CHATGPT_UPLOAD_SET_INPUT_FILES_TIMEOUT_MS", 180_000))
    confirm_timeout_ms = max(10_000, _env_int("CHATGPT_UPLOAD_CONFIRM_TIMEOUT_MS", 60_000))
    require_confirm = _truthy_env("CHATGPT_UPLOAD_REQUIRE_CONFIRM", False)
    inputs = page.locator("form:has(#prompt-textarea) input[type='file']")
    if not await inputs.count():
        inputs = page.locator("[data-type='unified-composer'] input[type='file']")
    chosen = None
    try:
        for idx in range(min(6, await inputs.count())):
            cand = inputs.nth(idx)
            cand_id = (await cand.get_attribute("id")) or ""
            if cand_id.strip().lower().startswith("upload-"):
                continue
            accept = (await cand.get_attribute("accept")) or ""
            if (not is_image) and accept.strip().lower().startswith("image/"):
                continue
            chosen = cand
            break
    except Exception:
        chosen = None
    if chosen is not None:
        await chosen.set_input_files(str(file_path), timeout=set_files_timeout_ms)
        await _human_pause(page)
        try:
            await page.keyboard.press("Escape")
            await _human_pause(page)
        except Exception:
            pass
        # Avoid strict full-filename waits: ChatGPT often truncates filenames in the composer.
        confirmed = await _composer_shows_uploaded_file(page, file_path=file_path, timeout_ms=confirm_timeout_ms, ctx=ctx)
        if require_confirm and not confirmed:
            raise RuntimeError(f"Upload not confirmed in UI: {file_path.name}")
        return bool(confirmed)

    menu = await _open_plus_menu(page)
    item = await _find_upload_menu_item(page, menu)

    try:
        async with page.expect_file_chooser(timeout=8_000) as fc_info:
            await item.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(str(file_path))
    except PlaywrightTimeoutError:
        try:
            await item.click()
        except Exception:
            pass
        await _human_pause(page)
        inputs = page.locator("input[type='file']")
        count = await inputs.count()
        if not count:
            raise TimeoutError("Upload file clicked but no file input was found.")
        await inputs.nth(count - 1).set_input_files(str(file_path), timeout=set_files_timeout_ms)

    await _human_pause(page)
    try:
        await page.keyboard.press("Escape")
        await _human_pause(page)
    except Exception:
        pass

    # Avoid strict full-filename waits: ChatGPT often truncates filenames in the composer.
    confirmed = await _composer_shows_uploaded_file(page, file_path=file_path, timeout_ms=confirm_timeout_ms, ctx=ctx)
    if require_confirm and not confirmed:
        raise RuntimeError(f"Upload not confirmed in UI: {file_path.name}")
    return bool(confirmed)


async def _ensure_github_connector(page, *, ctx: Context | None) -> None:
    pill = _composer_pills(page).filter(has_text=re.compile(r"^GitHub$", re.I)).first
    if await pill.count() and await pill.is_visible():
        return

    menu = await _open_plus_menu(page)

    more = menu.locator("[role='menuitem']:visible").filter(has_text=re.compile(r"\bMore\b", re.I)).first
    await more.wait_for(state="visible", timeout=10_000)

    submenu = page.locator("[role='menu']:visible").filter(has_text=re.compile(r"GitHub", re.I)).first

    async def _hover_more_once() -> None:
        try:
            expanded = ((await more.get_attribute("aria-expanded")) or "").strip().lower() == "true"
        except Exception:
            expanded = False
        if not expanded:
            try:
                await more.click()
                await _human_pause(page)
            except Exception:
                pass
        handle = await more.element_handle()
        if handle is None:
            return
        try:
            await handle.hover()
        except PlaywrightTimeoutError:
            return
        await page.wait_for_timeout(300)

    await _hover_more_once()
    try:
        await submenu.wait_for(state="visible", timeout=12_000)
    except PlaywrightTimeoutError:
        await _human_pause(page)
        await _hover_more_once()
        await submenu.wait_for(state="visible", timeout=12_000)

    github = submenu.locator("[role^='menuitem']").filter(has_text=re.compile(r"^GitHub$", re.I)).first
    if not await github.count():
        github = submenu.get_by_text("GitHub", exact=True).first
    await github.wait_for(state="visible", timeout=10_000)
    await github.click()
    await _human_pause(page)

    pill = _composer_pills(page).filter(has_text=re.compile(r"^GitHub$", re.I)).first
    await pill.wait_for(state="visible", timeout=10_000)
    await _ctx_info(ctx, "Enabled GitHub connector")


async def _open_github_repo_menu(page) -> Any:
    pill = _composer_pills(page).filter(has_text=re.compile(r"^GitHub$", re.I)).first
    await pill.wait_for(state="visible", timeout=10_000)
    await pill.click()
    await _human_pause(page)

    menus = page.locator("[role='menu']:visible, [role='listbox']:visible")
    menu_with_search = menus.filter(has=page.locator("input[placeholder^='Search']")).first
    if await menu_with_search.count():
        await menu_with_search.wait_for(state="visible", timeout=10_000)
        return menu_with_search

    menu = menus.first
    await menu.wait_for(state="visible", timeout=10_000)
    return menu


_GITHUB_INDEX_WAIT_SECONDS = int(os.environ.get("CHATGPT_GITHUB_INDEX_WAIT_SECONDS", "1200"))
_GITHUB_INDEX_POLL_INTERVAL = 60  # seconds between retry polls


async def _select_github_repo(page, *, repo: str, ctx: Context | None) -> None:
    menu = await _open_github_repo_menu(page)

    search = menu.locator("input[placeholder^='Search']").first
    if await search.count():
        await search.click()
        await _human_pause(page)
        await search.fill(repo)
        await _human_pause(page)

    deadline = time.time() + 20
    target = None
    while time.time() < deadline:
        candidate = menu.locator("[role='menuitem']").filter(has_text=re.compile(re.escape(repo), re.I)).first
        if await candidate.count() and await candidate.is_visible():
            target = candidate
            break
        await page.wait_for_timeout(500)

    if target is None:
        raise RuntimeError(f"GitHub repo not found in picker: {repo}")

    await target.click()
    await _human_pause(page)

    # Check for indexing modal — if repo is not yet indexed, wait for it.
    indexing_modal = page.locator("[data-testid='modal-github-indexing']").first
    if await indexing_modal.count() and await indexing_modal.is_visible():
        # Close the modal first.
        close_btn = indexing_modal.locator("button[aria-label='Close']").first
        if await close_btn.count():
            await close_btn.click()
            await _human_pause(page)

        await _ctx_info(ctx, f"GitHub repo indexing triggered for '{repo}', waiting up to {_GITHUB_INDEX_WAIT_SECONDS}s...")

        index_deadline = time.time() + _GITHUB_INDEX_WAIT_SECONDS
        indexed = False
        attempt = 0
        while time.time() < index_deadline:
            attempt += 1
            remaining = int(index_deadline - time.time())
            await _ctx_info(ctx, f"GitHub indexing wait: attempt {attempt}, {remaining}s remaining...")
            await page.wait_for_timeout(_GITHUB_INDEX_POLL_INTERVAL * 1000)

            # Dismiss any lingering menu/modal.
            try:
                await page.keyboard.press("Escape")
                await _human_pause(page)
            except Exception:
                pass

            # Re-open repo picker, search, click.
            try:
                menu = await _open_github_repo_menu(page)
                search = menu.locator("input[placeholder^='Search']").first
                if await search.count():
                    await search.click()
                    await _human_pause(page)
                    await search.fill(repo)
                    await _human_pause(page)

                retry_deadline = time.time() + 10
                target = None
                while time.time() < retry_deadline:
                    candidate = menu.locator("[role='menuitem']").filter(
                        has_text=re.compile(re.escape(repo), re.I)
                    ).first
                    if await candidate.count() and await candidate.is_visible():
                        target = candidate
                        break
                    await page.wait_for_timeout(500)

                if target is None:
                    continue

                await target.click()
                await _human_pause(page)

                # Check if indexing modal reappears.
                indexing_modal = page.locator("[data-testid='modal-github-indexing']").first
                if await indexing_modal.count() and await indexing_modal.is_visible():
                    # Still indexing — close modal and continue waiting.
                    close_btn = indexing_modal.locator("button[aria-label='Close']").first
                    if await close_btn.count():
                        await close_btn.click()
                        await _human_pause(page)
                    continue

                # No indexing modal → repo is ready!
                indexed = True
                break
            except Exception as exc:
                await _ctx_info(ctx, f"GitHub indexing retry error: {exc}")
                continue

        if not indexed:
            raise RuntimeError(
                f"GitHub repo indexing timed out after {_GITHUB_INDEX_WAIT_SECONDS}s: {repo}. "
                f"Try again later or manually activate in the ChatGPT UI."
            )

        await _ctx_info(ctx, f"GitHub repo indexing completed: {repo}")

    await page.keyboard.press("Escape")
    await _human_pause(page)

    await _ctx_info(ctx, f"GitHub repo selected: {repo}")



async def _prompt_box_text(prompt) -> str | None:
    try:
        return (await prompt.input_value(timeout=2_000)).strip()
    except Exception:
        pass
    try:
        return (await prompt.inner_text(timeout=2_000)).strip()
    except Exception:
        pass
    try:
        value = await prompt.evaluate("el => (el && (el.value || el.innerText || el.textContent) || '')")
        if isinstance(value, str):
            return value.strip()
    except Exception:
        pass
    return None


async def _wait_for_send_button_enabled(send_btn, *, timeout_ms: int = 30_000) -> bool:
    deadline = time.time() + max(0.2, timeout_ms / 1000)
    while time.time() < deadline:
        try:
            if await send_btn.count() and await send_btn.is_visible() and await send_btn.is_enabled():
                return True
        except Exception:
            pass
        await asyncio.sleep(0.25)
    return False


async def _find_regenerate_control(page, *, timeout_ms: int = 8_000) -> Any:
    deadline = time.time() + max(0.5, timeout_ms / 1000.0)
    locator = page.locator("button, a, [role='button'], [role='link'], input[type='button']").filter(
        has_text=_CHATGPT_REGENERATE_TEXT_RE
    )
    while time.time() < deadline:
        try:
            count = await locator.count()
        except Exception:
            count = 0
        if count > 0:
            for i in reversed(range(min(count, 20))):
                item = locator.nth(i)
                try:
                    if not await item.is_visible():
                        continue
                except Exception:
                    continue
                try:
                    # Some controls report enabled state; ignore errors for non-buttons.
                    if await item.is_enabled() is False:
                        continue
                except Exception:
                    pass
                return item
        await page.wait_for_timeout(200)
    raise RuntimeError("Cannot find Regenerate button/control. Is the last message eligible for regeneration?")


_CHATGPT_PROMPT_BOX_SELECTORS = [
    "textarea#prompt-textarea",
    "div#prompt-textarea[contenteditable='true']",
    "textarea[data-testid='prompt-textarea']",
    "div[contenteditable='true']#prompt-textarea",
    "div[contenteditable='true'][id='prompt-textarea']",
    "div[contenteditable='true']",
    "textarea",
]
_CHATGPT_SEND_BUTTON_SELECTOR = "button[data-testid='send-button'], button[aria-label='Send prompt']"
_CHATGPT_ASSISTANT_SELECTOR = "[data-message-author-role='assistant']"
_CHATGPT_USER_SELECTOR = "[data-message-author-role='user']"
_CHATGPT_STOP_BUTTON_SELECTOR = (
    "button[data-testid='stop-button'], "
    "button[aria-label='Stop generating'], "
    "button[aria-label='Stop'], "
    "button[aria-label='停止生成'], "
    "button[aria-label='停止']"
)
_CHATGPT_PLUS_BUTTON_SELECTOR = "button[data-testid='composer-plus-btn'], button[aria-label='Add files and more']"
_CHATGPT_REGENERATE_TEXT_RE = re.compile(
    r"("
    r"Regenerate|"
    r"Regenerate response|"
    r"Try again|"
    r"Retry|"
    r"重新生成|"
    r"再试一次|"
    r"重试"
    r")",
    re.I,
)


async def _find_prompt_box(page, *, timeout_ms: int = 15_000) -> Any:
    candidates = _CHATGPT_PROMPT_BOX_SELECTORS
    deadline = time.time() + max(0.5, timeout_ms / 1000)
    while time.time() < deadline:
        for selector in candidates:
            locator = page.locator(selector)
            count = await locator.count()
            if count <= 0:
                continue
            for i in range(min(count, 5)):
                item = locator.nth(i)
                try:
                    if await item.is_visible():
                        return item
                except PlaywrightTimeoutError:
                    continue
        await page.wait_for_timeout(200)
    raise RuntimeError("Cannot find prompt textarea. Are you logged in?")


def _chatgpt_reuse_existing_cdp_page() -> bool:
    return _truthy_env("CHATGPT_REUSE_EXISTING_CDP_PAGE", True)


async def _chatgpt_has_visible_prompt_box(page, *, timeout_ms: int = 1_500) -> bool:
    deadline = time.time() + max(0.2, timeout_ms / 1000.0)
    while time.time() < deadline:
        for selector in _CHATGPT_PROMPT_BOX_SELECTORS:
            locator = page.locator(selector)
            try:
                count = await locator.count()
            except Exception:
                count = 0
            if count <= 0:
                continue
            for i in range(min(count, 5)):
                item = locator.nth(i)
                try:
                    if await item.is_visible():
                        return True
                except Exception:
                    continue
        await page.wait_for_timeout(150)
    return False


async def _chatgpt_pick_existing_cdp_page(
    context,
    *,
    conversation_url: str | None,
    ctx: Context | None,
) -> Any | None:
    if not _chatgpt_reuse_existing_cdp_page():
        return None

    target_conv_id = _chatgpt_conversation_id_from_url(str(conversation_url or "").strip())
    pages = list(getattr(context, "pages", []) or [])
    fallback = None
    for existing in reversed(pages):
        try:
            current_url = str(existing.url or "").strip()
        except Exception:
            current_url = ""
        if not re.match(r"^https?://(?:chatgpt\.com|chat\.openai\.com)(?:/|$)", current_url, re.I):
            continue
        if target_conv_id:
            current_conv_id = _chatgpt_conversation_id_from_url(current_url)
            if current_conv_id != target_conv_id:
                continue
        try:
            title, url, body = await _chatgpt_page_snapshot(existing)
            signals = await _chatgpt_cloudflare_signals(existing, title=title, url=url, body=body)
        except Exception:
            continue
        if signals:
            continue
        if target_conv_id:
            await _ctx_info(ctx, f"Reusing existing ChatGPT CDP page for conversation {target_conv_id}.")
            return existing
        has_prompt = False
        try:
            has_prompt = await _chatgpt_has_visible_prompt_box(existing, timeout_ms=1_200)
        except Exception:
            has_prompt = False
        if has_prompt:
            await _ctx_info(ctx, "Reusing existing healthy ChatGPT CDP page with visible prompt box.")
            return existing
        if fallback is None:
            fallback = existing
    return fallback if target_conv_id else None


async def _extract_assistant_text(assistant_message) -> str:
    for selector in ["div.markdown", "div.prose", "[data-testid='markdown']"]:
        content = assistant_message.locator(selector)
        if await content.count():
            try:
                text = (await content.first.inner_text(timeout=2_000)).strip()
            except PlaywrightTimeoutError:
                continue
            if text:
                return text
    try:
        return (await assistant_message.inner_text(timeout=2_000)).strip()
    except PlaywrightTimeoutError:
        return ""


_CHATGPT_CLIPBOARD_CAPTURE_INIT_JS = r"""
() => {
  // Idempotent install.
  if (!window.__clipboardCapture) {
    window.__clipboardCapture = { text: null, calls: 0, lastError: null, lastKind: null };
  } else {
    window.__clipboardCapture.text = null;
    window.__clipboardCapture.lastError = null;
    window.__clipboardCapture.lastKind = null;
  }
  if (window.__clipboardCaptureInstalled) return;
  window.__clipboardCaptureInstalled = true;

  const cb = navigator.clipboard;
  if (!cb) return;

  // Hook writeText(text)
  if (typeof cb.writeText === "function") {
    const origWriteText = cb.writeText.bind(cb);
    cb.writeText = async (text) => {
      try {
        window.__clipboardCapture.text = String(text);
        window.__clipboardCapture.calls++;
        window.__clipboardCapture.lastKind = "writeText";
      } catch {}
      try {
        return await origWriteText(text);
      } catch (e) {
        try { window.__clipboardCapture.lastError = String(e); } catch {}
        return;
      }
    };
  }

  // Hook write(ClipboardItem[])
  if (typeof cb.write === "function") {
    const origWrite = cb.write.bind(cb);
    cb.write = async (items) => {
      try {
        if (Array.isArray(items)) {
          for (const item of items) {
            if (item && item.types && item.types.includes("text/plain")) {
              const blob = await item.getType("text/plain");
              const text = await blob.text();
              window.__clipboardCapture.text = String(text);
              window.__clipboardCapture.calls++;
              window.__clipboardCapture.lastKind = "write";
              break;
            }
          }
        }
      } catch {}
      try {
        return await origWrite(items);
      } catch (e) {
        try { window.__clipboardCapture.lastError = String(e); } catch {}
        return;
      }
    };
  }
};
"""


_CHATGPT_CLIPBOARD_CAPTURE_READ_JS = r"""
() => {
  const cap = window.__clipboardCapture;
  return cap && typeof cap.text === "string" ? cap.text : null;
};
"""


async def _chatgpt_best_effort_last_assistant_raw_markdown(
    page, *, timeout_ms: int = 6_000, question: str | None = None
) -> str | None:
    assistant = page.locator(_CHATGPT_ASSISTANT_SELECTOR)
    if await assistant.count() <= 0:
        return None

    last = assistant.last

    # Prefer the closest <article> container of the last assistant message.
    # In current ChatGPT Web, this reliably scopes the Copy button to a single turn.
    turn = last.locator("xpath=ancestor::article[1]").first
    if not await turn.count():
        # Fallback: any ancestor that contains a turn-level Copy button.
        turn = last.locator(
            "xpath=ancestor-or-self::*[.//button[@data-testid='copy-turn-action-button']]"
        ).first
    if not await turn.count():
        return None

    copy_btns = turn.locator("button[data-testid='copy-turn-action-button']")
    btn_count = await copy_btns.count()
    if btn_count <= 0:
        return None

    expected_tokens: list[str] = []
    try:
        expected = _normalize_ws(await _extract_assistant_text(last))
        raw_tokens = [t for t in re.split(r"\s+", expected) if t]
        preferred: list[str] = []
        for tok in raw_tokens:
            if len(preferred) >= 5:
                break
            if any(ch in tok for ch in (":", "：", ".", "/", "_")) or len(tok) >= 3:
                preferred.append(tok)
        expected_tokens = preferred or raw_tokens[:2]
    except Exception:
        expected_tokens = []

    question_sig = ""
    if isinstance(question, str) and question.strip():
        question_sig = _normalize_ws(question)[:160]

    # Install clipboard capture hooks (does not rely on OS clipboard).
    try:
        await page.evaluate(_CHATGPT_CLIPBOARD_CAPTURE_INIT_JS)
    except Exception:
        # Best-effort; continue anyway (may still succeed if button exposes payload in attributes).
        pass

    # Some UI hides action buttons until hover; best-effort reveal.
    try:
        await last.scroll_into_view_if_needed(timeout=2_000)
    except Exception:
        pass
    try:
        await last.hover(timeout=1_500)
    except Exception:
        pass

    # Try candidate buttons (some UIs render multiple Copy buttons under a turn container).
    # Prefer later buttons first (tends to be the assistant turn actions in current UI).
    for idx in reversed(range(btn_count)):
        btn = copy_btns.nth(idx)

        # Reset capture (idempotent) before each click.
        try:
            await page.evaluate(_CHATGPT_CLIPBOARD_CAPTURE_INIT_JS)
        except Exception:
            pass

        clicked = False
        for force in (False, True):
            try:
                await btn.click(timeout=2_500, force=force)
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            continue

        deadline = time.time() + max(0.5, timeout_ms / 1000)
        captured: str | None = None
        while time.time() < deadline:
            try:
                v = await page.evaluate(_CHATGPT_CLIPBOARD_CAPTURE_READ_JS)
            except Exception:
                v = None
            if isinstance(v, str) and v.strip():
                captured = v.strip()
                break
            await page.wait_for_timeout(100)
        if not captured:
            continue

        if question_sig and question_sig in _normalize_ws(captured):
            continue

        if expected_tokens:
            norm = _normalize_ws(captured)
            hits = sum(1 for tok in expected_tokens if tok and tok in norm)
            needed = len(expected_tokens) if len(expected_tokens) <= 2 else max(2, math.ceil(len(expected_tokens) * 0.6))
            if hits >= needed:
                return captured
            continue
        return captured
    return None


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _chatgpt_prompt_sent_from_debug_timeline(timeline: Any) -> bool:
    if not isinstance(timeline, list):
        return False
    for ev in timeline:
        if not isinstance(ev, dict):
            continue
        phase = str(ev.get("phase") or "").strip().lower()
        if phase in {"sent", "user_message_confirmed", "duplicate_prompt_guard_skip_send"}:
            return True
    return False


def _is_duplicate_user_prompt(*, question: str, last_user_text: str) -> bool:
    """
    Best-effort guard against accidentally sending the *same* user prompt twice in the same
    conversation (usually caused by a client using a different idempotency_key for a retry).

    Keep the heuristic conservative to avoid skipping an intentional re-ask.
    """

    q = _normalize_ws(question or "")
    last = _normalize_ws(last_user_text or "")
    return bool(q) and bool(last) and q == last


async def _wait_for_message_list_to_settle(page, *, timeout_ms: int = 8_000, stable_ms: int = 1_200) -> None:
    messages = page.locator("[data-message-author-role]")
    deadline = time.time() + max(0.2, timeout_ms / 1000)

    stable_for_ms = 0
    last_count = await messages.count()
    while time.time() < deadline:
        await page.wait_for_timeout(250)
        count = await messages.count()
        if count != last_count:
            last_count = count
            stable_for_ms = 0
            continue
        stable_for_ms += 250
        if stable_for_ms >= stable_ms:
            return


async def _last_assistant_text(page) -> str:
    assistant = page.locator(_CHATGPT_ASSISTANT_SELECTOR)
    count = await assistant.count()
    if count <= 0:
        return ""
    return await _extract_assistant_text(assistant.nth(count - 1))


_DEEP_RESEARCH_WIDGET_FRAME_URL_RE = re.compile(r"(connector_openai_deep_research|openai_deep_research)", re.I)
_DEEP_RESEARCH_WIDGET_INTERNAL_HOST_RE = re.compile(
    r"(^|//)(?:"
    r"chatgpt\.com|chat\.openai\.com|ab\.chatgpt\.com|cdn\.openai\.com|"
    r".*\.oaiusercontent\.com"
    r")(?=/|$)",
    re.I,
)


def _frame_is_descendant_of(frame, ancestor) -> bool:
    cur = frame
    while cur is not None:
        if cur == ancestor:
            return True
        cur = getattr(cur, "parent_frame", None)
    return False


async def _frame_best_effort_body_inner_text(frame) -> str:
    try:
        text = await frame.evaluate("() => (document.body && document.body.innerText) ? document.body.innerText : ''")
    except Exception:
        return ""
    return str(text or "")


async def _frame_best_effort_href_list(frame) -> list[str]:
    try:
        raw = await frame.evaluate(
            "() => Array.from(document.querySelectorAll('a[href]')).map((a) => a.href || a.getAttribute('href')).filter(Boolean)"
        )
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    urls: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        u = item.strip()
        if not u:
            continue
        urls.append(u)
    return urls


_DEEP_RESEARCH_WIDGET_EXPORT_BTN_SELECTORS = (
    "button[aria-label='Export']",
    "button[aria-label='导出']",
    "button[aria-label='匯出']",
    "button:has-text('Export')",
    "button:has-text('导出')",
    "button:has-text('匯出')",
)

_DEEP_RESEARCH_WIDGET_EXPORT_WORD_SELECTORS = (
    "button:has-text('Export to Word')",
    "button:has-text('Export to DOCX')",
    "button:has-text('Word')",
    "button:has-text('DOCX')",
    "button:has-text('导出到 Word')",
    "button:has-text('导出为 Word')",
    "button:has-text('匯出至 Word')",
)

_DEEP_RESEARCH_WIDGET_EXPORT_MARKDOWN_SELECTORS = (
    "button:has-text('Export to Markdown')",
    "button:has-text('Export Markdown')",
    "button:has-text('Export to MD')",
    "div[role='menuitem']:has-text('Export to Markdown')",
    "div[role='menuitem']:has-text('Export Markdown')",
    "div[role='menuitem']:has-text('Export to MD')",
    "button:has-text('导出到 Markdown')",
    "button:has-text('导出为 Markdown')",
    "button:has-text('导出到 MD')",
    "div[role='menuitem']:has-text('导出到 Markdown')",
    "div[role='menuitem']:has-text('导出为 Markdown')",
    "button:has-text('匯出至 Markdown')",
    "button:has-text('匯出為 Markdown')",
    "div[role='menuitem']:has-text('匯出至 Markdown')",
    "div[role='menuitem']:has-text('匯出為 Markdown')",
)


async def _frame_best_effort_has_visible_selector(frame, selector: str) -> bool:
    try:
        loc = frame.locator(selector).first
        if not await loc.count():
            return False
        return await loc.is_visible()
    except Exception:
        return False


def _pandoc_docx_to_gfm_markdown(path: str) -> str:
    if not path:
        return ""
    cmd = ["pandoc", str(path), "-t", "gfm", "--wrap=none"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        stderr = (res.stderr or "").strip()
        raise RuntimeError(f"pandoc failed (rc={res.returncode}): {stderr[:800]}")
    return str(res.stdout or "")


_DEEP_RESEARCH_PANDOC_CITE_LINK_RE = re.compile(
    r"\[\s*\\\[(\d{1,4})\\\]\s*\]\(([^)\s]+)\)",
    re.I,
)
_DEEP_RESEARCH_PANDOC_CITE_LINK_ALT_RE = re.compile(
    r"\[\[(\d{1,4})\]\]\(([^)\s]+)\)",
    re.I,
)
_DEEP_RESEARCH_MD_EXPORT_CITE_NUM_LINK_RE = re.compile(
    r"\[\s*(\d{1,4})\s*\]\(([^)\s]+)\)",
    re.I,
)


def _deep_research_pandoc_rewrite_citation_links(markdown: str) -> tuple[str, list[tuple[int, str]]]:
    s = str(markdown or "")
    sources: list[tuple[int, str]] = []

    def _repl(m: re.Match) -> str:
        try:
            idx = int(m.group(1))
        except Exception:
            return m.group(0)
        url = html.unescape(str(m.group(2) or "").strip())
        if not url:
            return m.group(0)
        sources.append((idx, url))
        return f"[[S{idx}]]({url})"

    s = _DEEP_RESEARCH_PANDOC_CITE_LINK_RE.sub(_repl, s)
    s = _DEEP_RESEARCH_PANDOC_CITE_LINK_ALT_RE.sub(_repl, s)
    # Deep Research "Export to Markdown" often uses `[1](url)` style citations; rewrite those too.
    s = _DEEP_RESEARCH_MD_EXPORT_CITE_NUM_LINK_RE.sub(_repl, s)
    return s, sources


_DEEP_RESEARCH_S_CITE_ONLY_LINE_RE = re.compile(r"^(?:\s*\[\[S\d+\]\]\([^)]+\)\s*)+$")


def _deep_research_pandoc_inline_citation_lines(markdown: str) -> str:
    lines = str(markdown or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    for ln in lines:
        if _DEEP_RESEARCH_S_CITE_ONLY_LINE_RE.match(ln or "") and out and out[-1].strip():
            out[-1] = out[-1].rstrip() + " " + ln.strip()
            continue
        out.append(ln)
    return "\n".join(out).strip()


def _deep_research_pandoc_append_sources(markdown: str, sources: list[tuple[int, str]]) -> str:
    s = str(markdown or "").strip()
    if not sources:
        return s
    if re.search(r"^##\\s+Sources\\s*$", s, re.I | re.M):
        return s

    seen: set[tuple[int, str]] = set()
    unique: list[tuple[int, str]] = []
    for idx, url in sources:
        key = (int(idx), str(url))
        if key in seen:
            continue
        seen.add(key)
        unique.append(key)
    unique.sort(key=lambda x: x[0])

    block = ["## Sources"]
    for idx, url in unique:
        block.append(f"- [[S{idx}]]({url})")
    return (s + "\n\n" + "\n".join(block)).strip()


async def _deep_research_widget_best_effort_export_docx_markdown(
    page,
    *,
    frame,
    ctx: Context | None,
    timeout_ms: int = 60_000,
) -> tuple[str, dict[str, Any]] | None:
    """
    Best-effort Deep Research export:
    - click Export -> Export to Word (DOCX) inside the embedded report frame
    - convert DOCX -> GitHub-flavored Markdown via pandoc
    - rewrite citation links to [[S#]] and append a Sources section
    """
    export_btn = None
    for sel in _DEEP_RESEARCH_WIDGET_EXPORT_BTN_SELECTORS:
        if await _frame_best_effort_has_visible_selector(frame, sel):
            export_btn = frame.locator(sel).first
            break
    if export_btn is None:
        return None

    started_at = time.time()
    tmp_dir = Path(tempfile.mkdtemp(prefix="chatgptrest_deep_research_export_"))
    docx_path = tmp_dir / "deep-research-report.docx"
    meta: dict[str, Any] = {}
    try:
        await export_btn.click(timeout=3_000)
        await page.wait_for_timeout(250)

        word_btn = None
        for sel in _DEEP_RESEARCH_WIDGET_EXPORT_WORD_SELECTORS:
            if await _frame_best_effort_has_visible_selector(frame, sel):
                word_btn = frame.locator(sel).first
                break
        if word_btn is None:
            return None

        try:
            async with page.expect_download(timeout=timeout_ms) as dl_info:
                await word_btn.click(timeout=5_000)
            dl = await dl_info.value
        except Exception as exc:
            meta["download_error"] = f"{type(exc).__name__}: {exc}"
            return None

        try:
            meta["suggested_filename"] = str(getattr(dl, "suggested_filename", "") or "")
        except Exception:
            pass
        await dl.save_as(str(docx_path))
        meta["docx_bytes"] = int(docx_path.stat().st_size)

        md = await asyncio.to_thread(_pandoc_docx_to_gfm_markdown, str(docx_path))
        md = md.strip()
        if not md:
            meta["pandoc_empty"] = True
            return None

        md2, sources = _deep_research_pandoc_rewrite_citation_links(md)
        md2 = _deep_research_pandoc_inline_citation_lines(md2)
        md2 = _deep_research_pandoc_append_sources(md2, sources)
        meta["pandoc_markdown_chars"] = len(md2)
        meta["sources_count"] = len({(i, u) for i, u in sources})
        meta["elapsed_ms"] = int(round((time.time() - started_at) * 1000))
        return md2.strip(), meta
    finally:
        try:
            if docx_path.exists():
                docx_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


async def _deep_research_widget_best_effort_export_markdown(
    page,
    *,
    frame,
    ctx: Context | None,
    timeout_ms: int = 60_000,
) -> tuple[str, dict[str, Any]] | None:
    """
    Best-effort Deep Research export (preferred when available):
    - click Export -> Export to Markdown inside the embedded report frame
    - rewrite citation links to [[S#]] and append a Sources section
    """
    export_btn = None
    for sel in _DEEP_RESEARCH_WIDGET_EXPORT_BTN_SELECTORS:
        if await _frame_best_effort_has_visible_selector(frame, sel):
            export_btn = frame.locator(sel).first
            break
    if export_btn is None:
        return None

    started_at = time.time()
    tmp_dir = Path(tempfile.mkdtemp(prefix="chatgptrest_deep_research_export_"))
    md_path = tmp_dir / "deep-research-report.md"
    meta: dict[str, Any] = {}
    try:
        await export_btn.click(timeout=3_000)
        await page.wait_for_timeout(250)

        md_btn = None
        for sel in _DEEP_RESEARCH_WIDGET_EXPORT_MARKDOWN_SELECTORS:
            if await _frame_best_effort_has_visible_selector(frame, sel):
                md_btn = frame.locator(sel).first
                break
        if md_btn is None:
            return None

        try:
            async with page.expect_download(timeout=timeout_ms) as dl_info:
                await md_btn.click(timeout=5_000)
            dl = await dl_info.value
        except Exception as exc:
            meta["download_error"] = f"{type(exc).__name__}: {exc}"
            return None

        try:
            meta["suggested_filename"] = str(getattr(dl, "suggested_filename", "") or "")
        except Exception:
            pass
        await dl.save_as(str(md_path))
        meta["md_bytes"] = int(md_path.stat().st_size)

        md = md_path.read_text(encoding="utf-8", errors="replace").strip()
        if not md:
            meta["markdown_empty"] = True
            return None

        md2, sources = _deep_research_pandoc_rewrite_citation_links(md)
        md2 = _deep_research_pandoc_inline_citation_lines(md2)
        md2 = _deep_research_pandoc_append_sources(md2, sources)
        meta["markdown_chars"] = len(md2)
        meta["sources_count"] = len({(i, u) for i, u in sources})
        meta["elapsed_ms"] = int(round((time.time() - started_at) * 1000))
        return md2.strip(), meta
    finally:
        try:
            if md_path.exists():
                md_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


def _deep_research_widget_filter_source_urls(urls: list[str]) -> list[str]:
    if not urls:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for u in urls:
        s = str(u or "").strip()
        if not s:
            continue
        if not re.match(r"^https?://", s, re.I):
            continue
        if _DEEP_RESEARCH_WIDGET_INTERNAL_HOST_RE.search(s):
            continue
        key = s.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


_DEEP_RESEARCH_WIDGET_HEADER_RE = re.compile(r"^\s*(Research completed|研究完成|已完成研究|Deep research)\b", re.I)
_DEEP_RESEARCH_WIDGET_META_RE = re.compile(r"^\s*(citations?|searches?)\b", re.I)


def _deep_research_widget_text_to_markdown(text: str, *, source_urls: list[str]) -> str:
    s = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in s.split("\n")]

    def _is_header_line(line: str) -> bool:
        t = (line or "").strip()
        if not t:
            return True
        if _DEEP_RESEARCH_WIDGET_HEADER_RE.match(t):
            return True
        if _DEEP_RESEARCH_WIDGET_META_RE.match(t):
            return True
        if re.fullmatch(r"\d{1,4}", t):
            return True
        if t in {"·", "•"}:
            return True
        return False

    # Drop the embedded widget's "Research completed / citations / searches" header chunk.
    while lines and _is_header_line(lines[0]):
        lines.pop(0)
    while lines and not lines[0].strip():
        lines.pop(0)

    # Remove duplicate consecutive lines (common: report title repeated twice).
    deduped: list[str] = []
    for ln in lines:
        if deduped and ln.strip() and ln.strip() == deduped[-1].strip():
            continue
        deduped.append(ln)
    lines = deduped

    # Promote the first line to a Markdown title when it looks like a report heading.
    if lines:
        first = lines[0].strip()
        if first and not first.startswith("#"):
            lines[0] = f"# {first}"

    # Best-effort: inline citation markers that were extracted as standalone digit-only lines.
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.fullmatch(r"\d{1,4}", (line or "").strip()) and out:
            digits: list[str] = []
            j = i
            while j < len(lines) and re.fullmatch(r"\d{1,4}", (lines[j] or "").strip()):
                digits.append(lines[j].strip())
                j += 1
            cite = "".join(f"[{d}]" for d in digits)
            next_line = lines[j] if j < len(lines) else ""
            if next_line.lstrip().startswith((".", "。", ",", "，", ";", "；", ":", "：", ")", "]", "】")):
                out[-1] = out[-1].rstrip() + cite + next_line.lstrip()
                i = j + 1
                continue
            out[-1] = out[-1].rstrip() + cite
            i = j
            continue
        out.append(line)
        i += 1

    cleaned = "\n".join(out).strip()
    urls = _deep_research_widget_filter_source_urls(list(source_urls or []))
    if urls:
        # Avoid emitting a second "## Sources" header when the report already contains one.
        header = "## Sources" if not re.search(r"^##\\s+Sources\\s*$", cleaned, re.I | re.M) else "## Source URLs"
        cleaned += f"\n\n{header}\n"
        cleaned += "\n".join(f"- {u}" for u in urls)
    return cleaned.strip()


_DEEP_RESEARCH_WIDGET_MARKER_RE = re.compile(r"([a-zA-Z_]+)(.*?)", re.S)
_DEEP_RESEARCH_WIDGET_ANY_TOKEN_RE = re.compile(r".*?", re.S)


def _deep_research_widget_strip_markup_tokens(markdown: str) -> str:
    """
    Deep Research widget innerText can include private-use "token" markers that render as
    citations/entities in the UI (for example: `cite...`, `entity[...]`).

    These are not valid Markdown and are confusing for downstream clients. Best-effort:
    - drop cite/ref tokens entirely
    - unwrap entity tokens to their display name when possible
    - strip any remaining `...` tokens
    """
    s = str(markdown or "")
    if "" not in s:
        return s.strip()

    def _repl(m: re.Match) -> str:
        kind = str(m.group(1) or "").strip().lower()
        payload = str(m.group(2) or "").strip()
        if kind == "entity":
            # Payload is usually a JSON array: ["type","Name","description"].
            try:
                obj = json.loads(payload)
            except Exception:
                obj = None
            if isinstance(obj, list) and len(obj) >= 2 and isinstance(obj[1], str) and obj[1].strip():
                return obj[1].strip()
            return ""
        # cite/ref/etc: remove (URLs are appended separately under Sources).
        return ""

    s = _DEEP_RESEARCH_WIDGET_MARKER_RE.sub(_repl, s)
    s = _DEEP_RESEARCH_WIDGET_ANY_TOKEN_RE.sub("", s)
    # Clean up whitespace artifacts.
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _should_prefer_deep_research_widget(widget_text: str, current_text: str) -> bool:
    """
    Decide whether to override the normal assistant text with the Deep Research embedded report.

    Heuristics:
    - prefer when widget is longer, OR
    - prefer when widget has a Sources section (URLs) and current doesn't, OR
    - prefer when widget has rewritten [[S#]] citations and current doesn't.
    """
    w = str(widget_text or "").strip()
    if not w:
        return False
    c = str(current_text or "").strip()
    if len(w) > len(c):
        return True
    if "## Sources" in w and "## Sources" not in c:
        return True
    if "[[S" in w and ("[[S" not in c and "[S" not in c):
        return True
    return False


async def _chatgpt_best_effort_deep_research_widget_text(page, *, ctx: Context | None) -> tuple[str, dict[str, Any]] | None:
    """
    ChatGPT Deep Research can render the final report inside a sandboxed embedded app (iframes).

    In this UI variant, the normal assistant turn text can be empty or a short JSON stub while the
    report is visible only inside a nested frame. Extract the longest visible body innerText among
    frames whose URL suggests the Deep Research connector.
    """
    try:
        frames = list(getattr(page, "frames", []))
    except Exception:
        frames = []
    if not frames:
        return None

    outer_frames = [
        f for f in frames if _DEEP_RESEARCH_WIDGET_FRAME_URL_RE.search(str(getattr(f, "url", "") or ""))
    ]
    if not outer_frames:
        # Embedded widget iframes may be lazy-loaded when the report scrolls into view.
        for _ in range(6):
            try:
                await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1200)
            except Exception:
                pass
            try:
                frames = list(getattr(page, "frames", []))
            except Exception:
                frames = []
            outer_frames = [
                f for f in frames if _DEEP_RESEARCH_WIDGET_FRAME_URL_RE.search(str(getattr(f, "url", "") or ""))
            ]
            if outer_frames:
                break
    if not frames:
        return None

    if not outer_frames:
        return None

    best_text = ""
    best_meta: dict[str, Any] = {}
    best_frame = None
    best_outer = None

    # The embedded Deep Research app can take a few seconds to initialize its inner frames; sometimes the report
    # text is empty but the Export menu is already available. Poll briefly for either (exportable report or text).
    export_fail: str | None = None
    for _ in range(12):
        # Prefer the widget's native "Export to Markdown" when available; fall back to DOCX+pandoc.
        export_frame = None
        export_outer = None
        for outer in outer_frames:
            for fr in frames:
                try:
                    if not _frame_is_descendant_of(fr, outer):
                        continue
                except Exception:
                    continue
                for sel in _DEEP_RESEARCH_WIDGET_EXPORT_BTN_SELECTORS:
                    if await _frame_best_effort_has_visible_selector(fr, sel):
                        export_frame = fr
                        export_outer = outer
                        break
                if export_frame is not None:
                    break
            if export_frame is not None:
                break

        if export_frame is not None:
            try:
                exported = await _deep_research_widget_best_effort_export_markdown(page, frame=export_frame, ctx=ctx)
                if exported is None:
                    exported = await _deep_research_widget_best_effort_export_docx_markdown(page, frame=export_frame, ctx=ctx)
            except Exception as exc:
                exported = None
                export_fail = f"{type(exc).__name__}: {exc}"
            if exported is not None:
                md, export_meta = exported
                md = _deep_research_widget_strip_markup_tokens(md)
                if md and len(md.strip()) >= 200:
                    meta = {
                        "outer_url": str(getattr(export_outer, "url", "") or ""),
                        "frame_url": str(getattr(export_frame, "url", "") or ""),
                        "export_meta": export_meta,
                        "markdown_chars": len(md),
                    }
                    return md, meta

        best_text = ""
        best_meta = {}
        best_frame = None
        best_outer = None
        for outer in outer_frames:
            for fr in frames:
                try:
                    if not _frame_is_descendant_of(fr, outer):
                        continue
                except Exception:
                    continue
                text = (await _frame_best_effort_body_inner_text(fr)).strip()
                if len(text) > len(best_text):
                    best_text = text
                    best_frame = fr
                    best_outer = outer
                    best_meta = {
                        "outer_url": str(getattr(outer, "url", "") or ""),
                        "frame_url": str(getattr(fr, "url", "") or ""),
                        "chars": len(text),
                    }

        if best_text:
            break

        try:
            await page.wait_for_timeout(1200)
        except Exception:
            pass
        try:
            frames = list(getattr(page, "frames", []))
        except Exception:
            frames = []
        if not frames:
            continue
        outer_frames = [
            f for f in frames if _DEEP_RESEARCH_WIDGET_FRAME_URL_RE.search(str(getattr(f, "url", "") or ""))
        ]
        if not outer_frames:
            continue

    if not best_text:
        if export_fail:
            best_meta = {"export_error": export_fail}
        return None

    # Best-effort: if we fell back to innerText, try one more export pass now that the embedded app likely finished
    # initializing (export often appears slightly later than the first text paint).
    try:
        for outer in outer_frames:
            for fr in frames:
                try:
                    if not _frame_is_descendant_of(fr, outer):
                        continue
                except Exception:
                    continue
                for sel in _DEEP_RESEARCH_WIDGET_EXPORT_BTN_SELECTORS:
                    if await _frame_best_effort_has_visible_selector(fr, sel):
                        exported = await _deep_research_widget_best_effort_export_markdown(page, frame=fr, ctx=ctx)
                        if exported is None:
                            exported = await _deep_research_widget_best_effort_export_docx_markdown(page, frame=fr, ctx=ctx)
                        if exported is None:
                            break
                        md, export_meta = exported
                        md = _deep_research_widget_strip_markup_tokens(md)
                        if md and len(md.strip()) >= 200:
                            meta = dict(best_meta)
                            meta["export_meta"] = export_meta
                            meta["markdown_chars"] = len(md)
                            return md, meta
                # Stop scanning if we already attempted export for this frame.
    except Exception as exc:
        best_meta["export_error"] = f"{type(exc).__name__}: {exc}"

    source_urls_raw: list[str] = []
    try:
        if best_outer is not None:
            for fr in frames:
                try:
                    if not _frame_is_descendant_of(fr, best_outer):
                        continue
                except Exception:
                    continue
                source_urls_raw.extend(await _frame_best_effort_href_list(fr))
        elif best_frame is not None:
            source_urls_raw.extend(await _frame_best_effort_href_list(best_frame))
    except Exception:
        source_urls_raw = []
    source_urls = _deep_research_widget_filter_source_urls(source_urls_raw)
    if source_urls:
        best_meta["source_urls"] = source_urls[:200]
        best_meta["source_urls_count"] = len(source_urls)
    markdown = _deep_research_widget_text_to_markdown(best_text, source_urls=source_urls)
    markdown = _deep_research_widget_strip_markup_tokens(markdown)
    best_meta["markdown_chars"] = len(markdown)
    return markdown, best_meta


async def _wait_for_user_message(page, *, question: str, start_user_count: int, timeout_ms: int = 12_000) -> None:
    user = page.locator(_CHATGPT_USER_SELECTOR)
    wanted = _normalize_ws(question)
    wanted_sig = wanted[:80] if wanted else ""

    deadline = time.time() + max(0.2, timeout_ms / 1000)
    while time.time() < deadline:
        count = await user.count()
        if count > start_user_count:
            if not wanted_sig:
                return
            try:
                last = _normalize_ws((await user.nth(count - 1).inner_text(timeout=2_000)).strip())
            except Exception:
                # If the DOM changed under us (or the message contains non-text attachments),
                # treat the count increase as confirmation the prompt was sent.
                return
            if wanted_sig in last:
                return
            # File uploads / rich message rendering can truncate or omit the raw prompt text
            # from the accessible innerText; accept the count increase as sufficient.
            return
        await page.wait_for_timeout(200)
    raise TimeoutError("Timed out waiting for the user message to appear after sending.")


def _flush_obs(
    obs: dict | None,
    *,
    started_at: float,
    stop_seen: bool,
    stop_gone_at: float | None,
    sandbox_seen: bool,
    dom_changes: int,
    timed_out: bool = False,
) -> None:
    """Populate optional wait observations dict."""
    if obs is None:
        return
    now = time.time()
    obs["thinking_seconds"] = round(now - started_at, 1)
    obs["code_sandbox_appeared"] = sandbox_seen
    obs["stop_button_appeared"] = stop_seen
    if stop_gone_at is not None:
        obs["stop_button_disappeared_at"] = stop_gone_at
    obs["answer_stable_at"] = now
    obs["dom_changes_count"] = dom_changes
    obs["timed_out"] = timed_out


async def _wait_for_answer(
    page,
    *,
    started_at: float,
    start_assistant_count: int,
    timeout_seconds: int,
    min_chars: int = 0,
    require_new: bool = True,
    baseline_last_text: str | None = None,
    observations: dict | None = None,
    ctx: Context | None = None,
) -> str:
    assistant = page.locator(_CHATGPT_ASSISTANT_SELECTOR)

    deadline = started_at + timeout_seconds
    baseline_last = _normalize_ws(baseline_last_text or "")

    stop_btn = page.locator(_CHATGPT_STOP_BUTTON_SELECTOR).first

    if require_new:
        while time.time() < deadline:
            count = await assistant.count()

            stop_visible = False
            try:
                if await stop_btn.count():
                    stop_visible = await stop_btn.is_visible()
            except PlaywrightTimeoutError:
                stop_visible = False

            last_text = ""
            if count > 0:
                last = assistant.nth(count - 1)
                last_text = _normalize_ws(await _extract_assistant_text(last))

            if count > start_assistant_count:
                if stop_visible or not baseline_last or last_text != baseline_last:
                    break

            if baseline_last and last_text and last_text != baseline_last:
                break

            # Avoid breaking early just because the stop button appears; require evidence that the
            # assistant content has actually started (new message or changed last_text).
            if stop_visible and count > start_assistant_count:
                break

            await _maybe_idle_interaction(page, ctx=ctx)
            await page.wait_for_timeout(200)
        else:
            raise TimeoutError("Timed out waiting for assistant response to start.")
    else:
        while time.time() < deadline:
            if await assistant.count() > start_assistant_count:
                break
            await _maybe_idle_interaction(page, ctx=ctx)
            await page.wait_for_timeout(200)
        else:
            raise TimeoutError("Timed out waiting for assistant message to appear.")

    stable_seconds = 0.0
    prev_count = -1
    prev_text = ""
    _obs_stop_button_seen = False
    _obs_stop_button_gone_at = None
    _obs_code_sandbox_seen = False
    _obs_dom_changes = 0
    while time.time() < deadline:
        count = await assistant.count()
        if count <= 0:
            await page.wait_for_timeout(200)
            continue

        last = assistant.nth(count - 1)
        try:
            text = await _extract_assistant_text(last)
        except PlaywrightTimeoutError:
            text = ""
        if text and text == prev_text and count == prev_count:
            stable_seconds += 0.5
        else:
            stable_seconds = 0.0
            if prev_text and text != prev_text:
                _obs_dom_changes += 1
            prev_text = text
            prev_count = count

        stop_visible = False
        try:
            if await stop_btn.count():
                stop_visible = await stop_btn.is_visible()
        except PlaywrightTimeoutError:
            stop_visible = False

        if stop_visible:
            _obs_stop_button_seen = True
            _obs_stop_button_gone_at = None
        elif _obs_stop_button_seen and _obs_stop_button_gone_at is None:
            _obs_stop_button_gone_at = time.time()

        # ── Code sandbox / canvas activity guard ──────────────────
        # When the model opens a code sandbox or canvas, text can temporarily
        # stabilize (the planning preamble) while actual generation continues.
        # Reset stable_seconds to avoid returning preamble as the final answer.
        code_sandbox_active = False
        try:
            code_sandbox_loc = page.locator(
                '[data-testid="canvas-panel"], '
                'iframe[src*="codesandbox"], '
                '[data-testid="code-interpreter"], '
                '.code-sandbox-active'
            )
            if await code_sandbox_loc.count() > 0:
                code_sandbox_active = True
                _obs_code_sandbox_seen = True
        except Exception:
            pass

        if prev_text and stable_seconds >= 2.0 and not stop_visible and len(prev_text) >= min_chars:
            if code_sandbox_active:
                # Code sandbox is open — text may be just a preamble; keep waiting.
                stable_seconds = 0.0
            elif require_new and baseline_last and _normalize_ws(prev_text) == baseline_last and count <= start_assistant_count:
                # Still seeing the baseline answer; keep waiting.
                pass
            else:
                _flush_obs(observations, started_at=started_at, stop_seen=_obs_stop_button_seen,
                           stop_gone_at=_obs_stop_button_gone_at, sandbox_seen=_obs_code_sandbox_seen,
                           dom_changes=_obs_dom_changes)
                return prev_text
        await _maybe_idle_interaction(page, ctx=ctx)
        await page.wait_for_timeout(500)

    if prev_text:
        if min_chars and len(prev_text) < min_chars:
            _flush_obs(observations, started_at=started_at, stop_seen=_obs_stop_button_seen,
                       stop_gone_at=_obs_stop_button_gone_at, sandbox_seen=_obs_code_sandbox_seen,
                       dom_changes=_obs_dom_changes, timed_out=True)
            raise TimeoutError("Timed out waiting for assistant answer content (min_chars not reached).")
        _flush_obs(observations, started_at=started_at, stop_seen=_obs_stop_button_seen,
                   stop_gone_at=_obs_stop_button_gone_at, sandbox_seen=_obs_code_sandbox_seen,
                   dom_changes=_obs_dom_changes, timed_out=True)
        return prev_text
    _flush_obs(observations, started_at=started_at, stop_seen=_obs_stop_button_seen,
               stop_gone_at=_obs_stop_button_gone_at, sandbox_seen=_obs_code_sandbox_seen,
               dom_changes=_obs_dom_changes, timed_out=True)
    raise TimeoutError("Timed out waiting for assistant answer content.")



async def _list_big_images(page, *, min_area: int) -> list[dict[str, Any]]:
    imgs = page.locator("main img")
    count = await imgs.count()
    found: list[dict[str, Any]] = []
    for i in range(min(count, 20)):
        img = imgs.nth(i)
        try:
            box = await img.bounding_box()
        except Exception:
            continue
        if not box:
            continue
        area = float(box.get("width", 0)) * float(box.get("height", 0))
        if area < min_area:
            continue
        src = (await img.get_attribute("src")) or ""
        if not src:
            continue
        alt = (await img.get_attribute("alt")) or ""
        found.append(
            {
                "src": src,
                "alt": alt,
                "width": round(float(box.get("width", 0))),
                "height": round(float(box.get("height", 0))),
            }
        )

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in found:
        src = str(item.get("src") or "")
        if not src or src in seen:
            continue
        seen.add(src)
        deduped.append(item)
    return deduped


async def _wait_for_generated_images(
    page,
    *,
    started_at: float,
    timeout_seconds: int,
    min_area: int,
    stable_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    deadline = started_at + timeout_seconds
    stop_btn = page.locator(
        _CHATGPT_STOP_BUTTON_SELECTOR
    ).first

    prev_srcs: list[str] = []
    stable_for = 0.0
    while time.time() < deadline:
        items = await _list_big_images(page, min_area=min_area)
        srcs = [str(item.get("src") or "") for item in items]

        stop_visible = False
        try:
            if await stop_btn.count():
                stop_visible = await stop_btn.is_visible()
        except PlaywrightTimeoutError:
            stop_visible = False

        if srcs and srcs == prev_srcs and not stop_visible:
            stable_for += 0.5
        else:
            stable_for = 0.0
            prev_srcs = srcs

        if srcs and stable_for >= stable_seconds:
            return items

    await page.wait_for_timeout(500)
    raise TimeoutError("Timed out waiting for generated images to appear.")





from chatgpt_web_mcp.mcp_registry import iter_mcp_tools as _iter_mcp_tools
from chatgpt_web_mcp.mcp_registry import mcp


_CHATGPT_SEND_LOCK: asyncio.Lock | None = None
_LAST_CHATGPT_PROMPT_SENT_AT: float = 0.0


def _chatgpt_send_lock() -> asyncio.Lock:
    global _CHATGPT_SEND_LOCK
    if _CHATGPT_SEND_LOCK is None:
        _CHATGPT_SEND_LOCK = asyncio.Lock()
    return _CHATGPT_SEND_LOCK




async def _chatgpt_send_prompt(*, page: Any, prompt_box: Any, send_btn: Any, ctx: Context | None) -> None:
    """Serialize ONLY the 'send new prompt' action across concurrent tool calls."""
    global _LAST_CHATGPT_PROMPT_SENT_AT

    async with _chatgpt_send_lock():
        async with _chatgpt_global_lock(ctx):
            rate_limit_file = _chatgpt_global_rate_limit_file()
            last_sent_at = _LAST_CHATGPT_PROMPT_SENT_AT
            if rate_limit_file is not None:
                last_sent_at = max(last_sent_at, _chatgpt_global_last_sent_at(rate_limit_file))

            await _respect_prompt_interval(
                last_sent_at=last_sent_at,
                min_interval_seconds=_min_prompt_interval_seconds(),
                label="ChatGPT",
                ctx=ctx,
            )
            try:
                if await send_btn.count() and await send_btn.is_enabled():
                    await _human_click(page, send_btn, timeout_ms=5_000)
                else:
                    await prompt_box.press("Enter")
            except PlaywrightTimeoutError:
                await prompt_box.press("Enter")
            except Exception:
                try:
                    await send_btn.click()
                except Exception:
                    await prompt_box.press("Enter")

            now_sent_at = time.time()
            _LAST_CHATGPT_PROMPT_SENT_AT = now_sent_at
            if rate_limit_file is not None:
                _chatgpt_global_write_last_sent_at(rate_limit_file, now_sent_at)


async def _chatgpt_send_followup_message(page, *, message: str, ctx: Context | None) -> None:
    prompt = await _find_prompt_box(page)
    await prompt.click()
    await _human_pause(page)
    try:
        await _type_question(prompt, message)
    except PlaywrightTimeoutError:
        # The composer can re-render after toggling modes; re-acquire once and retry.
        prompt = await _find_prompt_box(page, timeout_ms=30_000)
        await prompt.click()
        await _human_pause(page)
        await _type_question(prompt, message)
    await _human_pause(page)

    start_user_count = await page.locator(_CHATGPT_USER_SELECTOR).count()
    send_btn = page.locator(_CHATGPT_SEND_BUTTON_SELECTOR).first
    await _wait_for_send_button_enabled(send_btn, timeout_ms=30_000)
    await _chatgpt_send_prompt(page=page, prompt_box=prompt, send_btn=send_btn, ctx=ctx)
    try:
        await _wait_for_user_message(page, question=message, start_user_count=start_user_count, timeout_ms=20_000)
    except Exception:
        # If the composer cleared (or generation started), treat this as sent even if we can't
        # confirm the user message DOM update in time.
        stop_btn = page.locator(_CHATGPT_STOP_BUTTON_SELECTOR).first
        stop_visible = False
        try:
            if await stop_btn.count():
                stop_visible = await stop_btn.is_visible()
        except Exception:
            stop_visible = False

        current_text = await _prompt_box_text(prompt)
        if not ((current_text is not None and not current_text.strip()) or stop_visible):
            raise


async def _open_chatgpt_page(p, cfg: ChatGPTWebConfig, *, conversation_url: str | None, ctx: Context | None):
    if cfg.cdp_url:
        await _ctx_info(ctx, f"Connecting over CDP: {cfg.cdp_url}")
    else:
        await _ctx_info(ctx, f"Launching Chromium (headless={cfg.headless})")

    use_cdp = bool(cfg.cdp_url)
    viewport_width, viewport_height = _apply_viewport_jitter(cfg.viewport_width, cfg.viewport_height)
    if ctx and _random_log_enabled():
        delta_w = viewport_width - cfg.viewport_width
        delta_h = viewport_height - cfg.viewport_height
        if delta_w or delta_h:
            await _ctx_info(
                ctx,
                f"[random] viewport_jitter base={cfg.viewport_width}x{cfg.viewport_height} "
                f"delta=({delta_w},{delta_h}) final={viewport_width}x{viewport_height}",
            )

    if use_cdp:
        await _ensure_local_cdp_chrome_running(kind="chatgpt", cdp_url=cfg.cdp_url, ctx=ctx)

        async def _open_over_cdp() -> tuple[Any, Any, Any, bool]:
            browser = await _connect_over_cdp_resilient(p, cfg.cdp_url, ctx=ctx)
            if browser is None:
                raise RuntimeError("connect_over_cdp returned null browser")
            if not browser.contexts:
                raise RuntimeError("No Chrome contexts found via CDP.")
            context = browser.contexts[0]
            target_url = conversation_url or cfg.url
            page = await _chatgpt_pick_existing_cdp_page(context, conversation_url=conversation_url, ctx=ctx)
            reused_existing = page is not None
            if page is None:
                page = await context.new_page()
                await _install_stealth_init_script(page, ctx=ctx)
            try:
                await page.set_viewport_size({"width": viewport_width, "height": viewport_height})
            except Exception:
                pass
            try:
                await page.bring_to_front()
            except Exception:
                pass

            should_navigate = True
            if reused_existing:
                current_url = str(page.url or "").strip()
                if conversation_url:
                    current_conv_id = _chatgpt_conversation_id_from_url(current_url)
                    target_conv_id = _chatgpt_conversation_id_from_url(target_url)
                    should_navigate = bool(target_conv_id and current_conv_id != target_conv_id)
                else:
                    should_navigate = False
            if should_navigate:
                await _ctx_info(ctx, f"Navigating to {target_url}")
                await _goto_with_retry(page, target_url, ctx=ctx)
            close_context = False
            return browser, context, page, close_context

        cdp_ok = False
        try:
            browser, context, page, close_context = await _open_over_cdp()
            cdp_ok = True
        except Exception as e:
            restarted = await _restart_local_cdp_chrome(kind="chatgpt", cdp_url=cfg.cdp_url, ctx=ctx)
            if restarted:
                await _ctx_info(ctx, "Retrying CDP connect after Chrome restart …")
                try:
                    browser, context, page, close_context = await _open_over_cdp()
                    cdp_ok = True
                except Exception as e2:
                    e = e2

            if not cdp_ok:
                if not _cdp_fallback_enabled(kind="chatgpt"):
                    msg = (
                        f"CDP connect failed ({type(e).__name__}: {e}). "
                        "CDP fallback is disabled. Ensure the noVNC Chrome is running and reachable via CHATGPT_CDP_URL "
                        "(try: DISPLAY=:99 ops/chrome_start.sh), then retry."
                    )
                    raise RuntimeError(msg) from e
                await _ctx_info(
                    ctx,
                    f"CDP connect failed ({type(e).__name__}: {e}). Falling back to storage_state launch.",
                )
                use_cdp = False

    if not use_cdp:
        proxy = None
        if cfg.proxy_server:
            proxy = {"server": cfg.proxy_server}
            if cfg.proxy_username:
                proxy["username"] = cfg.proxy_username
            if cfg.proxy_password:
                proxy["password"] = cfg.proxy_password
            await _ctx_info(ctx, f"Using proxy: {cfg.proxy_server}")

        browser = await p.chromium.launch(headless=cfg.headless, proxy=proxy)
        context = await browser.new_context(
            storage_state=str(cfg.storage_state_path),
            viewport={"width": viewport_width, "height": viewport_height},
            accept_downloads=True,
        )
        page = await context.new_page()
        await _install_stealth_init_script(page, ctx=ctx)

        url = conversation_url or cfg.url
        await _ctx_info(ctx, f"Navigating to {url}")
        await _goto_with_retry(page, url, ctx=ctx)
        close_context = True

    await _raise_if_chatgpt_blocked(page, ctx=ctx, phase="open", connection=("cdp" if use_cdp else "storage_state"))

    return browser, context, page, close_context


def _chatgpt_should_preserve_cdp_page(
    *,
    tool: str,
    close_context: bool,
    conversation_url: str | None,
    page_url: str | None,
) -> bool:
    if bool(close_context):
        return False
    normalized_tool = str(tool or "").strip().lower()
    if normalized_tool not in {"chatgpt_web_self_check", "chatgpt_web_capture_ui"}:
        return False
    if str(conversation_url or "").strip():
        return False
    current_url = str(page_url or "").strip()
    if _chatgpt_conversation_id_from_url(current_url):
        return False
    return True


async def _chatgpt_maybe_close_page(
    page,
    *,
    tool: str,
    close_context: bool,
    conversation_url: str | None,
) -> bool:
    if page is None:
        return False
    preserve = _chatgpt_should_preserve_cdp_page(
        tool=tool,
        close_context=close_context,
        conversation_url=conversation_url,
        page_url=str(getattr(page, "url", "") or ""),
    )
    if preserve:
        return False
    try:
        await page.close()
        return True
    except Exception:
        return False


async def _chatgpt_clear_stale_blocked_state_if_active(*, ctx: Context | None, action: str) -> dict[str, Any] | None:
    state = await _chatgpt_read_blocked_state()
    if _retry_after_seconds_from_blocked_state(state) is None:
        return None
    prev = await _chatgpt_clear_blocked_state()
    await _ctx_info(ctx, f"Cleared stale ChatGPT blocked/cooldown state after successful {action}.")
    return prev

@mcp.tool(
    name="chatgpt_web_rate_limit_status",
    description="Return server-side ChatGPT send-prompt rate-limit status (min interval + last sent timestamps).",
    structured_output=True,
)
async def chatgpt_web_rate_limit_status(ctx: Context | None = None) -> dict[str, Any]:
    rate_limit_file = _chatgpt_global_rate_limit_file()
    min_interval = _min_prompt_interval_seconds()
    last_in_process = float(_LAST_CHATGPT_PROMPT_SENT_AT or 0.0)
    last_in_global = float(_chatgpt_global_last_sent_at(rate_limit_file)) if rate_limit_file is not None else 0.0
    last_effective = max(last_in_process, last_in_global)
    now = time.time()
    since = max(0.0, now - last_effective) if last_effective > 0 else None
    return {
        "ok": True,
        "status": "completed",
        "server_pid": os.getpid(),
        "min_interval_seconds": min_interval,
        "last_sent_at_in_process": last_in_process,
        "last_sent_at_global_file": last_in_global,
        "last_sent_at_effective": last_effective,
        "seconds_since_last_effective": since,
        "global_rate_limit_file": str(rate_limit_file) if rate_limit_file is not None else None,
    }


@mcp.tool(
    name="chatgpt_web_tab_stats",
    description="Return tab/concurrency stats for the ChatGPT/Gemini/Qwen drivers.",
    structured_output=True,
)
async def chatgpt_web_tab_stats(ctx: Context | None = None) -> dict[str, Any]:
    chatgpt_max = int(_chatgpt_max_concurrent_pages())
    gemini_max = int(_gemini_max_concurrent_pages())
    qwen_max = int(_qwen_max_concurrent_pages())
    chatgpt_sema = _chatgpt_page_semaphore()
    gemini_sema = _gemini_page_semaphore()
    qwen_sema = _qwen_page_semaphore()
    return {
        "ok": True,
        "status": "completed",
        "server_pid": os.getpid(),
        "chatgpt": {
            "max_pages": chatgpt_max,
            "in_use": _sema_in_use(chatgpt_sema, chatgpt_max),
            "limit_hits": int(_concurrency._CHATGPT_TAB_LIMIT_HITS),
            "last_limit_hit_at": _concurrency._CHATGPT_TAB_LAST_HIT_AT,
        },
        "gemini": {
            "max_pages": gemini_max,
            "in_use": _sema_in_use(gemini_sema, gemini_max),
            "limit_hits": int(_concurrency._GEMINI_TAB_LIMIT_HITS),
            "last_limit_hit_at": _concurrency._GEMINI_TAB_LAST_HIT_AT,
        },
        "qwen": {
            "max_pages": qwen_max,
            "in_use": _sema_in_use(qwen_sema, qwen_max),
            "limit_hits": int(_concurrency._QWEN_TAB_LIMIT_HITS),
            "last_limit_hit_at": _concurrency._QWEN_TAB_LAST_HIT_AT,
        },
    }


@mcp.tool(
    name="chatgpt_web_idempotency_get",
    description=(
        "Fetch the cached status/conversation_url for a previous `chatgpt_web_ask` by idempotency_key, without sending a prompt.\n"
        "Useful when a client aborted/disconnected and wants to resume via `chatgpt_web_wait`.\n"
        "Note: reads only within the caller's idempotency namespace."
    ),
    structured_output=True,
)
async def chatgpt_web_idempotency_get(
    idempotency_key: str,
    include_result: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    started_at = time.time()
    run_id = _run_id(tool="chatgpt_web_idempotency_get")
    namespace = _idempotency_namespace(ctx)
    key = _normalize_idempotency_key(idempotency_key)

    record = await _idempotency_lookup(namespace=namespace, tool="chatgpt_web_ask", idempotency_key=key)
    if record is None:
        result = {
            "ok": False,
            "status": "not_found",
            "found": False,
            "idempotency_namespace": namespace,
            "idempotency_key": key,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
        }
        _maybe_append_call_log(
            {
                "tool": "chatgpt_web_idempotency_get",
                "status": "not_found",
                "ok": False,
                "run_id": run_id,
                "elapsed_seconds": result.get("elapsed_seconds"),
                "idempotency_key": key,
                "idempotency_namespace": namespace,
            }
        )
        return result

    filtered = dict(record)
    if not include_result:
        filtered.pop("result", None)
    elif isinstance(filtered.get("result"), dict):
        filtered["result"] = _chatgpt_maybe_offload_answer_result(
            dict(filtered["result"]),
            tool="chatgpt_web_idempotency_get",
            run_id=run_id,
        )

    result = {
        "ok": True,
        "status": "completed",
        "found": True,
        "idempotency_namespace": namespace,
        "idempotency_key": key,
        "record": filtered,
        "elapsed_seconds": round(time.time() - started_at, 3),
        "run_id": run_id,
    }
    _maybe_append_call_log(
        {
            "tool": "chatgpt_web_idempotency_get",
            "status": "completed",
            "ok": True,
            "run_id": run_id,
            "elapsed_seconds": result.get("elapsed_seconds"),
            "idempotency_key": key,
            "idempotency_namespace": namespace,
            "found": True,
            "include_result": bool(include_result),
        }
    )
    return result


@mcp.tool(
    name="chatgpt_web_wait_idempotency",
    description=(
        "Wait for the latest assistant message for a previous `chatgpt_web_ask` by idempotency_key, without requiring conversation_url.\n"
        "Useful after client abort/disconnect or when the caller only saved the idempotency_key."
    ),
    structured_output=True,
)
async def chatgpt_web_wait_idempotency(
    idempotency_key: str,
    timeout_seconds: int = 7200,
    min_chars: int = 0,
    ctx: Context | None = None,
) -> dict[str, Any]:
    started_at = time.time()
    namespace = _idempotency_namespace(ctx)
    key = _normalize_idempotency_key(idempotency_key)
    run_id = _run_id(tool="chatgpt_web_wait_idempotency", idempotency_key=key)

    record = await _idempotency_lookup(namespace=namespace, tool="chatgpt_web_ask", idempotency_key=key)
    if record is None:
        result = {
            "ok": False,
            "status": "not_found",
            "answer": "",
            "conversation_url": "",
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "idempotency_key": key,
            "idempotency_namespace": namespace,
        }
        _maybe_append_call_log(
            {
                "tool": "chatgpt_web_wait_idempotency",
                "ok": False,
                "status": "not_found",
                "run_id": run_id,
                "elapsed_seconds": result.get("elapsed_seconds"),
                "idempotency_key": key,
                "idempotency_namespace": namespace,
            }
        )
        return result

    if isinstance(record.get("result"), dict):
        cached = dict(record["result"])
        cached.setdefault("run_id", run_id)
        cached.setdefault("idempotency_key", key)
        cached.setdefault("idempotency_namespace", namespace)
        cached.setdefault("sent", bool(record.get("sent")))
        cached["replayed"] = True
        cached["via"] = "idempotency"
        had_full_ref = _result_has_full_answer_reference(cached)
        cached = _chatgpt_maybe_offload_answer_result(
            cached,
            tool="chatgpt_web_wait_idempotency",
            run_id=str(cached.get("run_id") or run_id),
        )
        if cached.get("answer_saved") and not had_full_ref:
            try:
                idem = _IdempotencyContext(
                    namespace=namespace,
                    tool="chatgpt_web_ask",
                    key=key,
                    request_hash=str(record.get("request_hash") or ""),
                )
                await _idempotency_update(
                    idem,
                    status=str(cached.get("status") or "completed"),
                    sent=bool(record.get("sent")),
                    conversation_url=str(cached.get("conversation_url") or ""),
                    result=cached,
                )
            except Exception:
                pass
        _maybe_append_call_log(
            {
                "tool": "chatgpt_web_wait_idempotency",
                "ok": bool(cached.get("ok", True)),
                "status": cached.get("status"),
                "run_id": run_id,
                "elapsed_seconds": 0.0,
                "idempotency_key": key,
                "idempotency_namespace": namespace,
                "replayed": True,
                "answer_chars": int(cached.get("answer_chars") or len((cached.get("answer") or "").strip())),
            }
        )
        status = str(cached.get("status") or "").strip().lower()
        if status and status not in {"in_progress"}:
            return cached

    conversation_url = str(record.get("conversation_url") or "").strip()
    if not conversation_url:
        msg = "idempotency record has no conversation_url yet; retry later or call chatgpt_web_idempotency_get()."
        result = {
            "ok": False,
            "status": "error",
            "answer": "",
            "conversation_url": "",
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "idempotency_key": key,
            "idempotency_namespace": namespace,
            "sent": bool(record.get("sent")),
            "error_type": "RuntimeError",
            "error": msg,
        }
        _maybe_append_call_log(
            {
                "tool": "chatgpt_web_wait_idempotency",
                "ok": False,
                "status": "error",
                "run_id": run_id,
                "elapsed_seconds": result.get("elapsed_seconds"),
                "idempotency_key": key,
                "idempotency_namespace": namespace,
                "sent": bool(record.get("sent")),
                "error_type": "RuntimeError",
                "error": msg,
            }
        )
        return result

    idem = _IdempotencyContext(
        namespace=namespace,
        tool="chatgpt_web_ask",
        key=key,
        request_hash=str(record.get("request_hash") or ""),
    )
    job_key = (namespace, "chatgpt_web_ask", key)

    async def _factory() -> dict[str, Any]:
        runner = _ASK_RESUME_JOB_RUNNER or _default_ask_resume_job_runner
        return await runner(
            conversation_url=conversation_url,
            timeout_seconds=timeout_seconds,
            deep_research_requested=False,
            min_chars_override=min_chars,
            idempotency=idem,
            existing_record=record,
            run_id=run_id,
            ctx=ctx,
        )

    job = await asyncio.shield(_get_or_start_job(job_key, kind="resume_wait", factory=_factory))
    result = await asyncio.shield(job.task)
    result.setdefault("idempotency_key", key)
    result.setdefault("idempotency_namespace", namespace)
    result.setdefault("sent", True)
    result["replayed"] = True
    result["via"] = "idempotency"
    return result


@mcp.tool(
    name="chatgpt_web_answer_get",
    description=(
        "Fetch a previously persisted full answer blob by answer_id.\n"
        "Use this when tool outputs are truncated in the client; answers are stored under MCP_ANSWER_DIR/CHATGPT_ANSWER_DIR."
    ),
    structured_output=True,
)
async def chatgpt_web_answer_get(
    answer_id: str,
    offset: int = 0,
    max_chars: int = 8000,
    ctx: Context | None = None,
) -> dict[str, Any]:
    started_at = time.time()
    run_id = _run_id(tool="chatgpt_web_answer_get")
    key = str(answer_id or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{32}", key):
        return {
            "ok": False,
            "status": "error",
            "answer_id": key,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": "ValueError",
            "error": "answer_id must be a 32-char hex string.",
        }

    answer_dir = _chatgpt_answer_dir()
    meta_path = answer_dir / f"{key}.meta.json"
    if not meta_path.exists():
        return {
            "ok": False,
            "status": "not_found",
            "answer_id": key,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
        }

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "ok": False,
            "status": "error",
            "answer_id": key,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": type(exc).__name__,
            "error": _coerce_error_text(exc),
        }

    file_name = str((meta or {}).get("file_name") or "").strip()
    file_name = Path(file_name).name if file_name else f"{key}.txt"
    answer_path = (answer_dir / file_name).resolve()
    answer_dir_resolved = answer_dir.resolve()
    if answer_dir_resolved not in answer_path.parents:
        return {
            "ok": False,
            "status": "error",
            "answer_id": key,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": "RuntimeError",
            "error": "answer path escapes answer_dir",
        }

    try:
        content = answer_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return {
            "ok": False,
            "status": "error",
            "answer_id": key,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": type(exc).__name__,
            "error": _coerce_error_text(exc),
        }

    total = len(content)
    try:
        start = max(0, int(offset))
    except Exception:
        start = 0
    try:
        size = max(1, min(20000, int(max_chars)))
    except Exception:
        size = 8000

    chunk = content[start : start + size]
    next_offset = start + len(chunk)
    done = next_offset >= total
    result = {
        "ok": True,
        "status": "completed",
        "answer_id": key,
        "answer_format": str((meta or {}).get("answer_format") or "text"),
        "answer_sha256": str((meta or {}).get("answer_sha256") or "").strip() or None,
        "answer_chars": int((meta or {}).get("answer_chars") or total),
        "offset": start,
        "returned_chars": len(chunk),
        "next_offset": None if done else next_offset,
        "done": bool(done),
        "chunk": chunk,
        "elapsed_seconds": round(time.time() - started_at, 3),
        "run_id": run_id,
    }
    _maybe_append_call_log(
        {
            "tool": "chatgpt_web_answer_get",
            "status": "completed",
            "ok": True,
            "run_id": run_id,
            "elapsed_seconds": result.get("elapsed_seconds"),
            "answer_id": key,
            "params": {"offset": start, "max_chars": size},
        }
    )
    return result


_CHATGPT_FETCH_CONVERSATION_JSON_TEXT_JS = r"""
async (conversationId) => {
  const cid = String(conversationId || "").trim();
  if (!cid) throw new Error("missing conversationId");
  // ChatGPT's backend-api endpoints may require an access token from /api/auth/session.
  // Do NOT return tokens; keep them in-page only.
  let accessToken = null;
  let sessionStatus = null;
  try {
    const sresp = await fetch(`/api/auth/session`, { credentials: "include" });
    sessionStatus = sresp.status;
    if (sresp.ok) {
      const s = await sresp.json();
      accessToken = (s && (s.accessToken || s.access_token)) || null;
    }
  } catch (e) {}

  const headers = { "Accept": "application/json" };
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  // Best-effort: some deployments also key on a device id header.
  try {
    const deviceId = localStorage.getItem("oai-device-id");
    if (deviceId) headers["OAI-Device-Id"] = String(deviceId);
  } catch (e) {}

  const resp = await fetch(`/backend-api/conversation/${cid}`, { credentials: "include", headers });
  const text = await resp.text();
  return { ok: resp.ok, status: resp.status, text, session_status: sessionStatus, authed: !!accessToken };
};
"""


_CHATGPT_EXPORT_CONVERSATION_DOM_JS = r"""
() => {
  const out = [];
  const nodes = Array.from(document.querySelectorAll('[data-message-author-role]'));
  for (const el of nodes) {
    const role = (el.getAttribute('data-message-author-role') || '').trim();
    let text = '';
    const md = el.querySelector('div.markdown, div.prose, [data-testid="markdown"]');
    if (md) text = md.innerText || md.textContent || '';
    else text = el.innerText || el.textContent || '';
    text = String(text || '').trim();
    if (!role && !text) continue;
    out.push({ role, text });
  }
  return out;
}
"""


@mcp.tool(
    name="chatgpt_web_conversation_export",
    description=(
        "Export a ChatGPT conversation (JSON) without sending a prompt.\n"
        "Fetches via the ChatGPT Web backend API using the logged-in browser session, saves to disk, and returns a pointer."
    ),
    structured_output=True,
)
async def chatgpt_web_conversation_export(
    conversation_url: str,
    timeout_seconds: int = 60,
    dst_path: str | None = None,
    allow_dom_fallback: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    started_at = time.time()
    run_id = _run_id(tool="chatgpt_web_conversation_export")

    url = str(conversation_url or "").strip()
    if not url:
        return {
            "ok": False,
            "status": "error",
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": "ValueError",
            "error": "conversation_url is required.",
        }

    cfg = _load_config()
    try:
        await _chatgpt_enforce_not_blocked(ctx=ctx, action="conversation_export")
    except Exception as exc:
        blocked_state = await _chatgpt_read_blocked_state()
        retry_after = _retry_after_seconds_from_blocked_state(blocked_state)
        status = _blocked_status_from_state(blocked_state) if retry_after else "error"
        return {
            "ok": False,
            "status": status,
            "conversation_url": url,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": type(exc).__name__,
            "error": _coerce_error_text(exc),
            "blocked_state": blocked_state,
            "retry_after_seconds": retry_after,
        }

    env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
    with env_ctx:
        async with _page_slot(kind="chatgpt", ctx=ctx), async_playwright() as p:
            browser = None
            context = None
            page = None
            close_context = False
            try:
                browser, context, page, close_context = await _open_chatgpt_page(p, cfg, conversation_url=url, ctx=ctx)
                await _chatgpt_install_netlog(page, tool="chatgpt_web_conversation_export", run_id=run_id, ctx=ctx)
                effective_url = str((page.url if page is not None else url) or url).strip()

                # Best-effort: let the conversation UI hydrate before attempting export.
                try:
                    await page.locator("[data-message-author-role]").first.wait_for(timeout=8_000)
                except Exception:
                    pass
                try:
                    await _wait_for_message_list_to_settle(page, timeout_ms=10_000, stable_ms=1_200)
                except Exception:
                    pass

                conversation_id = _chatgpt_conversation_id_from_url(effective_url) or _chatgpt_conversation_id_from_url(url)
                if not conversation_id and page is not None:
                    try:
                        alt = await _chatgpt_wait_for_conversation_url(page, timeout_seconds=8.0)
                        if alt and isinstance(alt, str):
                            effective_url = alt.strip() or effective_url
                    except Exception:
                        pass
                    conversation_id = _chatgpt_conversation_id_from_url(effective_url) or _chatgpt_conversation_id_from_url(url)

                if not conversation_id:
                    raise RuntimeError(f"Cannot parse conversation id from url: {effective_url}")

                fetched = await page.evaluate(_CHATGPT_FETCH_CONVERSATION_JSON_TEXT_JS, conversation_id)
                if not isinstance(fetched, dict):
                    raise RuntimeError(f"Unexpected conversation fetch result type: {type(fetched).__name__}")
                ok = bool(fetched.get("ok"))
                status_code = int(fetched.get("status") or 0)
                text = str(fetched.get("text") or "")
                export_kind = "backend_api"
                backend_error = None
                conversation_json = text

                if (not ok) or status_code >= 400:
                    if not bool(allow_dom_fallback):
                        raise RuntimeError(
                            f"backend-api conversation fetch failed (HTTP {status_code}): "
                            f"{_coerce_error_text(text, limit=600) if text else 'no body'}"
                        )
                    export_kind = "dom_messages"
                    backend_error = _coerce_error_text(text, limit=600) if text else None
                    messages = None
                    for _attempt in range(2):
                        try:
                            await page.locator("[data-message-author-role]").first.wait_for(timeout=8_000)
                        except Exception:
                            pass
                        try:
                            await _wait_for_message_list_to_settle(page, timeout_ms=10_000, stable_ms=1_200)
                        except Exception:
                            pass
                        try:
                            messages = await page.evaluate(_CHATGPT_EXPORT_CONVERSATION_DOM_JS)
                        except Exception:
                            messages = None
                        if isinstance(messages, list) and messages:
                            break
                        try:
                            await page.wait_for_timeout(1_000)
                        except Exception:
                            pass
                    if not isinstance(messages, list) or not messages:
                        raise RuntimeError(
                            f"backend-api conversation fetch failed (HTTP {status_code}): {backend_error or 'no body'}"
                        )

                    title = None
                    try:
                        title = await page.title()
                    except Exception:
                        title = None
                    if isinstance(title, str):
                        title = title.strip()
                        if title.lower().endswith(" - chatgpt"):
                            title = title[: -len(" - chatgpt")].strip()
                        if title.lower() == "chatgpt":
                            title = ""

                    export_obj = _chatgpt_build_export_conversation_object_from_dom_messages(
                        messages=[m for m in messages if isinstance(m, dict)],
                        conversation_url=effective_url,
                        conversation_id=conversation_id,
                        backend_status=status_code,
                        backend_error=backend_error,
                        title=title,
                    )
                    # Backward compatible fields (ops scripts + older clients).
                    export_obj["export_kind"] = export_kind
                    export_obj["conversation_url"] = effective_url
                    export_obj["backend_status"] = status_code
                    export_obj["backend_error"] = backend_error
                    export_obj["messages"] = messages
                    conversation_json = json.dumps(export_obj, ensure_ascii=False, indent=2)
                else:
                    try:
                        export_obj = json.loads(conversation_json)
                    except Exception:
                        export_obj = None
                    if isinstance(export_obj, dict):
                        export_obj["conversation_url"] = effective_url
                        export_obj.setdefault("conversation_id", conversation_id)
                        chatgptrest_export = export_obj.get("chatgptrest_export")
                        if not isinstance(chatgptrest_export, dict):
                            chatgptrest_export = {}
                        chatgptrest_export.setdefault("export_kind", export_kind)
                        export_obj["chatgptrest_export"] = chatgptrest_export

                        needs_deep_research_widget = (
                            "implicit_link::connector_openai_deep_research" in conversation_json
                            or "Deep Research App/implicit_link" in conversation_json
                        )
                        if needs_deep_research_widget:
                            widget = await _chatgpt_best_effort_deep_research_widget_text(page, ctx=ctx)
                            if widget is not None:
                                widget_text, widget_meta = widget
                                widget_text = str(widget_text or "").strip()
                                if widget_text:
                                    export_obj["deep_research_widget_export"] = {
                                        "markdown": widget_text,
                                        "meta": widget_meta if isinstance(widget_meta, dict) else {},
                                    }
                                    chatgptrest_export["deep_research_widget_injected"] = True
                                    conversation_json = json.dumps(export_obj, ensure_ascii=False, indent=2)

                saved = _chatgpt_write_conversation_export_file(
                    conversation_json=conversation_json,
                    tool="chatgpt_web_conversation_export",
                    run_id=run_id,
                    conversation_url=effective_url,
                    conversation_id=conversation_id,
                    dst_path=dst_path,
                )
                preview = conversation_json[:1200]
                result = {
                    "ok": True,
                    "status": "completed",
                    "conversation_url": effective_url,
                    "conversation_id": conversation_id,
                    **saved,
                    "export_kind": export_kind,
                    "backend_status": status_code,
                    "backend_error": backend_error,
                    "preview": preview,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "blocked_state": await _chatgpt_read_blocked_state(),
                }
                _maybe_append_call_log(
                    {
                        "tool": "chatgpt_web_conversation_export",
                        "status": "completed",
                        "ok": True,
                        "run_id": run_id,
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "conversation_url": effective_url,
                        "conversation_id": conversation_id,
                        "export_id": result.get("export_id"),
                        "export_kind": export_kind,
                    }
                )
                return result
            except Exception as exc:
                if _is_tab_limit_error(exc):
                    return _tab_limit_result(
                        tool="chatgpt_web_conversation_export",
                        run_id=run_id,
                        started_at=started_at,
                        conversation_url=url,
                    )
                blocked_state = await _chatgpt_read_blocked_state()
                retry_after = _retry_after_seconds_from_blocked_state(blocked_state)
                status = _blocked_status_from_state(blocked_state) if retry_after else "error"
                result = {
                    "ok": False,
                    "status": status,
                    "conversation_url": url,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "error_type": type(exc).__name__,
                    "error": _coerce_error_text(exc),
                    "blocked_state": blocked_state,
                    "retry_after_seconds": retry_after,
                }
                _maybe_append_call_log(
                    {
                        "tool": "chatgpt_web_conversation_export",
                        "ok": False,
                        "status": status,
                        "run_id": run_id,
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "conversation_url": url,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                return result
            finally:
                try:
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
                    if close_context and context is not None:
                        await context.close()
                finally:
                    if browser is not None:
                        await browser.close()


@mcp.tool(
    name="chatgpt_web_blocked_status",
    description="Return server-side ChatGPT blocked/cooldown status (verification/login stop-the-world).",
    structured_output=True,
)
async def chatgpt_web_blocked_status(ctx: Context | None = None) -> dict[str, Any]:
    state = await _chatgpt_read_blocked_state()
    until = state.get("blocked_until")
    try:
        blocked_until = float(until) if until is not None else 0.0
    except Exception:
        blocked_until = 0.0
    now = time.time()
    retry_after = _retry_after_seconds_from_blocked_state(state)
    return {
        "ok": True,
        "status": "completed",
        "server_pid": os.getpid(),
        "now": now,
        "blocked": bool(blocked_until > 0 and now < blocked_until),
        "blocked_until": blocked_until,
        "seconds_until_unblocked": max(0.0, blocked_until - now) if blocked_until > 0 else 0.0,
        "retry_after_seconds": retry_after,
        "reason": state.get("reason"),
        "state_file": str(_chatgpt_blocked_state_file()),
        "state": state,
    }


@mcp.tool(
    name="chatgpt_web_clear_blocked",
    description="Clear server-side ChatGPT blocked/cooldown state (after manual verification/login).",
    structured_output=True,
)
async def chatgpt_web_clear_blocked(ctx: Context | None = None) -> dict[str, Any]:
    prev = await _chatgpt_clear_blocked_state()
    await _ctx_info(ctx, "Cleared ChatGPT blocked/cooldown state.")
    return {
        "ok": True,
        "status": "completed",
        "cleared": True,
        "prev": prev,
        "state_file": str(_chatgpt_blocked_state_file()),
    }


@mcp.tool(
    name="chatgpt_web_self_check",
    description="Open ChatGPT and verify the composer UI without sending a prompt (health check).",
    structured_output=True,
)
async def chatgpt_web_self_check(
    conversation_url: str | None = None,
    timeout_seconds: int = 30,
    ctx: Context | None = None,
) -> dict[str, Any]:
    await _chatgpt_enforce_not_blocked(ctx=ctx, action="self_check")
    cfg = _load_config()
    started_at = time.time()
    run_id = _run_id(tool="chatgpt_web_self_check")
    env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
    with env_ctx:
        async with _page_slot(kind="chatgpt", ctx=ctx), async_playwright() as p:
            browser = None
            context = None
            page = None
            close_context = False
            try:
                browser, context, page, close_context = await _open_chatgpt_page(
                    p, cfg, conversation_url=conversation_url, ctx=ctx
                )
                await _chatgpt_install_netlog(page, tool="chatgpt_web_self_check", run_id=run_id, ctx=ctx)
                await _find_prompt_box(page, timeout_ms=max(5_000, int(timeout_seconds * 1000)))
                await _wait_for_message_list_to_settle(page)
                cleared_prev = await _chatgpt_clear_stale_blocked_state_if_active(ctx=ctx, action="self_check")
                title = (await page.title()) if page is not None else ""
                model_text = await _current_model_text(page) if page is not None else ""
                result = {
                    "ok": True,
                    "status": "completed",
                    "conversation_url": (page.url if page is not None else None),
                    "title": (title or "").strip(),
                    "model_text": model_text,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "blocked_state": await _chatgpt_read_blocked_state(),
                }
                if cleared_prev is not None:
                    result["cleared_stale_blocked_state"] = True
                    result["previous_blocked_state"] = cleared_prev
                _maybe_append_call_log(
                    {
                        "tool": "chatgpt_web_self_check",
                        "ok": True,
                        "status": "completed",
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "conversation_url": conversation_url,
                        },
                    }
                )
                return result
            except Exception as exc:
                if _is_tab_limit_error(exc):
                    result = _tab_limit_result(
                        tool="chatgpt_web_self_check",
                        run_id=run_id,
                        started_at=started_at,
                        conversation_url=conversation_url,
                    )
                    _maybe_append_call_log(
                        {
                            "tool": "chatgpt_web_self_check",
                            "ok": False,
                            "status": result.get("status"),
                            "elapsed_seconds": result.get("elapsed_seconds"),
                            "run_id": run_id,
                            "params": {
                                "timeout_seconds": timeout_seconds,
                                "conversation_url": conversation_url,
                            },
                            "error_type": result.get("error_type"),
                            "error": result.get("error"),
                        }
                    )
                    return result
                blocked_state = await _chatgpt_read_blocked_state()
                result = {
                    "ok": False,
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": _coerce_error_text(exc),
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "blocked_state": blocked_state,
                    "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
                }
                _maybe_append_call_log(
                    {
                        "tool": "chatgpt_web_self_check",
                        "ok": False,
                        "status": "error",
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "conversation_url": conversation_url,
                        },
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                return result
            finally:
                try:
                    await _chatgpt_maybe_close_page(
                        page,
                        tool="chatgpt_web_self_check",
                        close_context=close_context,
                        conversation_url=conversation_url,
                    )
                    if close_context and context is not None:
                        await context.close()
                finally:
                    if browser is not None:
                        await browser.close()


_ASK_SEND_JOB_RUNNER: Callable[..., Awaitable[dict[str, Any]]] | None = None
_ASK_RESUME_JOB_RUNNER: Callable[..., Awaitable[dict[str, Any]]] | None = None


async def _default_ask_send_job_runner(
    *,
    question: str,
    conversation_url: str | None,
    timeout_seconds: int,
    model: str | None,
    thinking_time: str | None,
    deep_research: bool,
    web_search: bool,
    agent_mode: bool,
    github_repo: str | None,
    upload_paths: list[Path],
    uploaded_files: list[dict[str, Any]],
    idempotency: _IdempotencyContext,
    run_id: str,
    fire_and_forget: bool = False,
    ctx: Context | None,
) -> dict[str, Any]:
    started_at = time.time()
    try:
        return await _ask_locked(
            question=question,
            conversation_url=conversation_url,
            timeout_seconds=timeout_seconds,
            model=model,
            thinking_time=thinking_time,
            deep_research=deep_research,
            web_search=web_search,
            agent_mode=agent_mode,
            github_repo=github_repo,
            upload_paths=upload_paths,
            uploaded_files=uploaded_files,
            idempotency=idempotency,
            run_id=run_id,
            fire_and_forget=fire_and_forget,
            ctx=ctx,
        )
    except Exception as exc:
        try:
            await _idempotency_update(idempotency, status="error", error=f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
        blocked_state = await _chatgpt_read_blocked_state()
        status = _blocked_status_from_state(blocked_state) if _retry_after_seconds_from_blocked_state(blocked_state) else "error"
        return {
            "ok": False,
            "status": status,
            "answer": "",
            "conversation_url": str(conversation_url or "").strip(),
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": type(exc).__name__,
            "error": _coerce_error_text(exc),
            "blocked_state": blocked_state,
            "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
            "uploaded_files": uploaded_files,
        }


async def _default_ask_resume_job_runner(
    *,
    conversation_url: str,
    timeout_seconds: int,
    deep_research_requested: bool,
    min_chars_override: int | None = None,
    idempotency: _IdempotencyContext,
    existing_record: dict[str, Any] | None,
    run_id: str,
    ctx: Context | None,
) -> dict[str, Any]:
    started_at = time.time()
    min_chars = _deep_research_report_min_chars() if deep_research_requested else 0
    if min_chars_override is not None:
        try:
            min_chars = max(0, int(min_chars_override))
        except Exception:
            min_chars = 0

    wait_result = await wait(
        conversation_url=conversation_url,
        timeout_seconds=timeout_seconds,
        min_chars=min_chars,
        ctx=ctx,
    )

    base_result = (existing_record or {}).get("result") if isinstance((existing_record or {}).get("result"), dict) else {}
    model_text = str((base_result or {}).get("model_text") or "")
    thinking_time = (base_result or {}).get("thinking_time")
    thinking_time_requested = (base_result or {}).get("thinking_time_requested")
    uploaded_files = (base_result or {}).get("uploaded_files") or []

    result: dict[str, Any] = {
        "ok": bool(wait_result.get("ok")),
        "answer": str(wait_result.get("answer") or ""),
        "status": str(wait_result.get("status") or "in_progress"),
        "conversation_url": str(wait_result.get("conversation_url") or conversation_url),
        "elapsed_seconds": round(time.time() - started_at, 3),
        "run_id": run_id,
        "model_text": model_text,
        "thinking_time": thinking_time,
        "thinking_time_requested": thinking_time_requested,
        "uploaded_files": uploaded_files,
        "resume": True,
    }
    if isinstance(wait_result.get("answer_format"), str):
        result["answer_format"] = str(wait_result.get("answer_format"))
    for key in (
        "answer_id",
        "answer_path",
        "answer_sha256",
        "answer_chars",
        "answer_returned_chars",
        "answer_truncated",
        "answer_saved",
    ):
        if key in wait_result:
            result[key] = wait_result.get(key)
    if isinstance(wait_result.get("debug_artifacts"), dict) and wait_result.get("debug_artifacts"):
        result["debug_artifacts"] = wait_result.get("debug_artifacts")
    if isinstance(wait_result.get("blocked_state"), dict) and wait_result.get("blocked_state"):
        result["blocked_state"] = wait_result.get("blocked_state")
        result["retry_after_seconds"] = wait_result.get("retry_after_seconds")
    if isinstance(wait_result.get("error_type"), str) and str(wait_result.get("error_type") or "").strip():
        result["error_type"] = str(wait_result.get("error_type"))
    if isinstance(wait_result.get("error"), str) and str(wait_result.get("error") or "").strip():
        result["error"] = str(wait_result.get("error"))

    result = _chatgpt_maybe_offload_answer_result(
        result,
        tool="chatgpt_web_ask",
        run_id=run_id,
    )

    try:
        await _idempotency_update(
            idempotency,
            status=str(result.get("status") or "in_progress"),
            sent=True,
            conversation_url=str(result.get("conversation_url") or ""),
            result=result,
        )
    except Exception:
        pass
    return result


@mcp.tool(
    name="chatgpt_web_capture_ui",
    description=(
        "Open ChatGPT Web and capture screenshots of common UI surfaces (for debugging selector breakage).\n"
        "Does NOT send any prompt.\n"
        "Writes screenshots under CHATGPT_UI_SNAPSHOT_DIR (default: artifacts/ui_snapshots/) and updates a markdown\n"
        "reference doc at CHATGPT_UI_SNAPSHOT_DOC (default: docs/chatgpt_web_ui_reference.md)."
    ),
    structured_output=True,
)
async def chatgpt_web_capture_ui(
    conversation_url: str | None = None,
    mode: str = "full",
    timeout_seconds: int = 90,
    out_dir: str | None = None,
    write_doc: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    await _chatgpt_enforce_not_blocked(ctx=ctx, action="capture_ui")
    cfg = _load_config()
    started_at = time.time()
    run_id = _run_id(tool="chatgpt_web_capture_ui")

    normalized_mode = re.sub(r"[^a-z]+", "", (mode or "").strip().lower())
    if normalized_mode not in {"basic", "full"}:
        return {
            "ok": False,
            "error_type": "ValueError",
            "error": f"Unsupported mode: {mode} (use 'basic' or 'full')",
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
        }

    run_dir = Path(out_dir).expanduser() if (out_dir or "").strip() else _ui_snapshot_run_dir(_ui_snapshot_base_dir())
    doc_path = _ui_snapshot_doc_path()

    env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
    with env_ctx:
        async with _page_slot(kind="chatgpt", ctx=ctx), async_playwright() as p:
            browser = None
            context = None
            page = None
            close_context = False
            title = ""
            model_text = ""
            conversation_url_effective = ""
            targets: list[dict[str, Any]] = []
            notes: list[str] = []
            try:
                browser, context, page, close_context = await _open_chatgpt_page(
                    p, cfg, conversation_url=conversation_url, ctx=ctx
                )
                await _chatgpt_install_netlog(page, tool="chatgpt_web_capture_ui", run_id=run_id, ctx=ctx)
                conversation_url_effective = (page.url or "").strip()
                cleared_prev = await _chatgpt_clear_stale_blocked_state_if_active(ctx=ctx, action="capture_ui")

                await _find_prompt_box(page, timeout_ms=max(5_000, int(timeout_seconds * 1000)))
                await _wait_for_message_list_to_settle(page)

                try:
                    title = (await page.title()) or ""
                except Exception:
                    title = ""
                try:
                    model_text = await _current_model_text(page)
                except Exception:
                    model_text = ""

                # Baseline surfaces (safe; no stateful toggles).
                targets.append(await _ui_screenshot(page, target="page_full", out_dir=run_dir, full_page=True))

                prompt = await _find_prompt_box(page)
                targets.append(await _ui_screenshot(page, target="composer_prompt", out_dir=run_dir, locator=prompt))

                plus_btn = page.locator(_CHATGPT_PLUS_BUTTON_SELECTOR)
                targets.append(await _ui_screenshot(page, target="composer_plus_button", out_dir=run_dir, locator=plus_btn))

                # Some builds only render the send button after input; type a harmless stub (not sent)
                # so we can capture the selector surface for debugging.
                try:
                    await prompt.click()
                    await prompt.type("hi", delay=25, timeout=5_000)
                    await _human_pause(page)
                except Exception:
                    pass

                send_btn = page.locator(_CHATGPT_SEND_BUTTON_SELECTOR)
                targets.append(await _ui_screenshot(page, target="composer_send_button", out_dir=run_dir, locator=send_btn))

                # Clear the stub text to avoid affecting later probes/screenshots.
                try:
                    await prompt.click()
                    await page.keyboard.press("Control+A")
                    await page.keyboard.press("Backspace")
                    await _human_pause(page)
                except Exception:
                    try:
                        await prompt.fill("")
                    except Exception:
                        pass

                model_selector_btn = page.locator("button[aria-label^='Model selector']")
                targets.append(
                    await _ui_screenshot(page, target="model_selector_button", out_dir=run_dir, locator=model_selector_btn)
                )
                if await model_selector_btn.count() and await model_selector_btn.first.is_visible():
                    try:
                        await model_selector_btn.first.click()
                        await _human_pause(page)
                        model_menu = page.locator("[role='menu']:visible").first
                        try:
                            await model_menu.wait_for(state="visible", timeout=8_000)
                        except PlaywrightTimeoutError:
                            pass
                        targets.append(
                            await _ui_screenshot(page, target="model_selector_menu", out_dir=run_dir, locator=model_menu)
                        )
                    finally:
                        try:
                            await page.keyboard.press("Escape")
                            await _human_pause(page)
                        except Exception:
                            pass
                else:
                    targets.append(
                        {
                            "target": "model_selector_menu",
                            "error_type": "RuntimeError",
                            "error": "Model selector button not found/visible",
                        }
                    )

                thinking_pill = _composer_pills(page).filter(
                    has_text=re.compile(r"(thinking\b|^Pro$)", re.I)
                )
                targets.append(await _ui_screenshot(page, target="thinking_time_pill", out_dir=run_dir, locator=thinking_pill))
                if await thinking_pill.count() and await thinking_pill.first.is_visible():
                    try:
                        await thinking_pill.first.click()
                        await _human_pause(page)
                        thinking_menu = page.locator("[role='menu']:visible").first
                        try:
                            await thinking_menu.wait_for(state="visible", timeout=8_000)
                        except PlaywrightTimeoutError:
                            pass
                        targets.append(
                            await _ui_screenshot(page, target="thinking_time_menu", out_dir=run_dir, locator=thinking_menu)
                        )
                    finally:
                        try:
                            await page.keyboard.press("Escape")
                            await _human_pause(page)
                        except Exception:
                            pass

                try:
                    menu = await _open_plus_menu(page)
                    targets.append(await _ui_screenshot(page, target="plus_menu", out_dir=run_dir, locator=menu))

                    # Try opening the "More/更多" submenu (if present). Note: taking Playwright element screenshots
                    # of the submenu can collapse it (hover loss). We instead capture the viewport once and crop.
                    submenu_error: dict[str, Any] | None = None
                    submenu_target: Any | None = None
                    try:
                        more = (
                            menu.locator("[role='menuitem']:visible").filter(has_text=re.compile(r"^(More|更多)$", re.I)).first
                        )
                        if await more.count() and await more.is_visible():
                            visible_menus = page.locator("[role='menu']:visible")
                            before = await visible_menus.count()
                            try:
                                await more.hover()
                                await page.wait_for_timeout(200)
                                await _human_pause(page)
                            except Exception:
                                pass
                            after = await visible_menus.count()
                            if after <= before:
                                try:
                                    await more.click()
                                    await _human_pause(page)
                                except Exception:
                                    pass
                                after = await visible_menus.count()
                            if after > before:
                                submenu_target = visible_menus.nth(after - 1)
                                # Keep the hover-triggered submenu open by moving the mouse into it.
                                # (Leaving the "More" menuitem can collapse the submenu before we probe items.)
                                try:
                                    box = await submenu_target.bounding_box()
                                    if box and float(box.get("width") or 0) > 1 and float(box.get("height") or 0) > 1:
                                        x = float(box.get("x") or 0.0) + min(20.0, float(box.get("width") or 0.0) / 2.0)
                                        y = float(box.get("y") or 0.0) + min(20.0, float(box.get("height") or 0.0) / 2.0)
                                        await page.mouse.move(x, y)
                                        await page.wait_for_timeout(80)
                                except Exception:
                                    pass
                            else:
                                submenu_error = {
                                    "target": "plus_menu_more_submenu",
                                    "error_type": "NotFound",
                                    "error": "submenu not opened",
                                }
                        else:
                            submenu_error = {
                                "target": "plus_menu_more_submenu",
                                "error_type": "NotFound",
                                "error": "More menu item not found/visible",
                            }
                    except Exception as exc:
                        submenu_error = {"target": "plus_menu_more_submenu", "error_type": type(exc).__name__, "error": str(exc)}

                    viewport_path = run_dir / "__plus_menu_viewport.png"
                    await page.screenshot(path=str(viewport_path))
                    try:
                        viewport_metrics = await page.evaluate(
                            "() => ({scroll_x: window.scrollX, scroll_y: window.scrollY, inner_width: window.innerWidth, inner_height: window.innerHeight})"
                        )
                    except Exception:
                        viewport_metrics = {}
                    if not isinstance(viewport_metrics, dict):
                        viewport_metrics = {}

                    if submenu_target is not None:
                        targets.append(
                            await _ui_screenshot_from_viewport(
                                page,
                                target="plus_menu_more_submenu",
                                out_dir=run_dir,
                                viewport_path=viewport_path,
                                viewport_metrics=viewport_metrics,
                                locator=submenu_target,
                            )
                        )
                    elif submenu_error is not None:
                        targets.append(submenu_error)

                    # The "More" submenu can be hover-triggered; it may close between the crop screenshot and
                    # the item-detection pass. Re-open it best-effort so `plus_menu_deep_research_item` can be found.
                    if submenu_target is not None:
                        try:
                            visible_menus_now = page.locator("[role='menu']:visible")
                            if await visible_menus_now.count() < 2:
                                more_again = (
                                    menu.locator("[role='menuitem']:visible").filter(has_text=re.compile(r"^(More|更多)$", re.I)).first
                                )
                                if await more_again.count() and await more_again.is_visible():
                                    await more_again.hover()
                                    await page.wait_for_timeout(200)
                                    await _human_pause(page)
                            # Move into the submenu to keep it open while we locate/crop items.
                            box = await submenu_target.bounding_box()
                            if box and float(box.get("width") or 0) > 1 and float(box.get("height") or 0) > 1:
                                x = float(box.get("x") or 0.0) + min(20.0, float(box.get("width") or 0.0) / 2.0)
                                y = float(box.get("y") or 0.0) + min(20.0, float(box.get("height") or 0.0) / 2.0)
                                await page.mouse.move(x, y)
                                await page.wait_for_timeout(80)
                        except Exception:
                            pass

                    # Record whether key items exist in the + menu (base or submenu).
                    menus = page.locator("[role='menu']:visible")
                    items = menus.locator("[role='menuitemradio'], [role='menuitem'], [role='menuitemcheckbox']")

                    wanted_items: list[tuple[str, re.Pattern[str]]] = [
                        # Deep research UI labels vary across experiments/locales; avoid anchored matching.
                        ("deep_research_item", re.compile(r"(?:\bDeep\s*research\b|深度研究|深度调研|深入研究)", re.I)),
                        ("web_search_item", re.compile(r"(Web\s*search|Search\s+the\s+web|Browse\s+the\s+web|网页搜索|联网搜索)", re.I)),
                        ("agent_mode_item", re.compile(r"(Agent\s*mode|Agent|代理模式|代理)", re.I)),
                        (
                            "create_image_item",
                            re.compile(r"^(Create\s*image|Create\s*an\s*image|创建图片|生成图片|生成图像)$", re.I),
                        ),
                    ]
                    for label, pat in wanted_items:
                        item = items.filter(has_text=pat).first
                        targets.append(
                            await _ui_screenshot_from_viewport(
                                page,
                                target=f"plus_menu_{label}",
                                out_dir=run_dir,
                                viewport_path=viewport_path,
                                viewport_metrics=viewport_metrics,
                                locator=item,
                            )
                        )

                    try:
                        upload_item = await _find_upload_menu_item(page, menu)
                        targets.append(
                            await _ui_screenshot_from_viewport(
                                page,
                                target="plus_menu_upload_file_item",
                                out_dir=run_dir,
                                viewport_path=viewport_path,
                                viewport_metrics=viewport_metrics,
                                locator=upload_item,
                            )
                        )
                    except Exception as exc:
                        targets.append(
                            {
                                "target": "plus_menu_upload_file_item",
                                "error_type": type(exc).__name__,
                                "error": str(exc),
                            }
                        )
                except Exception as exc:
                    targets.append({"target": "plus_menu", "error_type": type(exc).__name__, "error": str(exc)})
                finally:
                    try:
                        await page.keyboard.press("Escape")
                        await _human_pause(page)
                    except Exception:
                        pass

                # Full probe: exercise the same selector paths used by the main tools (best-effort).
                if normalized_mode == "full":

                    async def _reset_between_probes(label: str) -> None:
                        try:
                            await _chatgpt_refresh_page(
                                page,
                                ctx=ctx,
                                reason=f"ui probe reset: {label}",
                                phase="ui_probe_reset",
                            )
                        except Exception:
                            return
                        await _find_prompt_box(page, timeout_ms=max(5_000, int(timeout_seconds * 1000)))
                        await _wait_for_message_list_to_settle(page)

                    # Web search
                    await _reset_between_probes("web_search")
                    try:
                        await _ensure_web_search(page, ctx=ctx)
                        pill = _composer_pills(page).filter(
                            has_text=re.compile(r"^(Web search|Search|网页搜索|联网搜索)$", re.I)
                        )
                        targets.append(await _ui_screenshot(page, target="probe_web_search_pill", out_dir=run_dir, locator=pill))
                    except Exception as exc:
                        targets.append({"target": "probe_web_search_pill", "error_type": type(exc).__name__, "error": str(exc)})

                    # Deep research
                    await _reset_between_probes("deep_research")
                    try:
                        await _ensure_deep_research(page, ctx=ctx)
                        pill = _composer_pills(page).filter(has_text=_DEEP_RESEARCH_PILL_RE)
                        targets.append(
                            await _ui_screenshot(page, target="probe_deep_research_pill", out_dir=run_dir, locator=pill)
                        )
                    except Exception as exc:
                        targets.append(
                            {"target": "probe_deep_research_pill", "error_type": type(exc).__name__, "error": str(exc)}
                        )

                    # Agent mode
                    await _reset_between_probes("agent_mode")
                    try:
                        await _ensure_agent_mode(page, ctx=ctx)
                        pill = _composer_pills(page).filter(
                            has_text=re.compile(r"(Agent\s*mode|Agent|代理模式|代理)", re.I)
                        )
                        targets.append(await _ui_screenshot(page, target="probe_agent_mode_pill", out_dir=run_dir, locator=pill))
                    except Exception as exc:
                        targets.append(
                            {"target": "probe_agent_mode_pill", "error_type": type(exc).__name__, "error": str(exc)}
                        )

                    # Create image (toggle + capture prompt box UI)
                    await _reset_between_probes("create_image")
                    try:
                        await _ensure_model(page, model="thinking", ctx=ctx)
                        await _ensure_create_image(page, ctx=ctx)
                        prompt = await _find_prompt_box(page)
                        targets.append(
                            await _ui_screenshot(page, target="probe_create_image_prompt", out_dir=run_dir, locator=prompt)
                        )
                    except Exception as exc:
                        targets.append(
                            {"target": "probe_create_image_prompt", "error_type": type(exc).__name__, "error": str(exc)}
                        )

                    # GitHub connector (enable + open repo picker).
                    await _reset_between_probes("github_connector")
                    try:
                        await _ensure_github_connector(page, ctx=ctx)
                        pill = _composer_pills(page).filter(has_text=re.compile(r"^GitHub$", re.I))
                        targets.append(await _ui_screenshot(page, target="probe_github_pill", out_dir=run_dir, locator=pill))
                        try:
                            repo_menu = await _open_github_repo_menu(page)
                            targets.append(
                                await _ui_screenshot(page, target="probe_github_repo_menu", out_dir=run_dir, locator=repo_menu)
                            )
                        finally:
                            try:
                                await page.keyboard.press("Escape")
                                await _human_pause(page)
                            except Exception:
                                pass
                    except Exception as exc:
                        targets.append({"target": "probe_github_pill", "error_type": type(exc).__name__, "error": str(exc)})

                    # Upload file (dummy) and capture the composer.
                    await _reset_between_probes("upload_file")
                    try:
                        dummy = run_dir / "ui_snapshot_dummy.txt"
                        dummy.write_text("UI snapshot dummy file (generated by chatgpt_web_capture_ui).\n", encoding="utf-8")
                        await _upload_file_via_menu(page, file_path=dummy, ctx=ctx)
                        prompt = await _find_prompt_box(page)
                        targets.append(
                            await _ui_screenshot(page, target="probe_upload_composer", out_dir=run_dir, locator=prompt)
                        )
                        targets.append(await _ui_screenshot(page, target="probe_upload_page_full", out_dir=run_dir, full_page=True))
                    except Exception as exc:
                        targets.append(
                            {"target": "probe_upload_composer", "error_type": type(exc).__name__, "error": str(exc)}
                        )

                # Persist manifest + optional doc for quick diffing.
                run_dir.mkdir(parents=True, exist_ok=True)
                manifest_path = run_dir / "manifest.json"
                payload = {
                    "tool": "chatgpt_web_capture_ui",
                    "run_id": run_id,
                    "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "conversation_url": conversation_url_effective,
                    "title": (title or "").strip(),
                    "model_text": (model_text or "").strip(),
                    "mode": normalized_mode,
                    "targets": targets,
                    "notes": notes,
                }
                manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

                if write_doc:
                    await _ui_write_snapshot_doc(
                        doc_path=doc_path,
                        run_dir=run_dir,
                        conversation_url=conversation_url_effective,
                        title=title,
                        model_text=model_text,
                        targets=targets,
                    )

                result = {
                    "ok": True,
                    "status": "completed",
                    "conversation_url": conversation_url_effective,
                    "run_id": run_id,
                    "mode": normalized_mode,
                    "out_dir": str(run_dir),
                    "manifest_path": str(manifest_path),
                    "doc_path": str(doc_path) if write_doc else None,
                    "targets": targets,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                }
                if cleared_prev is not None:
                    result["cleared_stale_blocked_state"] = True
                    result["previous_blocked_state"] = cleared_prev
                _maybe_append_call_log(
                    {
                        "tool": "chatgpt_web_capture_ui",
                        "ok": True,
                        "status": "completed",
                        "conversation_url": conversation_url_effective,
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "params": {
                            "conversation_url": conversation_url,
                            "mode": normalized_mode,
                            "timeout_seconds": timeout_seconds,
                            "out_dir": out_dir,
                            "write_doc": bool(write_doc),
                        },
                        "out_dir": str(run_dir),
                        "manifest_path": str(manifest_path),
                        "doc_path": str(doc_path) if write_doc else None,
                    }
                )
                return result
            except Exception as exc:
                if _is_tab_limit_error(exc):
                    result = _tab_limit_result(
                        tool="chatgpt_web_capture_ui",
                        run_id=run_id,
                        started_at=started_at,
                        conversation_url=conversation_url_effective or conversation_url,
                        extra={
                            "out_dir": str(run_dir),
                            "doc_path": str(doc_path) if write_doc else None,
                        },
                    )
                    _maybe_append_call_log(
                        {
                            "tool": "chatgpt_web_capture_ui",
                            "ok": False,
                            "status": result.get("status"),
                            "elapsed_seconds": result.get("elapsed_seconds"),
                            "run_id": run_id,
                            "params": {
                                "conversation_url": conversation_url,
                                "mode": normalized_mode,
                                "timeout_seconds": timeout_seconds,
                                "out_dir": out_dir,
                                "write_doc": bool(write_doc),
                            },
                            "error_type": result.get("error_type"),
                            "error": result.get("error"),
                        }
                    )
                    return result
                artifacts: dict[str, str] = {}
                if page is not None:
                    try:
                        artifacts = await _capture_debug_artifacts(page, label="capture_ui_error")
                    except Exception:
                        artifacts = {}
                blocked_state = await _chatgpt_read_blocked_state()
                result = {
                    "ok": False,
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": _coerce_error_text(exc),
                    "run_id": run_id,
                    "conversation_url": conversation_url_effective or conversation_url,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "debug_artifacts": artifacts,
                    "out_dir": str(run_dir),
                    "doc_path": str(doc_path) if write_doc else None,
                    "blocked_state": blocked_state,
                    "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
                }
                _maybe_append_call_log(
                    {
                        "tool": "chatgpt_web_capture_ui",
                        "ok": False,
                        "status": "error",
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "params": {
                            "conversation_url": conversation_url,
                            "mode": normalized_mode,
                            "timeout_seconds": timeout_seconds,
                            "out_dir": out_dir,
                            "write_doc": bool(write_doc),
                        },
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "debug_artifacts": artifacts,
                    }
                )
                return result
            finally:
                try:
                    await _chatgpt_maybe_close_page(
                        page,
                        tool="chatgpt_web_capture_ui",
                        close_context=close_context,
                        conversation_url=conversation_url,
                    )
                    if close_context and context is not None:
                        await context.close()
                finally:
                    if browser is not None:
                        await browser.close()


@mcp.tool(
    name="chatgpt_web_ask",
    description=(
        "Ask ChatGPT on chatgpt.com (web UI automation) and return the final answer text.\n"
        "Optional controls:\n"
        "- model: switch via the top-left model selector (ex: '5.2 pro', 'thinking').\n"
        "- thinking_time: set composer thinking time (ex: 'extended', 'heavy').\n"
        "- deep_research: enable Deep research from the + menu.\n"
        "- web_search: enable Web search (网页搜索/联网搜索) in the composer.\n"
        "- agent_mode: enable Agent mode (代理模式) from the + menu.\n"
        "- github_repo: enable GitHub connector and select a repo.\n"
        "- file_paths: upload local files via the + menu before sending the question."
    ),
    structured_output=True,
)
async def ask(
    question: str,
    idempotency_key: str,
    conversation_url: str | None = None,
    timeout_seconds: int = 600,
    model: str | None = None,
    thinking_time: str | None = None,
    deep_research: bool = False,
    web_search: bool = False,
    agent_mode: bool = False,
    github_repo: str | None = None,
    file_paths: str | list[str] | None = None,
    fire_and_forget: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    started_at = time.time()
    tool_name = "chatgpt_web_ask"
    run_id = _run_id(tool=tool_name, idempotency_key=idempotency_key)
    upload_paths = _resolve_upload_paths(file_paths)
    file_fingerprints = [_file_fingerprint(p) for p in upload_paths]
    idem_file_fingerprints = [_file_fingerprint_for_idempotency(fp) for fp in file_fingerprints]
    idem = _IdempotencyContext(
        namespace=_idempotency_namespace(ctx),
        tool=tool_name,
        key=_normalize_idempotency_key(idempotency_key),
        request_hash=_hash_request(
            {
                "tool": tool_name,
                "question": question,
                "model": model,
                "thinking_time": thinking_time,
                "deep_research": bool(deep_research),
                "web_search": bool(web_search),
                "agent_mode": bool(agent_mode),
                "github_repo": github_repo,
                "file_fingerprints": idem_file_fingerprints,
            }
        ),
    )
    should_execute, existing = await _idempotency_begin(idem)
    replayed = not should_execute

    if (not should_execute) and isinstance((existing or {}).get("result"), dict):
        cached = dict(existing["result"])
        cached.setdefault("run_id", run_id)
        cached.setdefault("idempotency_key", idem.key)
        cached.setdefault("idempotency_namespace", idem.namespace)
        cached.setdefault("sent", bool((existing or {}).get("sent")))
        cached.setdefault(
            "ok",
            bool(
                str(cached.get("status") or "").strip().lower() not in {"error", "blocked", "cooldown"}
                and not str(cached.get("error_type") or "").strip()
                and not str(cached.get("error") or "").strip()
            ),
        )
        cached["replayed"] = True
        had_full_ref = _result_has_full_answer_reference(cached)
        cached = _chatgpt_maybe_offload_answer_result(
            cached,
            tool=tool_name,
            run_id=str(cached.get("run_id") or run_id),
        )
        if cached.get("answer_saved") and not had_full_ref:
            try:
                await _idempotency_update(
                    idem,
                    status=str(cached.get("status") or "completed"),
                    sent=bool((existing or {}).get("sent")),
                    conversation_url=str(cached.get("conversation_url") or ""),
                    result=cached,
                )
            except Exception:
                pass
        event = {
            "tool": "chatgpt_web_ask",
            "status": cached.get("status"),
            "conversation_url": cached.get("conversation_url"),
            "elapsed_seconds": 0.0,
            "run_id": cached.get("run_id") or run_id,
            "idempotency_key": idem.key,
            "idempotency_namespace": idem.namespace,
            "replayed": True,
            "answer_chars": int(cached.get("answer_chars") or len((cached.get("answer") or "").strip())),
        }
        _maybe_append_call_log(event)
        return cached

    job_key = (idem.namespace, tool_name, idem.key)
    existing_sent = bool((existing or {}).get("sent"))
    resume_url = str((existing or {}).get("conversation_url") or "").strip()
    if existing_sent and not resume_url:
        resume_url = str(conversation_url or "").strip()

    kind = "send"
    if existing_sent and resume_url:
        kind = "resume_wait"

        async def _factory() -> dict[str, Any]:
            runner = _ASK_RESUME_JOB_RUNNER or _default_ask_resume_job_runner
            return await runner(
                conversation_url=resume_url,
                timeout_seconds=timeout_seconds,
                deep_research_requested=bool(deep_research),
                idempotency=idem,
                existing_record=existing,
                run_id=run_id,
                ctx=ctx,
            )
    else:
        async def _factory() -> dict[str, Any]:
            runner = _ASK_SEND_JOB_RUNNER or _default_ask_send_job_runner
            return await runner(
                question=question,
                conversation_url=conversation_url,
                timeout_seconds=timeout_seconds,
                model=model,
                thinking_time=thinking_time,
                deep_research=deep_research,
                web_search=web_search,
                agent_mode=agent_mode,
                github_repo=github_repo,
                upload_paths=upload_paths,
                uploaded_files=file_fingerprints,
                idempotency=idem,
                run_id=run_id,
                fire_and_forget=fire_and_forget,
                ctx=ctx,
            )

    if existing_sent and not resume_url:
        running = await asyncio.shield(_get_running_job(job_key))
        if running is None:
            msg = (
                "idempotency record is marked sent=true but conversation_url is missing; "
                "cannot resume safely. Use chatgpt_web_idempotency_get(include_result=true) "
                "or retry with a new idempotency_key."
            )
            result = {
                "ok": False,
                "status": "error",
                "answer": "",
                "conversation_url": "",
                "elapsed_seconds": round(time.time() - started_at, 3),
                "run_id": run_id,
                "idempotency_key": idem.key,
                "idempotency_namespace": idem.namespace,
                "replayed": True,
                "sent": True,
                "error_type": "RuntimeError",
                "error": msg,
                "uploaded_files": file_fingerprints,
            }
            _maybe_append_call_log(
                {
                    "tool": "chatgpt_web_ask",
                    "status": "error",
                    "elapsed_seconds": result.get("elapsed_seconds"),
                    "run_id": run_id,
                    "idempotency_key": idem.key,
                    "idempotency_namespace": idem.namespace,
                    "replayed": True,
                    "sent": True,
                    "error_type": "RuntimeError",
                    "error": msg,
                }
            )
            return result

    job = await asyncio.shield(_get_or_start_job(job_key, kind=kind, factory=_factory))
    try:
        result = await asyncio.shield(job.task)
    except Exception as exc:
        try:
            await _idempotency_update(idem, status="error", error=f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
        blocked_state = await _chatgpt_read_blocked_state()
        status = _blocked_status_from_state(blocked_state) if _retry_after_seconds_from_blocked_state(blocked_state) else "error"
        result = {
            "ok": False,
            "status": status,
            "answer": "",
            "conversation_url": str(conversation_url or "").strip(),
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": type(exc).__name__,
            "error": _coerce_error_text(exc),
            "blocked_state": blocked_state,
            "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
            "uploaded_files": file_fingerprints,
        }

    result.setdefault("idempotency_key", idem.key)
    result.setdefault("idempotency_namespace", idem.namespace)
    if "sent" not in result:
        status = str(result.get("status") or "").strip().lower()
        if status in {"completed", "in_progress", "needs_followup"}:
            result["sent"] = True
        else:
            result["sent"] = bool(existing_sent or _chatgpt_prompt_sent_from_debug_timeline(result.get("debug_timeline")))
    result["replayed"] = bool(replayed)
    result = _chatgpt_maybe_offload_answer_result(
        result,
        tool=tool_name,
        run_id=str(result.get("run_id") or run_id),
    )

    event: dict[str, Any] = {
        "tool": "chatgpt_web_ask",
        "status": result.get("status"),
        "conversation_url": result.get("conversation_url"),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "run_id": result.get("run_id") or run_id,
        "idempotency_key": idem.key,
        "idempotency_namespace": idem.namespace,
        "replayed": bool(replayed),
        "job_kind": kind,
        "params": {
            "timeout_seconds": timeout_seconds,
            "model": model,
            "thinking_time": thinking_time,
            "deep_research": deep_research,
            "web_search": web_search,
            "agent_mode": agent_mode,
            "github_repo": github_repo,
            "files_count": len(upload_paths),
            "conversation_url": conversation_url,
        },
    }
    if _call_log_include_prompts():
        event["question"] = question
    if _call_log_include_answers():
        event["answer"] = result.get("answer")
    else:
        event["answer_chars"] = int(result.get("answer_chars") or len((result.get("answer") or "").strip()))
    debug_artifacts = result.get("debug_artifacts")
    if isinstance(debug_artifacts, dict) and debug_artifacts:
        event["debug_artifacts"] = debug_artifacts
    if isinstance(result.get("error_type"), str) and str(result.get("error_type") or "").strip():
        event["error_type"] = str(result.get("error_type"))
    if isinstance(result.get("error"), str) and str(result.get("error") or "").strip():
        event["error"] = str(result.get("error"))
    _maybe_append_call_log(event)
    return result


async def _ask_locked(
    *,
    question: str,
    conversation_url: str | None,
    timeout_seconds: int,
    model: str | None,
    thinking_time: str | None,
    deep_research: bool,
    web_search: bool,
    agent_mode: bool,
    github_repo: str | None,
    upload_paths: list[Path],
    uploaded_files: list[dict[str, Any]],
    idempotency: _IdempotencyContext | None,
    run_id: str,
    fire_and_forget: bool = False,
    ctx: Context | None,
) -> dict[str, Any]:
    cfg = _load_config()
    started_at = time.time()
    debug_timeline: list[dict[str, Any]] = []

    def _mark(phase: str) -> None:
        debug_timeline.append({"phase": str(phase), "t": round(time.time() - started_at, 3)})

    _mark("start")
    try:
        await _chatgpt_enforce_not_blocked(ctx=ctx, action="send")
    except Exception as exc:
        blocked_state = await _chatgpt_read_blocked_state()
        status = _blocked_status_from_state(blocked_state)
        result = {
            "ok": False,
            "status": status,
            "answer": "",
            "conversation_url": (str(conversation_url or "").strip() if conversation_url else ""),
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": type(exc).__name__,
            "error": _coerce_error_text(exc),
            "blocked_state": blocked_state,
            "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
            "debug_timeline": debug_timeline,
            "uploaded_files": uploaded_files,
        }
        if idempotency is not None:
            try:
                await _idempotency_update(
                    idempotency,
                    status=str(status or "error"),
                    sent=False,
                    conversation_url=str(result.get("conversation_url") or ""),
                    result=result,
                    error=f"{type(exc).__name__}: {exc}",
                )
            except Exception:
                pass
        return result

    enabled_modes = sum(1 for x in (deep_research, web_search, agent_mode) if x)
    if enabled_modes > 1:
        msg = "Choose at most one of: deep_research, web_search, agent_mode."
        result = {
            "ok": False,
            "status": "error",
            "answer": "",
            "conversation_url": (str(conversation_url or "").strip() if conversation_url else ""),
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": "ValueError",
            "error": msg,
            "uploaded_files": uploaded_files,
        }
        if idempotency is not None:
            try:
                await _idempotency_update(
                    idempotency,
                    status="error",
                    conversation_url=str(result.get("conversation_url") or ""),
                    result=result,
                    error=f"ValueError: {msg}",
                )
            except Exception:
                pass
        return result

    if cfg.cdp_url is None and not cfg.storage_state_path.exists():
        msg = (
            f"Missing storage_state.json at {cfg.storage_state_path}. "
            "Run ops/chatgpt_bootstrap_login.py to create it, or set CHATGPT_CDP_URL to use a running Chrome."
        )
        result = {
            "ok": False,
            "status": "error",
            "answer": "",
            "conversation_url": (str(conversation_url or "").strip() if conversation_url else ""),
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": "RuntimeError",
            "error": msg,
            "uploaded_files": uploaded_files,
        }
        if idempotency is not None:
            try:
                await _idempotency_update(
                    idempotency,
                    status="error",
                    conversation_url=str(result.get("conversation_url") or ""),
                    result=result,
                    error=f"RuntimeError: {msg}",
                )
            except Exception:
                pass
        return result

    env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
    with env_ctx:
        async with _page_slot(kind="chatgpt", ctx=ctx), async_playwright() as p:
            browser = None
            context = None
            page = None
            close_context = False
            # Defaults used by the exception handler below. These must be
            # initialized before any awaited calls that might raise.
            sent_prompt = False
            deep_research_requested = bool(deep_research)
            deep_research_active = bool(deep_research)
            conversation_url_effective = (str(conversation_url or "").strip() if conversation_url else "")
            model_text_effective = ""
            thinking_time_effective: str | None = None
            try:
                browser, context, page, close_context = await _open_chatgpt_page(
                    p, cfg, conversation_url=conversation_url, ctx=ctx
                )
                tool = (idempotency.tool if idempotency is not None else "chatgpt_web_ask")
                await _chatgpt_install_netlog(page, tool=tool, run_id=run_id, ctx=ctx)
                _mark("open_page")

                # Track whether we have already sent a prompt; on failures after send,
                # return a resumable `status=in_progress` state rather than raising.
                sent_prompt = False
                deep_research_requested = bool(deep_research)
                deep_research_active = bool(deep_research)
                conversation_url_effective = (page.url or "").strip()
                model_text_effective = ""
                thinking_time_effective: str | None = None

                # Ensure the composer is ready before we try to click pills/menus.
                await _find_prompt_box(page)
                await _wait_for_message_list_to_settle(page)
                _mark("composer_ready")

                # When the caller doesn't pin a specific conversation, prefer starting a fresh chat.
                # This avoids stale composer modes (e.g. "Create image") leaking across unrelated jobs.
                if not conversation_url:
                    try:
                        if re.search(r"^https?://(?:chatgpt\\.com|chat\\.openai\\.com)/c/", page.url or "", re.I):
                            await _ctx_info(ctx, "No conversation_url provided; switching to a fresh chat…")
                            clicked = await _chatgpt_click_new_chat(page)
                            if clicked:
                                await _find_prompt_box(page, timeout_ms=30_000)
                                await _wait_for_message_list_to_settle(page)
                                conversation_url_effective = (page.url or "").strip()
                                _mark("new_chat")
                    except Exception as exc:
                        await _ctx_info(ctx, f"New chat switch failed (best-effort): {type(exc).__name__}: {exc}")

                # Default: when using Pro, prefer Extended thinking time unless caller overrides.
                # This is best-effort because some modes (e.g. Research) may hide the thinking-time UI.
                implicit_thinking_time = False
                if model and not (thinking_time or "").strip():
                    try:
                        # Best-effort default only for callers explicitly asking for "Pro".
                        # In current ChatGPT Web UI, "Pro" is often a label while the selector exposes "Thinking".
                        if re.search(r"\bpro\b", str(model or ""), re.I):
                            thinking_time = _chatgpt_pro_default_thinking_time()
                            implicit_thinking_time = True
                    except Exception:
                        implicit_thinking_time = False

                async def _configure_requested_composer_state(*, after_uploads: bool) -> None:
                    await _human_pause(page)
                    if model:
                        await _ensure_model(page, model=model, ctx=ctx)
                    if thinking_time:
                        try:
                            await _ensure_thinking_time(page, thinking_time=thinking_time, ctx=ctx)
                        except Exception as exc:
                            if not implicit_thinking_time:
                                raise
                            await _ctx_info(ctx, f"Thinking time not applied (best-effort): {exc}")
                    if agent_mode:
                        await _ensure_agent_mode(page, ctx=ctx)
                    elif deep_research and (after_uploads or not upload_paths):
                        # Deep Research conversations can reset the composer after uploads;
                        # enable Deep Research after uploading when attachments are present.
                        await _ensure_deep_research(page, ctx=ctx)
                    elif web_search:
                        await _ensure_web_search(page, ctx=ctx)
                    if github_repo:
                        await _ensure_github_connector(page, ctx=ctx)
                        await _select_github_repo(page, repo=github_repo, ctx=ctx)

                await _configure_requested_composer_state(after_uploads=False)

                await _wait_for_message_list_to_settle(page)
                _mark("ui_configured")

                async def _recover_upload_surface(*, reason: str, phase: str) -> bool:
                    nonlocal browser, context, page, close_context, conversation_url_effective
                    try:
                        await _chatgpt_refresh_page(
                            page,
                            ctx=ctx,
                            reason=reason,
                            phase=phase,
                            preferred_url=conversation_url_effective or conversation_url,
                        )
                        _mark("upload_recover_refresh")
                        await _find_prompt_box(page, timeout_ms=30_000)
                        await _wait_for_message_list_to_settle(page)
                        await _configure_requested_composer_state(after_uploads=False)
                        await _wait_for_message_list_to_settle(page)
                        return True
                    except Exception as refresh_exc:
                        await _ctx_info(
                            ctx,
                            "Upload refresh recovery failed; reopening page: "
                            f"{type(refresh_exc).__name__}: {refresh_exc}",
                        )

                    old_page = page
                    old_context = context
                    old_browser = browser
                    old_close_context = close_context
                    try:
                        browser, context, page, close_context = await _open_chatgpt_page(
                            p,
                            cfg,
                            conversation_url=conversation_url_effective or conversation_url,
                            ctx=ctx,
                        )
                        tool = (idempotency.tool if idempotency is not None else "chatgpt_web_ask")
                        await _chatgpt_install_netlog(page, tool=tool, run_id=run_id, ctx=ctx)
                        await _find_prompt_box(page, timeout_ms=30_000)
                        await _wait_for_message_list_to_settle(page)
                        await _configure_requested_composer_state(after_uploads=False)
                        await _wait_for_message_list_to_settle(page)
                        conversation_url_effective = (page.url or "").strip() or conversation_url_effective
                        _mark("upload_recover_reopen")
                        return True
                    except Exception as reopen_exc:
                        await _ctx_info(
                            ctx,
                            "Upload reopen recovery failed: "
                            f"{type(reopen_exc).__name__}: {reopen_exc}",
                        )
                        return False
                    finally:
                        try:
                            if old_page is not None:
                                try:
                                    await old_page.close()
                                except Exception:
                                    pass
                            if old_close_context and old_context is not None:
                                try:
                                    await old_context.close()
                                except Exception:
                                    pass
                        finally:
                            if old_browser is not None:
                                try:
                                    await old_browser.close()
                                except Exception:
                                    pass

                if upload_paths:
                    await _ctx_info(ctx, f"Uploading {len(upload_paths)} file(s)…")
                    upload_recovery_attempts = max(1, _env_int("CHATGPT_UPLOAD_RECOVERY_ATTEMPTS", 2))
                    stage_attempt = 1
                    while True:
                        try:
                            for up in upload_paths:
                                confirmed = False
                                for attempt in range(1, upload_recovery_attempts + 1):
                                    try:
                                        confirmed = await _upload_file_via_menu(page, file_path=up, ctx=ctx)
                                        break
                                    except Exception as exc:
                                        if attempt >= upload_recovery_attempts or not _looks_like_upload_page_closed_error(exc):
                                            raise
                                        await _ctx_info(
                                            ctx,
                                            "Upload transient failure; trying recovery "
                                            f"({attempt}/{upload_recovery_attempts}): {type(exc).__name__}: {exc}",
                                        )
                                        recovered = await _recover_upload_surface(
                                            reason=f"upload failed for {up.name}: {type(exc).__name__}: {exc}",
                                            phase="ask_upload_retry",
                                        )
                                        if not recovered:
                                            raise
                                if confirmed:
                                    await _ctx_info(ctx, f"Uploaded file: {up.name}")
                                else:
                                    await _ctx_info(ctx, f"Upload attempted (unconfirmed): {up.name}")
                            break
                        except Exception as exc:
                            if stage_attempt >= upload_recovery_attempts or not _looks_like_upload_page_closed_error(exc):
                                raise
                            stage_attempt += 1
                            await _ctx_info(
                                ctx,
                                "Upload stage transient failure; retrying all files "
                                f"({stage_attempt}/{upload_recovery_attempts}): {type(exc).__name__}: {exc}",
                            )
                            recovered = await _recover_upload_surface(
                                reason=f"upload stage retry: {type(exc).__name__}: {exc}",
                                phase="ask_upload_stage_retry",
                            )
                            if not recovered:
                                raise
                    await _wait_for_message_list_to_settle(page)
                    _mark("uploads_done")

                    # Uploading files can reset the model/mode/thinking-time UI; re-apply requested settings.
                    await _configure_requested_composer_state(after_uploads=True)
                    await _wait_for_message_list_to_settle(page)
                    _mark("ui_configured_after_upload")

                # Snapshot effective UI settings (best-effort; for debugging / audit).
                model_text_effective = await _current_model_text(page)
                try:
                    thinking_time_effective = await _current_thinking_time_key(page)
                except Exception:
                    thinking_time_effective = None

                # Detect whether the conversation is currently in Research/Deep Research mode.
                # Some callers reply inside a Research conversation without setting `deep_research=true`;
                # in that case we still want to classify the returned status correctly (but avoid blocking
                # for the full report unless `deep_research` was explicitly requested).
                deep_research_active = deep_research_requested
                try:
                    research = (
                        _composer_pills(page)
                        .filter(has_text=_DEEP_RESEARCH_PILL_RE)
                        .first
                    )
                    if await research.count() and await research.is_visible():
                        deep_research_active = True
                except Exception:
                    deep_research_active = deep_research_requested

                start_user_count = await page.locator(_CHATGPT_USER_SELECTOR).count()
                baseline_last_assistant = await _last_assistant_text(page)
                start_assistant_count = await page.locator(_CHATGPT_ASSISTANT_SELECTOR).count()
                sent_prompt = False
                refreshed_once = False
                conversation_url_effective = (page.url or "").strip()

                duplicate_prompt_guard: dict[str, Any] | None = None
                skip_send = False
                if (
                    conversation_url
                    and _truthy_env("CHATGPT_DUPLICATE_PROMPT_GUARD", True)
                    and not upload_paths
                ):
                    try:
                        user = page.locator(_CHATGPT_USER_SELECTOR)
                        last_user_text = ""
                        if start_user_count > 0:
                            last_user_text = _normalize_ws(
                                (await user.nth(int(start_user_count) - 1).inner_text(timeout=2_000)).strip()
                            )
                        if _is_duplicate_user_prompt(question=question, last_user_text=last_user_text):
                            skip_send = True
                            sent_prompt = True  # treat as "already sent" for error handling
                            duplicate_prompt_guard = {
                                "skipped_send": True,
                                "question_sig": _normalize_ws(question)[:160],
                                "last_user_sig": last_user_text[:160],
                            }
                            _mark("duplicate_prompt_guard_skip_send")
                            await _ctx_info(ctx, "Duplicate prompt detected; skipping send and resuming wait…")
                            if idempotency is not None:
                                try:
                                    await _idempotency_update(
                                        idempotency,
                                        sent=True,
                                        conversation_url=conversation_url_effective or page.url,
                                    )
                                except Exception:
                                    pass
                    except Exception:
                        skip_send = False

                if not skip_send:
                    prompt = await _find_prompt_box(page)
                    await prompt.click()
                    await _human_pause(page)
                    try:
                        await _type_question(prompt, question)
                    except PlaywrightTimeoutError:
                        # The composer can re-render after toggling model/modes; re-acquire once and retry.
                        prompt = await _find_prompt_box(page, timeout_ms=30_000)
                        await prompt.click()
                        await _human_pause(page)
                        await _type_question(prompt, question)
                    await _human_pause(page)
                    _mark("typed")

                    # Prefer clicking send if available; fall back to Enter.
                    send_btn = page.locator(_CHATGPT_SEND_BUTTON_SELECTOR).first
                    send_wait_ms = 90_000 if upload_paths else 30_000
                    await _wait_for_send_button_enabled(send_btn, timeout_ms=send_wait_ms)
                    await _chatgpt_send_prompt(page=page, prompt_box=prompt, send_btn=send_btn, ctx=ctx)
                    _mark("sent")
                    try:
                        conversation_url_effective = await _chatgpt_wait_for_conversation_url(page, timeout_seconds=2.0)
                    except Exception:
                        conversation_url_effective = (conversation_url_effective or (page.url or "")).strip()

                    user_message_confirmed = False
                    try:
                        await _wait_for_user_message(page, question=question, start_user_count=start_user_count)
                        user_message_confirmed = True
                    except Exception as exc:
                        # If the composer cleared (or generation started), treat this as sent even if we can't
                        # confirm the user message DOM update in time.
                        stop_btn = page.locator(_CHATGPT_STOP_BUTTON_SELECTOR).first
                        stop_visible = False
                        try:
                            if await stop_btn.count():
                                stop_visible = await stop_btn.is_visible()
                        except Exception:
                            stop_visible = False

                        current_text = await _prompt_box_text(prompt)
                        if (current_text is not None and not current_text.strip()) or stop_visible:
                            user_message_confirmed = True
                        else:
                            # Retry once: uploads can keep the send button disabled briefly.
                            try:
                                await _wait_for_send_button_enabled(send_btn, timeout_ms=send_wait_ms)
                            except Exception:
                                pass
                            await _chatgpt_send_prompt(page=page, prompt_box=prompt, send_btn=send_btn, ctx=ctx)
                            try:
                                await _wait_for_user_message(
                                    page,
                                    question=question,
                                    start_user_count=start_user_count,
                                    timeout_ms=20_000,
                                )
                                user_message_confirmed = True
                            except Exception:
                                current_text = await _prompt_box_text(prompt)
                                stop_visible = False
                                try:
                                    if await stop_btn.count():
                                        stop_visible = await stop_btn.is_visible()
                                except Exception:
                                    stop_visible = False
                                if (current_text is not None and not current_text.strip()) or stop_visible:
                                    user_message_confirmed = True
                                else:
                                    raise exc

                    # Confirmed: the user message is visible (or at least count increased).
                    if not user_message_confirmed:
                        raise TimeoutError("Failed to confirm prompt was sent.")
                    _mark("user_message_confirmed")
                    sent_prompt = True
                    if idempotency is not None:
                        try:
                            await _idempotency_update(
                                idempotency,
                                sent=True,
                                conversation_url=conversation_url_effective or page.url,
                            )
                        except Exception:
                            pass

                conv_wait_s = 20.0 if upload_paths else 6.0
                conversation_url_effective = await _chatgpt_wait_for_conversation_url(page, timeout_seconds=conv_wait_s)
                _mark("conversation_url_ready")
                if idempotency is not None:
                    try:
                        await _idempotency_update(
                            idempotency,
                            conversation_url=conversation_url_effective or page.url,
                        )
                    except Exception:
                        pass
                if conversation_url_effective and "/c/" in conversation_url_effective:
                    await _ctx_info(ctx, f"Conversation URL: {conversation_url_effective}")

                # Phase 2: Fire-and-forget mode — return immediately after prompt is
                # confirmed sent, without waiting for the model's answer.  The wait
                # worker will pick up this job via conversation_url.
                if fire_and_forget and sent_prompt:
                    _mark("fire_and_forget_return")
                    partial = ""
                    try:
                        partial = await _last_assistant_text(page)
                    except Exception:
                        pass
                    result = {
                        "ok": True,
                        "answer": partial,
                        "answer_format": "text",
                        "status": "in_progress",
                        "conversation_url": conversation_url_effective or page.url,
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "model_text": model_text_effective,
                        "thinking_time": thinking_time_effective,
                        "thinking_time_requested": (thinking_time or None),
                        "debug_timeline": debug_timeline,
                        "uploaded_files": uploaded_files,
                        "fire_and_forget": True,
                    }
                    if duplicate_prompt_guard is not None:
                        result["duplicate_prompt_guard"] = duplicate_prompt_guard
                    if idempotency is not None:
                        try:
                            await _idempotency_update(
                                idempotency,
                                status="in_progress",
                                sent=True,
                                conversation_url=str(result.get("conversation_url") or ""),
                                result=result,
                            )
                        except Exception:
                            pass
                    return result

                await _ctx_info(ctx, "Waiting for answer…")
                _mark("wait_for_answer")

                answer = ""
                wait_observations: dict[str, Any] = {}
                try:
                    answer = await _wait_for_answer(
                        page,
                        started_at=started_at,
                        start_assistant_count=start_assistant_count,
                        timeout_seconds=timeout_seconds,
                        require_new=True,
                        baseline_last_text=baseline_last_assistant,
                        ctx=ctx,
                        observations=wait_observations,
                    )
                except TimeoutError as exc:
                    # Recovery attempt: occasionally ChatGPT accepts the prompt but the UI doesn't
                    # render the assistant message until a refresh. Try a single refresh and
                    # re-check briefly before returning `status=in_progress`.
                    if not refreshed_once:
                        refreshed_once = True
                        try:
                            await _chatgpt_refresh_page(
                                page,
                                ctx=ctx,
                                reason=f"timeout waiting for answer start: {exc}",
                                phase="ask_timeout_wait_start",
                                preferred_url=conversation_url_effective or conversation_url,
                            )
                            await _wait_for_message_list_to_settle(page)
                            assistant_count = await page.locator(_CHATGPT_ASSISTANT_SELECTOR).count()
                            answer = await _wait_for_answer(
                                page,
                                started_at=started_at,
                                start_assistant_count=max(0, assistant_count - 1),
                                timeout_seconds=min(timeout_seconds, 90),
                                min_chars=0,
                                require_new=False,
                                ctx=ctx,
                            )
                        except Exception:
                            answer = ""

                    if answer:
                        # Proceed with normal completion classification below.
                        pass
                    else:
                        _mark("timeout_waiting_for_answer")
                        # Some modes (e.g. long Pro/agent runs) may not emit an assistant message promptly.
                        # Return a resumable state so callers can poll via chatgpt_web.wait(conversation_url).
                        artifacts = await _capture_debug_artifacts(page, label="ask_timeout")
                        if ctx and artifacts:
                            await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")
                        try:
                            conversation_url_effective = await _chatgpt_wait_for_conversation_url(page, timeout_seconds=3.0)
                        except Exception:
                            pass
                        partial = await _last_assistant_text(page)
                        partial_format = "text"
                        try:
                            raw = await _chatgpt_best_effort_last_assistant_raw_markdown(page, question=question)
                            if raw and (
                                len(raw.strip()) > len(partial.strip())
                                or ("\n\n" in raw and "\n\n" not in partial)
                            ):
                                partial = raw
                                partial_format = "markdown"
                        except Exception:
                            pass
                        result = {
                            "ok": True,
                            "answer": partial,
                            "answer_format": partial_format,
                            "status": "in_progress" if not deep_research_active else _classify_deep_research_answer(partial),
                            "conversation_url": conversation_url_effective or page.url,
                            "elapsed_seconds": round(time.time() - started_at, 3),
                            "run_id": run_id,
                            "model_text": model_text_effective,
                            "thinking_time": thinking_time_effective,
                            "thinking_time_requested": (thinking_time or None),
                            "debug_artifacts": artifacts,
                            "debug_timeline": debug_timeline,
                            "uploaded_files": uploaded_files,
                        }
                        if duplicate_prompt_guard is not None:
                            result["duplicate_prompt_guard"] = duplicate_prompt_guard
                        if idempotency is not None:
                            try:
                                await _idempotency_update(
                                    idempotency,
                                    status=str(result.get("status") or "in_progress"),
                                    conversation_url=str(result.get("conversation_url") or ""),
                                    result=result,
                                )
                            except Exception:
                                pass
                        return result
                except Exception as exc:
                    if sent_prompt and (not refreshed_once) and _looks_like_transient_playwright_error(exc):
                        refreshed_once = True
                        await _chatgpt_refresh_page(
                            page,
                            ctx=ctx,
                            reason=f"{type(exc).__name__}: {exc}",
                            phase="ask_wait_answer",
                            preferred_url=conversation_url_effective or conversation_url,
                        )
                        await _wait_for_message_list_to_settle(page)
                        assistant_count = await page.locator(_CHATGPT_ASSISTANT_SELECTOR).count()
                        answer = await _wait_for_answer(
                            page,
                            started_at=started_at,
                            start_assistant_count=max(0, assistant_count - 1),
                            timeout_seconds=timeout_seconds,
                            min_chars=0,
                            require_new=False,
                            ctx=ctx,
                        )
                    else:
                        raise

                status = "completed"
                deep_research_auto_followup: dict[str, Any] | None = None
                if deep_research_active:
                    status = _classify_deep_research_answer(answer)
                    if deep_research_requested and status == "in_progress":
                        min_chars = _deep_research_report_min_chars()
                        assistant_count = await page.locator(_CHATGPT_ASSISTANT_SELECTOR).count()
                        answer = await _wait_for_answer(
                            page,
                            started_at=started_at,
                            start_assistant_count=max(0, assistant_count - 1),
                            timeout_seconds=timeout_seconds,
                            min_chars=min_chars,
                            require_new=False,
                            ctx=ctx,
                        )
                        status = _classify_deep_research_answer(answer)

                if (
                    deep_research_requested
                    and deep_research_active
                    and status == "needs_followup"
                    and _deep_research_auto_followup_enabled()
                ):
                    followup = _deep_research_auto_followup_prompt(answer)
                    deep_research_auto_followup = {"enabled": True, "followup_prompt": followup}
                    assistant_count_before = await page.locator(_CHATGPT_ASSISTANT_SELECTOR).count()
                    try:
                        await _ctx_info(ctx, "Deep Research asked for confirmation; auto-following up to proceed…")
                        await _chatgpt_send_followup_message(page, message=followup, ctx=ctx)
                        deep_research_auto_followup["sent"] = True
                    except Exception as exc:
                        deep_research_auto_followup["sent"] = False
                        deep_research_auto_followup["error"] = f"{type(exc).__name__}: {exc}"
                    else:
                        # We've responded to the follow-up prompt; treat this as resumable and let the
                        # wait/export phase collect the full report.
                        status = "in_progress"
                        try:
                            answer2 = await _wait_for_answer(
                                page,
                                started_at=time.time(),
                                start_assistant_count=assistant_count_before,
                                timeout_seconds=min(120, max(30, int(timeout_seconds))),
                                min_chars=0,
                                require_new=True,
                                baseline_last_text=answer,
                                ctx=ctx,
                            )
                        except Exception as exc:
                            deep_research_auto_followup["wait_error"] = f"{type(exc).__name__}: {exc}"
                        else:
                            if answer2:
                                answer = answer2
                                status = _classify_deep_research_answer(answer)
                                deep_research_auto_followup["post_status"] = status

                if _looks_like_transient_assistant_error(answer):
                    if not refreshed_once:
                        refreshed_once = True
                        await _chatgpt_refresh_page(
                            page,
                            ctx=ctx,
                            reason=f"transient assistant error: {answer}",
                            phase="ask_transient_assistant_error",
                            preferred_url=conversation_url_effective or conversation_url,
                        )
                        await _wait_for_message_list_to_settle(page)
                        assistant_count = await page.locator(_CHATGPT_ASSISTANT_SELECTOR).count()
                        answer2 = await _wait_for_answer(
                            page,
                            started_at=started_at,
                            start_assistant_count=max(0, assistant_count - 1),
                            timeout_seconds=min(timeout_seconds, 90),
                            min_chars=0,
                            require_new=False,
                            ctx=ctx,
                        )
                        if answer2 and not _looks_like_transient_assistant_error(answer2):
                            answer = answer2
                            if deep_research_active:
                                status = _classify_deep_research_answer(answer)

                    if _looks_like_transient_assistant_error(answer):
                        artifacts = await _capture_debug_artifacts(page, label="ask_transient_error")
                        await _chatgpt_set_blocked(
                            reason="network",
                            cooldown_seconds=_chatgpt_network_recovery_cooldown_seconds(),
                            artifacts=artifacts,
                        )
                        blocked_state = await _chatgpt_read_blocked_state()
                        result = {
                            "ok": False,
                            "answer": answer,
                            "answer_format": "text",
                            "status": "in_progress",
                            "conversation_url": conversation_url_effective or page.url,
                            "elapsed_seconds": round(time.time() - started_at, 3),
                            "run_id": run_id,
                            "model_text": model_text_effective,
                            "thinking_time": thinking_time_effective,
                            "thinking_time_requested": (thinking_time or None),
                            "debug_artifacts": artifacts,
                            "debug_timeline": debug_timeline,
                            "blocked_state": blocked_state,
                            "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
                            "uploaded_files": uploaded_files,
                        }
                        result = _chatgpt_maybe_offload_answer_result(
                            result,
                            tool="chatgpt_web_ask",
                            run_id=run_id,
                        )
                        if idempotency is not None:
                            try:
                                await _idempotency_update(
                                    idempotency,
                                    status=str(result.get("status") or "in_progress"),
                                    conversation_url=str(result.get("conversation_url") or ""),
                                    result=result,
                                )
                            except Exception:
                                pass
                        return result

                # Best-effort: return the raw Markdown payload (avoids losing `---/#/|` via rendered DOM).
                answer_format = "text"
                try:
                    raw = await _chatgpt_best_effort_last_assistant_raw_markdown(page, question=question)
                    if raw:
                        answer = raw
                        answer_format = "markdown"
                except Exception:
                    pass

                _mark("answer_ready")
                navigator_user_agent = ""
                navigator_platform = ""
                try:
                    navigator_user_agent = str(await page.evaluate("() => navigator.userAgent") or "").strip()
                except Exception:
                    navigator_user_agent = ""
                try:
                    navigator_platform = str(await page.evaluate("() => navigator.platform") or "").strip()
                except Exception:
                    navigator_platform = ""
                result = {
                    "ok": True,
                    "answer": answer,
                    "answer_format": answer_format,
                    "status": status,
                    "conversation_url": conversation_url_effective or page.url,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "model_text": model_text_effective,
                    "thinking_time": thinking_time_effective,
                    "thinking_time_requested": (thinking_time or None),
                    "debug_timeline": debug_timeline,
                    "uploaded_files": uploaded_files,
                }
                if wait_observations:
                    result["wait_observations"] = wait_observations
                if navigator_user_agent:
                    result["navigator_user_agent"] = navigator_user_agent
                if navigator_platform:
                    result["navigator_platform"] = navigator_platform
                if duplicate_prompt_guard is not None:
                    result["duplicate_prompt_guard"] = duplicate_prompt_guard
                if deep_research_auto_followup is not None:
                    result["deep_research_auto_followup"] = deep_research_auto_followup
                try:
                    thinking_obs = await _chatgpt_best_effort_thinking_observation(page, ctx=ctx)
                    if thinking_obs:
                        result["thinking_observation"] = thinking_obs
                        if _truthy_env("CHATGPT_THOUGHT_GUARD_CAPTURE_DEBUG", False) and (
                            bool(thinking_obs.get("thought_too_short"))
                            or bool(thinking_obs.get("skipping"))
                            or bool(thinking_obs.get("answer_now_visible"))
                        ):
                            try:
                                result["thought_guard_debug_artifacts"] = await _capture_debug_artifacts(page, label="thought_guard")
                            except Exception:
                                pass
                    elif _truthy_env("CHATGPT_THOUGHT_GUARD_CAPTURE_DEBUG", False) and bool(thinking_time_effective or thinking_time):
                        try:
                            result["thought_guard_debug_artifacts"] = await _capture_debug_artifacts(page, label="thought_guard_missing")
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    thinking_trace = await _chatgpt_capture_thinking_trace(page, ctx=ctx)
                    if thinking_trace:
                        result["thinking_trace"] = thinking_trace
                except Exception:
                    pass
                try:
                    dom_risk = await _chatgpt_best_effort_dom_risk_observation(page, phase="ask_answer_ready", ctx=ctx)
                    if dom_risk:
                        result["dom_risk_observation"] = dom_risk
                except Exception:
                    pass
                result = _chatgpt_maybe_offload_answer_result(
                    result,
                    tool="chatgpt_web_ask",
                    run_id=run_id,
                )
                if idempotency is not None:
                    try:
                        await _idempotency_update(
                            idempotency,
                            status=str(result.get("status") or "completed"),
                            conversation_url=str(result.get("conversation_url") or ""),
                            result=result,
                        )
                    except Exception:
                        pass
                return result
            except Exception as exc:
                if _is_tab_limit_error(exc):
                    resume_url = (
                        str(conversation_url_effective or "").strip()
                        or (str(page.url or "").strip() if page is not None else "")
                        or (str(conversation_url or "").strip() if conversation_url else "")
                    )
                    result = _tab_limit_result(
                        tool="chatgpt_web_ask",
                        run_id=run_id,
                        started_at=started_at,
                        conversation_url=resume_url,
                        extra={
                            "model_text": model_text_effective,
                            "thinking_time": thinking_time_effective,
                            "thinking_time_requested": (thinking_time or None),
                            "debug_timeline": debug_timeline,
                            "uploaded_files": uploaded_files,
                        },
                    )
                    if idempotency is not None:
                        try:
                            await _idempotency_update(
                                idempotency,
                                status="cooldown",
                                sent=False,
                                conversation_url=resume_url,
                                result=result,
                                error="TabLimitReached",
                            )
                        except Exception:
                            pass
                    return result
                artifacts: dict[str, str] = {}
                if page is not None:
                    artifacts = await _capture_debug_artifacts(page, label="ask_error")
                    if ctx and artifacts:
                        await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")

                # If we already sent the prompt, avoid raising: return a resumable state so callers can
                # continue via chatgpt_web_wait(conversation_url, ...), without re-sending.
                if bool(sent_prompt):
                    partial = ""
                    if page is not None:
                        try:
                            partial = await _last_assistant_text(page)
                        except Exception:
                            partial = ""
                    resume_url = (
                        str(conversation_url_effective or "").strip()
                        or (str(page.url or "").strip() if page is not None else "")
                        or (str(conversation_url or "").strip() if conversation_url else "")
                    )
                    if page is not None and "/c/" not in (resume_url or ""):
                        try:
                            alt = await _best_effort_conversation_url(page)
                            if alt and "/c/" in alt:
                                resume_url = alt
                        except Exception:
                            pass
                    result = {
                        "ok": False,
                        "answer": partial,
                        "answer_format": "text",
                        "status": "in_progress",
                        "conversation_url": resume_url,
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "model_text": model_text_effective,
                        "thinking_time": thinking_time_effective,
                        "thinking_time_requested": (thinking_time or None),
                        "debug_artifacts": artifacts,
                        "debug_timeline": debug_timeline,
                        "error_type": type(exc).__name__,
                        "error": _coerce_error_text(exc),
                        "uploaded_files": uploaded_files,
                    }
                    result = _chatgpt_maybe_offload_answer_result(
                        result,
                        tool="chatgpt_web_ask",
                        run_id=run_id,
                    )
                    if idempotency is not None:
                        try:
                            await _idempotency_update(
                                idempotency,
                                status="in_progress",
                                sent=True,
                                conversation_url=resume_url,
                                result=result,
                                error=f"{type(exc).__name__}: {exc}",
                            )
                        except Exception:
                            pass
                    return result

                resume_url = (
                    str(conversation_url_effective or "").strip()
                    or (str(page.url or "").strip() if page is not None else "")
                    or (str(conversation_url or "").strip() if conversation_url else "")
                )
                blocked_state = await _chatgpt_read_blocked_state()
                retry_after = _retry_after_seconds_from_blocked_state(blocked_state)
                status = _blocked_status_from_state(blocked_state) if retry_after else "error"
                if not retry_after and _looks_like_transient_playwright_error(exc):
                    retry_after = float(_env_int("CHATGPT_UNSENT_TRANSIENT_RETRY_AFTER_SECONDS", 30)) + random.uniform(
                        0.0, 3.0
                    )
                    status = "cooldown"
                result = {
                    "ok": False,
                    "status": status,
                    "answer": "",
                    "conversation_url": resume_url,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "model_text": model_text_effective,
                    "thinking_time": thinking_time_effective,
                    "thinking_time_requested": (thinking_time or None),
                    "debug_artifacts": artifacts,
                    "debug_timeline": debug_timeline,
                    "error_type": type(exc).__name__,
                    "error": _coerce_error_text(exc),
                    "blocked_state": blocked_state,
                    "retry_after_seconds": retry_after,
                    "uploaded_files": uploaded_files,
                }
                if idempotency is not None:
                    try:
                        await _idempotency_update(
                            idempotency,
                            status=str(status or "error"),
                            sent=False,
                            conversation_url=resume_url,
                            result=result,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    except Exception:
                        pass
                return result
            finally:
                try:
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
                    if close_context and context is not None:
                        await context.close()
                finally:
                    if browser is not None:
                        await browser.close()


@mcp.tool(
    name="chatgpt_web_wait",
    description=(
        "Wait for the latest assistant message in a conversation WITHOUT sending a new prompt.\n"
        "Useful for long-running modes like Deep research."
    ),
    structured_output=True,
)
async def wait(
    conversation_url: str,
    timeout_seconds: int = 7200,
    min_chars: int = 0,
    ctx: Context | None = None,
) -> dict[str, Any]:
    cfg = _load_config()
    try:
        await _chatgpt_enforce_not_blocked(ctx=ctx, action="wait")
    except Exception as exc:
        started_at = time.time()
        blocked_state = await _chatgpt_read_blocked_state()
        status = _blocked_status_from_state(blocked_state)
        return {
            "ok": False,
            "status": status,
            "answer": "",
            "conversation_url": str(conversation_url or "").strip(),
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": _run_id(tool="chatgpt_web_wait"),
            "error_type": type(exc).__name__,
            "error": _coerce_error_text(exc),
            "blocked_state": blocked_state,
            "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
        }

    started_at = time.time()
    run_id = _run_id(tool="chatgpt_web_wait")
    env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
    with env_ctx:
        async with _page_slot(kind="chatgpt", ctx=ctx), async_playwright() as p:
            browser = None
            context = None
            page = None
            close_context = False
            try:
                browser, context, page, close_context = await _open_chatgpt_page(
                    p, cfg, conversation_url=conversation_url, ctx=ctx
                )
                await _chatgpt_install_netlog(page, tool="chatgpt_web_wait", run_id=run_id, ctx=ctx)

                refreshed_once = False
                refreshed_performed = False
                refresh_guard: dict[str, Any] | None = None
                conversation_url_effective = (page.url or "").strip()
                assistant_count = await page.locator(_CHATGPT_ASSISTANT_SELECTOR).count()
                result: dict[str, Any] | None = None
                try:
                    answer = await _wait_for_answer(
                        page,
                        started_at=started_at,
                        start_assistant_count=max(0, assistant_count - 1),
                        timeout_seconds=timeout_seconds,
                        min_chars=min_chars,
                        require_new=False,
                        ctx=ctx,
                    )
                except TimeoutError:
                    artifacts = await _capture_debug_artifacts(page, label="wait_timeout")
                    if ctx and artifacts:
                        await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")
                    partial_before = await _last_assistant_text(page)
                    partial = partial_before
                    answer_format = "text"
                    status = "in_progress"
                    deep_research_widget_observation: dict[str, Any] | None = None
                    deep_research_widget_failure: str | None = None

                    # Sometimes the UI finishes thinking but doesn't render the final assistant
                    # message until a refresh. Try one refresh (no prompt send) as a best-effort
                    # recovery before returning `in_progress`.
                    if not refreshed_once:
                        refreshed_once = True
                        try:
                            conversation_id = _chatgpt_conversation_id_from_url(conversation_url_effective) or _chatgpt_conversation_id_from_url(conversation_url)
                            refresh_guard = await _chatgpt_wait_refresh_reserve(
                                conversation_id=conversation_id,
                                reason="wait timeout",
                                phase="wait_timeout",
                            )
                            if bool(refresh_guard.get("allowed")):
                                await _chatgpt_refresh_page(
                                    page,
                                    ctx=ctx,
                                    reason="wait timeout",
                                    phase="wait_timeout",
                                    preferred_url=conversation_url_effective or conversation_url,
                                )
                                refreshed_performed = True
                                await _wait_for_message_list_to_settle(page)
                                conversation_url_effective = (page.url or "").strip() or conversation_url_effective
                                partial_after = await _last_assistant_text(page)
                                if len(partial_after.strip()) > len(partial_before.strip()):
                                    partial = partial_after
                        except Exception:
                            pass

                    # Prefer raw Markdown when available (avoids rendered-DOM losses for tables/code).
                    try:
                        raw = await _chatgpt_best_effort_last_assistant_raw_markdown(page)
                        if raw and (
                            len(raw.strip()) > len(partial.strip())
                            or ("\n\n" in raw and "\n\n" not in partial)
                        ):
                            partial = raw
                            answer_format = "markdown"
                    except Exception:
                        pass

                    # Deep Research can render its final report inside an embedded app (iframes), leaving the
                    # normal assistant turn text empty or a short JSON stub. Best-effort extract from the widget.
                    try:
                        widget = await _chatgpt_best_effort_deep_research_widget_text(page, ctx=ctx)
                        if widget is not None:
                            widget_text, widget_meta = widget
                            widget_text = (widget_text or "").strip()
                            deep_research_widget_observation = widget_meta
                            deep_research_widget_failure = _deep_research_widget_failure_reason(widget_text)
                            if _should_prefer_deep_research_widget(widget_text, partial):
                                partial = widget_text
                                answer_format = "markdown"
                    except Exception:
                        pass

                    # If the timeout recovery refresh triggered a blocked/cooldown state (e.g. unusual activity
                    # / verification), fail-closed: return the blocked status instead of an in-progress partial.
                    try:
                        blocked_state = await _chatgpt_read_blocked_state()
                        retry_after = _retry_after_seconds_from_blocked_state(blocked_state)
                        if retry_after:
                            status = _blocked_status_from_state(blocked_state)
                            result = {
                                "ok": False,
                                "status": status,
                                "answer": partial,
                                "answer_format": answer_format,
                                "conversation_url": conversation_url_effective or page.url,
                                "elapsed_seconds": round(time.time() - started_at, 3),
                                "run_id": run_id,
                                "debug_artifacts": artifacts,
                                "refreshed_after_timeout": bool(refreshed_performed),
                                "blocked_state": blocked_state,
                                "retry_after_seconds": retry_after,
                                "error_type": "Blocked",
                                "error": "blocked during wait timeout recovery",
                            }
                            if refresh_guard is not None:
                                result["wait_refresh_guard"] = refresh_guard
                            if deep_research_widget_observation is not None:
                                result["deep_research_widget_observation"] = deep_research_widget_observation
                            event: dict[str, Any] = {
                                "tool": "chatgpt_web_wait",
                                "status": status,
                                "conversation_url": result.get("conversation_url"),
                                "elapsed_seconds": result.get("elapsed_seconds"),
                                "run_id": run_id,
                                "params": {
                                    "timeout_seconds": timeout_seconds,
                                    "min_chars": min_chars,
                                    "conversation_url": conversation_url,
                                },
                                "error_type": result.get("error_type"),
                                "error": result.get("error"),
                            }
                            if artifacts:
                                event["debug_artifacts"] = artifacts
                            _maybe_append_call_log(event)
                            return result
                    except Exception:
                        pass

                    if deep_research_widget_failure:
                        retry_after = float(max(10, _chatgpt_network_recovery_cooldown_seconds()))
                        status = "cooldown"
                        result = {
                            "ok": False,
                            "status": status,
                            "answer": partial,
                            "answer_format": answer_format,
                            "conversation_url": conversation_url_effective or page.url,
                            "elapsed_seconds": round(time.time() - started_at, 3),
                            "run_id": run_id,
                            "debug_artifacts": artifacts,
                            "refreshed_after_timeout": bool(refreshed_performed),
                            "retry_after_seconds": retry_after,
                            "error_type": "DeepResearchFailed",
                            "error": f"deep research widget reported failure: {deep_research_widget_failure}",
                        }
                        if refresh_guard is not None:
                            result["wait_refresh_guard"] = refresh_guard
                        if deep_research_widget_observation is not None:
                            result["deep_research_widget_observation"] = deep_research_widget_observation
                        event = {
                            "tool": "chatgpt_web_wait",
                            "status": status,
                            "conversation_url": result.get("conversation_url"),
                            "elapsed_seconds": result.get("elapsed_seconds"),
                            "run_id": run_id,
                            "params": {
                                "timeout_seconds": timeout_seconds,
                                "min_chars": min_chars,
                                "conversation_url": conversation_url,
                            },
                            "error_type": result.get("error_type"),
                            "error": result.get("error"),
                        }
                        if artifacts:
                            event["debug_artifacts"] = artifacts
                        _maybe_append_call_log(event)
                        return result

                    if partial.strip() and (min_chars <= 0 or len(partial.strip()) >= int(min_chars)):
                        status = _classify_deep_research_answer(partial)
                    result = {
                        "ok": True,
                        "answer": partial,
                        "answer_format": answer_format,
                        "status": status,
                        "conversation_url": conversation_url_effective or page.url,
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "debug_artifacts": artifacts,
                        "refreshed_after_timeout": bool(refreshed_performed),
                    }
                    if refresh_guard is not None:
                        result["wait_refresh_guard"] = refresh_guard
                    if deep_research_widget_observation is not None:
                        result["deep_research_widget_observation"] = deep_research_widget_observation
                except Exception as exc:
                    if (not refreshed_once) and _looks_like_transient_playwright_error(exc):
                        refreshed_once = True
                        conversation_id = _chatgpt_conversation_id_from_url(conversation_url_effective) or _chatgpt_conversation_id_from_url(conversation_url)
                        refresh_guard = await _chatgpt_wait_refresh_reserve(
                            conversation_id=conversation_id,
                            reason=f"{type(exc).__name__}: {exc}",
                            phase="wait_error",
                        )
                        if bool(refresh_guard.get("allowed")):
                            await _chatgpt_refresh_page(
                                page,
                                ctx=ctx,
                                reason=f"{type(exc).__name__}: {exc}",
                                phase="wait_error",
                                preferred_url=conversation_url_effective or conversation_url,
                            )
                            refreshed_performed = True
                            await _wait_for_message_list_to_settle(page)
                            assistant_count = await page.locator(_CHATGPT_ASSISTANT_SELECTOR).count()
                            answer = await _wait_for_answer(
                                page,
                                started_at=started_at,
                                start_assistant_count=max(0, assistant_count - 1),
                                timeout_seconds=timeout_seconds,
                                min_chars=min_chars,
                                require_new=False,
                                ctx=ctx,
                            )
                        else:
                            raise
                    else:
                        raise

                if result is None and _looks_like_transient_assistant_error(answer):
                    if not refreshed_once:
                        refreshed_once = True
                        conversation_id = _chatgpt_conversation_id_from_url(conversation_url_effective) or _chatgpt_conversation_id_from_url(conversation_url)
                        refresh_guard = await _chatgpt_wait_refresh_reserve(
                            conversation_id=conversation_id,
                            reason=f"transient assistant error: {answer}",
                            phase="wait_transient_assistant_error",
                        )
                        if bool(refresh_guard.get("allowed")):
                            await _chatgpt_refresh_page(
                                page,
                                ctx=ctx,
                                reason=f"transient assistant error: {answer}",
                                phase="wait_transient_assistant_error",
                                preferred_url=conversation_url_effective or conversation_url,
                            )
                            refreshed_performed = True
                            await _wait_for_message_list_to_settle(page)
                            assistant_count = await page.locator(_CHATGPT_ASSISTANT_SELECTOR).count()
                            answer2 = await _wait_for_answer(
                                page,
                                started_at=started_at,
                                start_assistant_count=max(0, assistant_count - 1),
                                timeout_seconds=min(timeout_seconds, 90),
                                min_chars=min_chars,
                                require_new=False,
                                ctx=ctx,
                            )
                            if answer2 and not _looks_like_transient_assistant_error(answer2):
                                answer = answer2

                    if _looks_like_transient_assistant_error(answer):
                        artifacts = await _capture_debug_artifacts(page, label="wait_transient_error")
                        await _chatgpt_set_blocked(
                            reason="network",
                            cooldown_seconds=_chatgpt_network_recovery_cooldown_seconds(),
                            artifacts=artifacts,
                        )
                        blocked_state = await _chatgpt_read_blocked_state()
                        result = {
                            "ok": False,
                            "answer": answer,
                            "status": "in_progress",
                            "conversation_url": conversation_url_effective or page.url,
                            "elapsed_seconds": round(time.time() - started_at, 3),
                            "run_id": run_id,
                            "debug_artifacts": artifacts,
                            "refreshed_after_timeout": bool(refreshed_performed),
                            "blocked_state": blocked_state,
                            "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
                        }
                        if refresh_guard is not None:
                            result["wait_refresh_guard"] = refresh_guard

                if result is None:
                    # Best-effort: return the raw Markdown payload (avoids losing `---/#/|` via rendered DOM).
                    answer_format = "text"
                    deep_research_widget_observation: dict[str, Any] | None = None
                    deep_research_widget_failure: str | None = None
                    try:
                        raw = await _chatgpt_best_effort_last_assistant_raw_markdown(page)
                        if raw:
                            answer = raw
                            answer_format = "markdown"
                    except Exception:
                        pass
                    try:
                        widget = await _chatgpt_best_effort_deep_research_widget_text(page, ctx=ctx)
                        if widget is not None:
                            widget_text, widget_meta = widget
                            widget_text = (widget_text or "").strip()
                            deep_research_widget_observation = widget_meta
                            deep_research_widget_failure = _deep_research_widget_failure_reason(widget_text)
                            if _should_prefer_deep_research_widget(widget_text, (answer or "")):
                                answer = widget_text
                                answer_format = "markdown"
                    except Exception:
                        pass
                    if deep_research_widget_failure:
                        artifacts = await _capture_debug_artifacts(page, label="deep_research_failed")
                        retry_after = float(max(10, _chatgpt_network_recovery_cooldown_seconds()))
                        result = {
                            "ok": False,
                            "answer": answer,
                            "answer_format": answer_format,
                            "status": "cooldown",
                            "conversation_url": conversation_url_effective or page.url,
                            "elapsed_seconds": round(time.time() - started_at, 3),
                            "run_id": run_id,
                            "debug_artifacts": artifacts,
                            "retry_after_seconds": retry_after,
                            "error_type": "DeepResearchFailed",
                            "error": f"deep research widget reported failure: {deep_research_widget_failure}",
                        }
                        if deep_research_widget_observation is not None:
                            result["deep_research_widget_observation"] = deep_research_widget_observation
                        event = {
                            "tool": "chatgpt_web_wait",
                            "status": result.get("status"),
                            "conversation_url": result.get("conversation_url"),
                            "elapsed_seconds": result.get("elapsed_seconds"),
                            "run_id": run_id,
                            "params": {
                                "timeout_seconds": timeout_seconds,
                                "min_chars": min_chars,
                                "conversation_url": conversation_url,
                            },
                            "error_type": result.get("error_type"),
                            "error": result.get("error"),
                        }
                        if artifacts:
                            event["debug_artifacts"] = artifacts
                        _maybe_append_call_log(event)
                        return result
                    result = {
                        "ok": True,
                        "answer": answer,
                        "answer_format": answer_format,
                        "status": _classify_deep_research_answer(answer),
                        "conversation_url": conversation_url_effective or page.url,
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                    }
                    if deep_research_widget_observation is not None:
                        result["deep_research_widget_observation"] = deep_research_widget_observation
                try:
                    thinking_obs = await _chatgpt_best_effort_thinking_observation(page, ctx=ctx)
                    if thinking_obs:
                        result["thinking_observation"] = thinking_obs
                        if _truthy_env("CHATGPT_THOUGHT_GUARD_CAPTURE_DEBUG", False) and (
                            bool(thinking_obs.get("thought_too_short"))
                            or bool(thinking_obs.get("skipping"))
                            or bool(thinking_obs.get("answer_now_visible"))
                        ):
                            try:
                                result["thought_guard_debug_artifacts"] = await _capture_debug_artifacts(page, label="thought_guard")
                            except Exception:
                                pass
                    elif _truthy_env("CHATGPT_THOUGHT_GUARD_CAPTURE_DEBUG", False):
                        try:
                            result["thought_guard_debug_artifacts"] = await _capture_debug_artifacts(page, label="thought_guard_missing")
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    thinking_trace = await _chatgpt_capture_thinking_trace(page, ctx=ctx)
                    if thinking_trace:
                        result["thinking_trace"] = thinking_trace
                except Exception:
                    pass
                # Best-effort: include the currently selected model label for observability.
                try:
                    model_text = await _current_model_text(page)
                    if model_text:
                        result["model_text"] = model_text
                except Exception:
                    pass
                try:
                    dom_risk = await _chatgpt_best_effort_dom_risk_observation(
                        page, phase=f"wait_{result.get('status') or 'unknown'}", ctx=ctx
                    )
                    if dom_risk:
                        result["dom_risk_observation"] = dom_risk
                except Exception:
                    pass
                result = _chatgpt_maybe_offload_answer_result(
                    result,
                    tool="chatgpt_web_wait",
                    run_id=run_id,
                )
                event: dict[str, Any] = {
                    "tool": "chatgpt_web_wait",
                    "status": result.get("status"),
                    "conversation_url": result.get("conversation_url"),
                    "elapsed_seconds": result.get("elapsed_seconds"),
                    "run_id": run_id,
                    "params": {
                        "timeout_seconds": timeout_seconds,
                        "min_chars": min_chars,
                        "conversation_url": conversation_url,
                    },
                }
                if _call_log_include_answers():
                    event["answer"] = result.get("answer")
                else:
                    event["answer_chars"] = int(result.get("answer_chars") or len((result.get("answer") or "").strip()))
                _maybe_append_call_log(event)
                return result
            except Exception as exc:
                if _is_tab_limit_error(exc):
                    result = _tab_limit_result(
                        tool="chatgpt_web_wait",
                        run_id=run_id,
                        started_at=started_at,
                        conversation_url=(conversation_url or ""),
                    )
                    event = {
                        "tool": "chatgpt_web_wait",
                        "status": result.get("status"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "conversation_url": conversation_url,
                        "run_id": run_id,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "min_chars": min_chars,
                            "conversation_url": conversation_url,
                        },
                        "error_type": result.get("error_type"),
                        "error": result.get("error"),
                    }
                    _maybe_append_call_log(event)
                    return result
                artifacts: dict[str, str] = {}
                if page is not None:
                    artifacts = await _capture_debug_artifacts(page, label="wait_error")
                    if ctx and artifacts:
                        await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")

                blocked_state = await _chatgpt_read_blocked_state()
                retry_after = _retry_after_seconds_from_blocked_state(blocked_state)
                transient_pw = _looks_like_transient_playwright_error(exc)
                if transient_pw and not retry_after:
                    # Most common cause: Chrome/target crashed or transient CDP/network issues. Treat as retryable and
                    # set a short global cooldown to avoid hammering ChatGPT while Chrome recovers.
                    try:
                        await _chatgpt_set_blocked(
                            reason="network",
                            cooldown_seconds=_chatgpt_network_recovery_cooldown_seconds(),
                            artifacts=artifacts,
                        )
                        blocked_state = await _chatgpt_read_blocked_state()
                        retry_after = _retry_after_seconds_from_blocked_state(blocked_state)
                    except Exception:
                        pass

                if retry_after:
                    status = _blocked_status_from_state(blocked_state)
                elif transient_pw:
                    status = "cooldown"
                    retry_after = float(max(10, _chatgpt_network_recovery_cooldown_seconds()))
                else:
                    status = "error"
                result = {
                    "ok": False,
                    "status": status,
                    "answer": "",
                    "conversation_url": (page.url if page is not None else conversation_url),
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "error_type": type(exc).__name__,
                    "error": _coerce_error_text(exc),
                    "debug_artifacts": artifacts,
                    "blocked_state": blocked_state,
                    "retry_after_seconds": retry_after,
                }
                event: dict[str, Any] = {
                    "tool": "chatgpt_web_wait",
                    "status": status,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "conversation_url": (page.url if page is not None else conversation_url),
                    "run_id": run_id,
                    "params": {
                        "timeout_seconds": timeout_seconds,
                        "min_chars": min_chars,
                        "conversation_url": conversation_url,
                    },
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                if artifacts:
                    event["debug_artifacts"] = artifacts
                _maybe_append_call_log(event)
                return result
            finally:
                try:
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
                    if close_context and context is not None:
                        await context.close()
                finally:
                    if browser is not None:
                        await browser.close()


@mcp.tool(
    name="chatgpt_web_refresh",
    description="Open ChatGPT and refresh the page (no prompt send).",
    structured_output=True,
)
async def chatgpt_web_refresh(
    conversation_url: str,
    timeout_seconds: int = 60,
    ctx: Context | None = None,
) -> dict[str, Any]:
    cfg = _load_config()
    try:
        await _chatgpt_enforce_not_blocked(ctx=ctx, action="refresh")
    except Exception as exc:
        started_at = time.time()
        blocked_state = await _chatgpt_read_blocked_state()
        status = _blocked_status_from_state(blocked_state)
        return {
            "ok": False,
            "status": status,
            "conversation_url": str(conversation_url or "").strip(),
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": _run_id(tool="chatgpt_web_refresh"),
            "error_type": type(exc).__name__,
            "error": _coerce_error_text(exc),
            "blocked_state": blocked_state,
            "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
        }

    started_at = time.time()
    run_id = _run_id(tool="chatgpt_web_refresh")
    env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
    with env_ctx:
        async with _page_slot(kind="chatgpt", ctx=ctx), async_playwright() as p:
            browser = None
            context = None
            page = None
            close_context = False
            try:
                browser, context, page, close_context = await _open_chatgpt_page(p, cfg, conversation_url=conversation_url, ctx=ctx)
                await _chatgpt_install_netlog(page, tool="chatgpt_web_refresh", run_id=run_id, ctx=ctx)
                await _find_prompt_box(page, timeout_ms=max(5_000, int(timeout_seconds * 1000)))
                await _chatgpt_refresh_page(
                    page,
                    ctx=ctx,
                    reason="explicit refresh",
                    phase="refresh",
                    preferred_url=conversation_url,
                )
                await _wait_for_message_list_to_settle(page)
                result: dict[str, Any] = {
                    "ok": True,
                    "status": "completed",
                    "conversation_url": (page.url if page is not None else str(conversation_url or "").strip()),
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                }
                try:
                    thinking_obs = await _chatgpt_best_effort_thinking_observation(page, ctx=ctx)
                    if thinking_obs:
                        result["thinking_observation"] = thinking_obs
                        if _truthy_env("CHATGPT_THOUGHT_GUARD_CAPTURE_DEBUG", False) and (
                            bool(thinking_obs.get("thought_too_short"))
                            or bool(thinking_obs.get("skipping"))
                            or bool(thinking_obs.get("answer_now_visible"))
                        ):
                            try:
                                result["thought_guard_debug_artifacts"] = await _capture_debug_artifacts(page, label="thought_guard")
                            except Exception:
                                pass
                except Exception:
                    pass
                try:
                    thinking_trace = await _chatgpt_capture_thinking_trace(page, ctx=ctx)
                    if thinking_trace:
                        result["thinking_trace"] = thinking_trace
                except Exception:
                    pass
                _maybe_append_call_log(
                    {
                        "tool": "chatgpt_web_refresh",
                        "ok": True,
                        "status": "completed",
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "params": {"timeout_seconds": timeout_seconds, "conversation_url": conversation_url},
                    }
                )
                return result
            except Exception as exc:
                artifacts: dict[str, str] = {}
                if page is not None:
                    try:
                        artifacts = await _capture_debug_artifacts(page, label="refresh_error")
                        if ctx and artifacts:
                            await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")
                    except Exception:
                        artifacts = {}
                blocked_state = await _chatgpt_read_blocked_state()
                status = _blocked_status_from_state(blocked_state) if _retry_after_seconds_from_blocked_state(blocked_state) else "error"
                return {
                    "ok": False,
                    "status": status,
                    "conversation_url": (str(conversation_url or "").strip() if conversation_url else ""),
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "error_type": type(exc).__name__,
                    "error": _coerce_error_text(exc),
                    "debug_artifacts": artifacts,
                    "blocked_state": blocked_state,
                    "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
                }
            finally:
                try:
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
                    if close_context and context is not None:
                        await context.close()
                finally:
                    if browser is not None:
                        await browser.close()


@mcp.tool(
    name="chatgpt_web_regenerate",
    description=(
        "Click the ChatGPT UI 'Regenerate/重新生成' control to re-generate the latest assistant response.\n"
        "Does NOT send a new user prompt.\n"
        "Guarded by CHATGPT_REGENERATE_STATE_FILE/CHATGPT_REGENERATE_MIN_INTERVAL_SECONDS to avoid storms."
    ),
    structured_output=True,
)
async def chatgpt_web_regenerate(
    conversation_url: str,
    timeout_seconds: int = 1800,
    min_chars: int = 0,
    ctx: Context | None = None,
) -> dict[str, Any]:
    cfg = _load_config()
    try:
        await _chatgpt_enforce_not_blocked(ctx=ctx, action="regenerate")
    except Exception as exc:
        started_at = time.time()
        blocked_state = await _chatgpt_read_blocked_state()
        status = _blocked_status_from_state(blocked_state)
        return {
            "ok": False,
            "status": status,
            "answer": "",
            "conversation_url": str(conversation_url or "").strip(),
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": _run_id(tool="chatgpt_web_regenerate"),
            "error_type": type(exc).__name__,
            "error": _coerce_error_text(exc),
            "blocked_state": blocked_state,
            "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
        }

    started_at = time.time()
    run_id = _run_id(tool="chatgpt_web_regenerate")
    conversation_url_in = str(conversation_url or "").strip()
    pre_guard = None
    conversation_id = _chatgpt_conversation_id_from_url(conversation_url_in)
    if conversation_id:
        pre_guard = await _chatgpt_regenerate_reserve(
            conversation_id=conversation_id,
            reason="explicit regenerate",
            phase="regenerate",
        )
        if not bool(pre_guard.get("allowed")):
            retry_after = 0
            next_allowed = pre_guard.get("next_allowed_at")
            try:
                if isinstance(next_allowed, (int, float)) and next_allowed > 0:
                    retry_after = max(1, int(float(next_allowed) - time.time()))
            except Exception:
                retry_after = 0
            return {
                "ok": False,
                "status": "cooldown",
                "answer": "",
                "conversation_url": conversation_url_in,
                "elapsed_seconds": round(time.time() - started_at, 3),
                "run_id": run_id,
                "error_type": "RegenerateCooldown",
                "error": "regenerate is in cooldown (guardrail)",
                "regenerate_guard": pre_guard,
                "retry_after_seconds": retry_after,
            }
    env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
    with env_ctx:
        async with _page_slot(kind="chatgpt", ctx=ctx), async_playwright() as p:
            browser = None
            context = None
            page = None
            close_context = False
            try:
                browser, context, page, close_context = await _open_chatgpt_page(p, cfg, conversation_url=conversation_url, ctx=ctx)
                await _chatgpt_install_netlog(page, tool="chatgpt_web_regenerate", run_id=run_id, ctx=ctx)

                await _find_prompt_box(page, timeout_ms=max(5_000, int(min(90, timeout_seconds) * 1000)))
                await _wait_for_message_list_to_settle(page)

                conversation_url_effective = (page.url or "").strip() or str(conversation_url or "").strip()
                guard = pre_guard
                if guard is None:
                    conversation_id_effective = _chatgpt_conversation_id_from_url(conversation_url_effective) or _chatgpt_conversation_id_from_url(conversation_url)
                    guard = await _chatgpt_regenerate_reserve(
                        conversation_id=conversation_id_effective,
                        reason="explicit regenerate",
                        phase="regenerate",
                    )
                    if not bool(guard.get("allowed")):
                        retry_after = 0
                        next_allowed = guard.get("next_allowed_at")
                        try:
                            if isinstance(next_allowed, (int, float)) and next_allowed > 0:
                                retry_after = max(1, int(float(next_allowed) - time.time()))
                        except Exception:
                            retry_after = 0
                        return {
                            "ok": False,
                            "status": "cooldown",
                            "answer": "",
                            "conversation_url": conversation_url_effective,
                            "elapsed_seconds": round(time.time() - started_at, 3),
                            "run_id": run_id,
                            "error_type": "RegenerateCooldown",
                            "error": "regenerate is in cooldown (guardrail)",
                            "regenerate_guard": guard,
                            "retry_after_seconds": retry_after,
                        }

                assistant = page.locator(_CHATGPT_ASSISTANT_SELECTOR)
                assistant_count = await assistant.count()
                baseline = ""
                try:
                    baseline = await _last_assistant_text(page)
                except Exception:
                    baseline = ""

                regen_btn = await _find_regenerate_control(page)
                await _human_click(page, regen_btn, timeout_ms=8_000)
                await _human_pause(page)

                regen_started_at = time.time()
                answer = await _wait_for_answer(
                    page,
                    started_at=regen_started_at,
                    start_assistant_count=max(0, assistant_count - 1),
                    timeout_seconds=int(timeout_seconds),
                    min_chars=int(min_chars),
                    require_new=True,
                    baseline_last_text=baseline,
                    ctx=ctx,
                )

                # Prefer raw Markdown when available (avoids rendered-DOM losses for tables/code).
                answer_format = "text"
                try:
                    raw = await _chatgpt_best_effort_last_assistant_raw_markdown(page)
                    if raw and len(raw.strip()) > len((answer or "").strip()):
                        answer = raw
                        answer_format = "markdown"
                except Exception:
                    pass

                result: dict[str, Any] = {
                    "ok": True,
                    "status": "completed",
                    "answer": answer,
                    "answer_format": answer_format,
                    "conversation_url": conversation_url_effective or page.url,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "regenerate_guard": guard,
                }
                try:
                    thinking_obs = await _chatgpt_best_effort_thinking_observation(page, ctx=ctx)
                    if thinking_obs:
                        result["thinking_observation"] = thinking_obs
                        if _truthy_env("CHATGPT_THOUGHT_GUARD_CAPTURE_DEBUG", False) and (
                            bool(thinking_obs.get("thought_too_short"))
                            or bool(thinking_obs.get("skipping"))
                            or bool(thinking_obs.get("answer_now_visible"))
                        ):
                            try:
                                result["thought_guard_debug_artifacts"] = await _capture_debug_artifacts(page, label="thought_guard")
                            except Exception:
                                pass
                    elif _truthy_env("CHATGPT_THOUGHT_GUARD_CAPTURE_DEBUG", False):
                        try:
                            result["thought_guard_debug_artifacts"] = await _capture_debug_artifacts(page, label="thought_guard_missing")
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    thinking_trace = await _chatgpt_capture_thinking_trace(page, ctx=ctx)
                    if thinking_trace:
                        result["thinking_trace"] = thinking_trace
                except Exception:
                    pass

                result = _chatgpt_maybe_offload_answer_result(result, tool="chatgpt_web_regenerate", run_id=run_id)
                _maybe_append_call_log(
                    {
                        "tool": "chatgpt_web_regenerate",
                        "ok": True,
                        "status": result.get("status"),
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "min_chars": min_chars,
                            "conversation_url": conversation_url,
                        },
                        "answer_chars": int(result.get("answer_chars") or len((result.get("answer") or "").strip())),
                    }
                )
                return result
            except TimeoutError as exc:
                artifacts = await _capture_debug_artifacts(page, label="regenerate_timeout") if page is not None else {}
                blocked_state = await _chatgpt_read_blocked_state()
                return {
                    "ok": False,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": (page.url if page is not None else str(conversation_url or "").strip()),
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "error_type": "TimeoutError",
                    "error": _coerce_error_text(exc),
                    "debug_artifacts": artifacts,
                    "blocked_state": blocked_state,
                    "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
                }
            except Exception as exc:
                artifacts = await _capture_debug_artifacts(page, label="regenerate_error") if page is not None else {}
                blocked_state = await _chatgpt_read_blocked_state()
                status = _blocked_status_from_state(blocked_state) if _retry_after_seconds_from_blocked_state(blocked_state) else "error"
                return {
                    "ok": False,
                    "status": status,
                    "answer": "",
                    "conversation_url": (page.url if page is not None else str(conversation_url or "").strip()),
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "error_type": type(exc).__name__,
                    "error": _coerce_error_text(exc),
                    "debug_artifacts": artifacts,
                    "blocked_state": blocked_state,
                    "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
                }
            finally:
                try:
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
                    if close_context and context is not None:
                        await context.close()
                finally:
                    if browser is not None:
                        await browser.close()


_CHATGPT_PRO_EXTENDED_SHORTCUT_PRESET_BY_KEY: dict[str, tuple[str, str]] = {
    "pro_extended": ("5.2 pro", "extended"),
    "thinking_heavy": ("thinking", "heavy"),
}


def _chatgpt_pro_extended_shortcut_settings() -> tuple[str, str]:
    """
    Allow temporarily overriding the `chatgpt_web_ask_pro_extended` shortcut via env var.

    Env:
      - CHATGPT_PRO_EXTENDED_SHORTCUT_PRESET=thinking_heavy|pro_extended(default)
    """
    raw = (os.environ.get("CHATGPT_PRO_EXTENDED_SHORTCUT_PRESET") or "").strip()
    if not raw:
        return _CHATGPT_PRO_EXTENDED_SHORTCUT_PRESET_BY_KEY["pro_extended"]

    key = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    if key in {"default", "pro", "proextended"}:
        key = "pro_extended"
    elif key in {"thinking", "heavy", "thinkingheavy"}:
        key = "thinking_heavy"

    return _CHATGPT_PRO_EXTENDED_SHORTCUT_PRESET_BY_KEY.get(
        key, _CHATGPT_PRO_EXTENDED_SHORTCUT_PRESET_BY_KEY["pro_extended"]
    )


@mcp.tool(
    name="chatgpt_web_ask_pro_extended",
    description=(
        "Shortcut: model=5.2 Pro + thinking_time=Extended, then ask. "
        "Override via CHATGPT_PRO_EXTENDED_SHORTCUT_PRESET=thinking_heavy to use Thinking+Heavy temporarily."
    ),
    structured_output=True,
)
async def ask_pro_extended(
    question: str,
    idempotency_key: str,
    conversation_url: str | None = None,
    timeout_seconds: int = 600,
    file_paths: str | list[str] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    model, thinking_time = _chatgpt_pro_extended_shortcut_settings()
    return await ask(
        question=question,
        idempotency_key=idempotency_key,
        conversation_url=conversation_url,
        timeout_seconds=timeout_seconds,
        model=model,
        thinking_time=thinking_time,
        deep_research=False,
        web_search=False,
        github_repo=None,
        file_paths=file_paths,
        ctx=ctx,
    )


@mcp.tool(
    name="chatgpt_web_ask_deep_research",
    description="Shortcut: enable Deep research, then ask. May return follow-up questions first.",
    structured_output=True,
)
async def ask_deep_research(
    question: str,
    idempotency_key: str,
    conversation_url: str | None = None,
    timeout_seconds: int = 1800,
    model: str = "5.2 pro",
    file_paths: str | list[str] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    return await ask(
        question=question,
        idempotency_key=idempotency_key,
        conversation_url=conversation_url,
        timeout_seconds=timeout_seconds,
        model=model,
        thinking_time=None,
        deep_research=True,
        web_search=False,
        github_repo=None,
        file_paths=file_paths,
        ctx=ctx,
    )


@mcp.tool(
    name="chatgpt_web_ask_web_search",
    description="Shortcut: enable Web search (网页搜索/联网搜索) in the composer, then ask.",
    structured_output=True,
)
async def ask_web_search(
    question: str,
    idempotency_key: str,
    conversation_url: str | None = None,
    timeout_seconds: int = 600,
    model: str = "auto",
    file_paths: str | list[str] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    return await ask(
        question=question,
        idempotency_key=idempotency_key,
        conversation_url=conversation_url,
        timeout_seconds=timeout_seconds,
        model=model,
        thinking_time=None,
        deep_research=False,
        web_search=True,
        agent_mode=False,
        github_repo=None,
        file_paths=file_paths,
        ctx=ctx,
    )


@mcp.tool(
    name="chatgpt_web_ask_agent_mode",
    description="Shortcut: enable Agent mode (代理模式) from the + menu, then ask.",
    structured_output=True,
)
async def ask_agent_mode(
    question: str,
    idempotency_key: str,
    conversation_url: str | None = None,
    timeout_seconds: int = 900,
    model: str = "auto",
    file_paths: str | list[str] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    return await ask(
        question=question,
        idempotency_key=idempotency_key,
        conversation_url=conversation_url,
        timeout_seconds=timeout_seconds,
        model=model,
        thinking_time=None,
        deep_research=False,
        web_search=False,
        agent_mode=True,
        github_repo=None,
        file_paths=file_paths,
        ctx=ctx,
    )


@mcp.tool(
    name="chatgpt_web_ask_thinking_heavy_github",
    description="Shortcut: model=Thinking + thinking_time=Heavy + GitHub connector (repo), then ask.",
    structured_output=True,
)
async def ask_thinking_heavy_github(
    question: str,
    github_repo: str,
    idempotency_key: str,
    conversation_url: str | None = None,
    timeout_seconds: int = 900,
    file_paths: str | list[str] | None = None,
    ctx: Context | None = None,
    ) -> dict[str, Any]:
    return await ask(
        question=question,
        idempotency_key=idempotency_key,
        conversation_url=conversation_url,
        timeout_seconds=timeout_seconds,
        model="thinking",
        thinking_time="heavy",
        deep_research=False,
        web_search=False,
        agent_mode=False,
        github_repo=github_repo,
        file_paths=file_paths,
        ctx=ctx,
    )


@mcp.tool(
    name="chatgpt_web_create_image",
    description="Create an image via ChatGPT web UI (+ → Create image) and save it locally.",
    structured_output=True,
)
async def create_image(
    prompt: str,
    idempotency_key: str,
    conversation_url: str | None = None,
    timeout_seconds: int = 600,
    ctx: Context | None = None,
) -> dict[str, Any]:
    started_at = time.time()
    tool_name = "chatgpt_web_create_image"
    run_id = _run_id(tool=tool_name, idempotency_key=idempotency_key)
    idem = _IdempotencyContext(
        namespace=_idempotency_namespace(ctx),
        tool=tool_name,
        key=_normalize_idempotency_key(idempotency_key),
        request_hash=_hash_request(
            {
                "tool": tool_name,
                "prompt": prompt,
            }
        ),
    )
    should_execute, existing = await _idempotency_begin(idem)
    if not should_execute:
        if isinstance((existing or {}).get("result"), dict):
            cached = dict(existing["result"])
            cached.setdefault("run_id", run_id)
            cached.setdefault(
                "ok",
                bool(
                    str(cached.get("status") or "").strip().lower() not in {"error", "blocked", "cooldown"}
                    and not str(cached.get("error_type") or "").strip()
                    and not str(cached.get("error") or "").strip()
                ),
            )
            cached["replayed"] = True
            return cached
        status = str((existing or {}).get("status") or "in_progress").strip()
        ok = status.lower() not in {"error", "blocked", "cooldown"}
        return {
            "ok": ok,
            "status": status,
            "images": [],
            "conversation_url": str((existing or {}).get("conversation_url") or conversation_url or ""),
            "elapsed_seconds": 0.0,
            "run_id": run_id,
            "replayed": True,
            "error_type": None,
            "error": (str((existing or {}).get("error") or "").strip() or None),
        }
    try:
        result = await _create_image_locked(
            prompt=prompt,
            conversation_url=conversation_url,
            timeout_seconds=timeout_seconds,
            idempotency=idem,
            run_id=run_id,
            ctx=ctx,
        )
        images = result.get("images") if isinstance(result.get("images"), list) else []
        event: dict[str, Any] = {
            "tool": "chatgpt_web_create_image",
            "conversation_url": result.get("conversation_url"),
            "status": result.get("status"),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "run_id": result.get("run_id") or run_id,
            "idempotency_key": idem.key,
            "idempotency_namespace": idem.namespace,
            "params": {
                "timeout_seconds": timeout_seconds,
                "conversation_url": conversation_url,
            },
            "images_count": len(images),
        }
        if _call_log_include_prompts():
            event["prompt"] = prompt
        if isinstance(result.get("debug_artifacts"), dict) and result.get("debug_artifacts"):
            event["debug_artifacts"] = result.get("debug_artifacts")
        if isinstance(result.get("error_type"), str) and str(result.get("error_type") or "").strip():
            event["error_type"] = str(result.get("error_type"))
        if isinstance(result.get("error"), str) and str(result.get("error") or "").strip():
            event["error"] = str(result.get("error"))
        _maybe_append_call_log(event)
        return result
    except Exception as exc:
        try:
            await _idempotency_update(idem, status="error", error=f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
        blocked_state = await _chatgpt_read_blocked_state()
        status = _blocked_status_from_state(blocked_state) if _retry_after_seconds_from_blocked_state(blocked_state) else "error"
        result = {
            "ok": False,
            "status": status,
            "images": [],
            "conversation_url": str(conversation_url or "").strip(),
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "idempotency_key": idem.key,
            "idempotency_namespace": idem.namespace,
            "error_type": type(exc).__name__,
            "error": _coerce_error_text(exc),
            "blocked_state": blocked_state,
            "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
        }
        event = {
            "tool": "chatgpt_web_create_image",
            "status": "error",
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "idempotency_key": idem.key,
            "idempotency_namespace": idem.namespace,
            "params": {
                "timeout_seconds": timeout_seconds,
                "conversation_url": conversation_url,
            },
            "images_count": None,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        if _call_log_include_prompts():
            event["prompt"] = prompt
        _maybe_append_call_log(event)
        return result


async def _create_image_locked(
    *,
    prompt: str,
    conversation_url: str | None,
    timeout_seconds: int,
    idempotency: _IdempotencyContext | None,
    run_id: str,
    ctx: Context | None,
) -> dict[str, Any]:
    cfg = _load_config()
    started_at = time.time()
    try:
        await _chatgpt_enforce_not_blocked(ctx=ctx, action="send")
    except Exception as exc:
        blocked_state = await _chatgpt_read_blocked_state()
        status = _blocked_status_from_state(blocked_state)
        result = {
            "ok": False,
            "status": status,
            "images": [],
            "conversation_url": (str(conversation_url or "").strip() if conversation_url else ""),
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": type(exc).__name__,
            "error": _coerce_error_text(exc),
            "blocked_state": blocked_state,
            "retry_after_seconds": _retry_after_seconds_from_blocked_state(blocked_state),
        }
        if idempotency is not None:
            try:
                await _idempotency_update(
                    idempotency,
                    status="error",
                    conversation_url=str(result.get("conversation_url") or ""),
                    result=result,
                    error=f"{type(exc).__name__}: {exc}",
                )
            except Exception:
                pass
        return result

    if cfg.cdp_url is None and not cfg.storage_state_path.exists():
        msg = (
            f"Missing storage_state.json at {cfg.storage_state_path}. "
            "Run ops/chatgpt_bootstrap_login.py to create it, or set CHATGPT_CDP_URL to use a running Chrome."
        )
        result = {
            "ok": False,
            "status": "error",
            "images": [],
            "conversation_url": (str(conversation_url or "").strip() if conversation_url else ""),
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": "RuntimeError",
            "error": msg,
        }
        if idempotency is not None:
            try:
                await _idempotency_update(
                    idempotency,
                    status="error",
                    conversation_url=str(result.get("conversation_url") or ""),
                    result=result,
                    error=f"RuntimeError: {msg}",
                )
            except Exception:
                pass
        return result
    env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
    with env_ctx:
        async with _page_slot(kind="chatgpt", ctx=ctx), async_playwright() as p:
            browser = None
            context = None
            page = None
            close_context = False
            try:
                browser, context, page, close_context = await _open_chatgpt_page(
                    p, cfg, conversation_url=conversation_url, ctx=ctx
                )
                await _chatgpt_install_netlog(page, tool="chatgpt_web_create_image", run_id=run_id, ctx=ctx)

                await _find_prompt_box(page)
                await _human_pause(page)

                # Create image is currently exposed in the UI for certain model modes (e.g. 5.2 Thinking).
                await _ensure_model(page, model="thinking", ctx=ctx)
                await _human_pause(page)

                async def _try_enable_create_image() -> None:
                    await _ensure_create_image(page, ctx=ctx)

                try:
                    await _try_enable_create_image()
                except Exception:
                    # Some UI states hide Create image in existing threads; fall back to a fresh chat once.
                    await _goto_with_retry(page, cfg.url, ctx=ctx)
                    await _find_prompt_box(page)
                    await _human_pause(page)
                    await _try_enable_create_image()

                start_user_count = await page.locator(_CHATGPT_USER_SELECTOR).count()

                prompt_box = await _find_prompt_box(page)
                await prompt_box.click()
                await _human_pause(page)
                await _type_question(prompt_box, prompt)
                await _human_pause(page)

                send_btn = page.locator(_CHATGPT_SEND_BUTTON_SELECTOR).first
                await _chatgpt_send_prompt(page=page, prompt_box=prompt_box, send_btn=send_btn, ctx=ctx)
                sent_prompt = True
                if idempotency is not None:
                    try:
                        await _idempotency_update(idempotency, sent=True, conversation_url=(page.url or "").strip() or conversation_url)
                    except Exception:
                        pass

                await _wait_for_user_message(page, question=prompt, start_user_count=start_user_count)
                await _ctx_info(ctx, "Waiting for image…")

                images = await _wait_for_generated_images(
                    page,
                    started_at=started_at,
                    timeout_seconds=timeout_seconds,
                    min_area=_chatgpt_image_min_area(),
                )

                out_dir = _chatgpt_output_dir()
                out_dir.mkdir(parents=True, exist_ok=True)
                ts = time.strftime("%Y%m%d_%H%M%S")
                slug = _slugify(prompt[:80])

                saved: list[dict[str, Any]] = []
                for img in images:
                    src = str(img.get("src") or "")
                    if not src:
                        continue
                    raw, mime_type = await _fetch_bytes_via_browser(page, src)
                    ext = {
                        "image/png": "png",
                        "image/jpeg": "jpg",
                        "image/jpg": "jpg",
                        "image/webp": "webp",
                    }.get(mime_type.lower(), "bin")
                    path = out_dir / f"{ts}_{slug}_{random.randint(1000, 9999)}.{ext}"
                    path.write_bytes(raw)
                    saved.append(
                        {
                            "path": str(path),
                            "mime_type": mime_type,
                            "bytes": len(raw),
                            "width": img.get("width"),
                            "height": img.get("height"),
                        }
                    )

                result = {
                    "ok": True,
                    "status": "completed",
                    "images": saved,
                    "conversation_url": page.url,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                }
                if idempotency is not None:
                    try:
                        await _idempotency_update(
                            idempotency,
                            status="completed",
                            conversation_url=str(result.get("conversation_url") or ""),
                            result=result,
                        )
                    except Exception:
                        pass
                return result
            except Exception as exc:
                artifacts: dict[str, str] = {}
                if page is not None:
                    try:
                        artifacts = await _capture_debug_artifacts(page, label="create_image_error")
                    except Exception:
                        artifacts = {}
                    if ctx and artifacts:
                        await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")

                blocked_state = await _chatgpt_read_blocked_state()
                retry_after = _retry_after_seconds_from_blocked_state(blocked_state)
                status = "in_progress" if sent_prompt else (_blocked_status_from_state(blocked_state) if retry_after else "error")
                result = {
                    "ok": False,
                    "status": status,
                    "images": [],
                    "conversation_url": (page.url if page is not None else conversation_url),
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "error_type": type(exc).__name__,
                    "error": _coerce_error_text(exc),
                    "debug_artifacts": artifacts,
                    "blocked_state": blocked_state,
                    "retry_after_seconds": retry_after,
                }
                if idempotency is not None:
                    try:
                        await _idempotency_update(
                            idempotency,
                            status="in_progress" if sent_prompt else "error",
                            sent=bool(sent_prompt),
                            conversation_url=str(result.get("conversation_url") or ""),
                            result=result,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    except Exception:
                        pass
                return result
            finally:
                try:
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
                    if close_context and context is not None:
                        await context.close()
                finally:
                    if browser is not None:
                        await browser.close()




# Provider implementations are split into dedicated modules.
from chatgpt_web_mcp.providers import gemini_web as _gemini_web  # noqa: F401
from chatgpt_web_mcp.providers import qwen_web as _qwen_web  # noqa: F401
from chatgpt_web_mcp.providers import gemini_api as _gemini_api  # noqa: F401

# Tool entrypoints register provider functions with `mcp_registry`.
from chatgpt_web_mcp.tools import gemini_web as _gemini_web_tools  # noqa: F401
from chatgpt_web_mcp.tools import qwen_web as _qwen_web_tools  # noqa: F401
from chatgpt_web_mcp.tools import gemini_api as _gemini_api_tools  # noqa: F401


def __getattr__(name: str) -> Any:  # pragma: no cover - compat shim for split modules
    # Keep legacy imports working after splitting provider implementations.
    # Tests and ops tooling historically imported internal helpers from `chatgpt_web_mcp.server`.
    for mod in (_gemini_web_tools, _qwen_web_tools, _gemini_api_tools, _gemini_web, _qwen_web, _gemini_api):
        try:
            return getattr(mod, name)
        except AttributeError:
            pass

    # Some helpers were moved into shared runtime/playwright modules.
    try:
        from chatgpt_web_mcp.playwright import cdp as _cdp
        from chatgpt_web_mcp.playwright import evidence as _evidence
        from chatgpt_web_mcp.playwright import navigation as _navigation
        from chatgpt_web_mcp.runtime import call_log as _call_log
        from chatgpt_web_mcp.runtime import concurrency as _concurrency
        from chatgpt_web_mcp.runtime import humanize as _humanize
        from chatgpt_web_mcp.runtime import locks as _runtime_locks
        from chatgpt_web_mcp.runtime import paths as _paths
        from chatgpt_web_mcp.runtime import ratelimit as _ratelimit
        from chatgpt_web_mcp.runtime import util as _util
    except Exception as exc:
        raise AttributeError(name) from exc

    for mod in (
        _cdp,
        _evidence,
        _navigation,
        _call_log,
        _concurrency,
        _humanize,
        _runtime_locks,
        _paths,
        _ratelimit,
        _util,
    ):
        try:
            return getattr(mod, name)
        except AttributeError:
            continue

    raise AttributeError(name)
