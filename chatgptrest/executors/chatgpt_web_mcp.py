from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from chatgptrest.core.attachment_contract import (
    attachment_contract_missing_message,
    detect_missing_attachment_contract,
)
from chatgptrest.driver.api import ToolCallError, ToolCaller
from chatgptrest.driver.backends.mcp_http import McpHttpToolCaller
from chatgptrest.executors.base import BaseExecutor, ExecutorResult
from chatgptrest.executors._shared_utils import (
    coerce_int as _coerce_int,
    normalize_phase as _normalize_phase,
    now_monotonic as _now,
    truthy_env as _truthy_env,
)
from chatgptrest.executors.config import ChatGPTExecutorConfig

_cfg = ChatGPTExecutorConfig()
_log = logging.getLogger(__name__)


# ── Preamble heuristic detection ───────────────────────────────────────────
# Fallback when the is_complete signal is unavailable from conversation export.
# Detects short "planning" answers that indicate the model hasn't started the
# real response yet (e.g. "Let me plan…", "I'll start by…").
_PREAMBLE_HEURISTIC_RE = re.compile(
    r"(?:"
    r"let me (?:plan|think|analyze|outline|break|consider)"
    r"|i'?ll (?:start|begin) by"
    r"|here'?s my (?:plan|approach)"
    r"|step \d+:"
    r"|first,? let me"
    r"|让我先"
    r"|我先规划"
    r")",
    re.IGNORECASE,
)

# Only flag as preamble if answer is shorter than this (longer = real answer).
_PREAMBLE_MIN_ANSWER_CHARS = 400
# Only check the first N chars of the answer for preamble patterns.
_PREAMBLE_MAX_CHECK_CHARS = 500


def _preamble_heuristic_check(answer: str) -> bool:
    """Return True if *answer* looks like a preamble (short planning text)."""
    if not answer or len(answer) >= _PREAMBLE_MIN_ANSWER_CHARS:
        return False
    return bool(_PREAMBLE_HEURISTIC_RE.search(answer[:_PREAMBLE_MAX_CHECK_CHARS]))


@dataclass(frozen=True)
class ChatGPTWebJobParams:
    preset: str
    send_timeout_seconds: int
    wait_timeout_seconds: int
    min_chars: int
    max_wait_seconds: int
    answer_format: str
    pro_fallback_presets: tuple[str, ...]
    phase: str


# _now  # re-exported from _shared_utils above


# _coerce_int  # re-exported from _shared_utils above


# _normalize_phase  # re-exported from _shared_utils above


def _is_sent(timeline: Any) -> bool:
    if not isinstance(timeline, list):
        return False
    for ev in timeline:
        if not isinstance(ev, dict):
            continue
        if ev.get("phase") in {"sent", "user_message_confirmed"}:
            return True
    return False


_TRANSIENT_ASSISTANT_ERROR_RE = re.compile(
    r"("
    r"Error in message stream|"
    r"message stream error|"
    r"Network connection lost|"
    r"Attempting to reconnect|"
    r"Something went wrong|"
    r"There was an error"
    r")",
    re.I,
)


def _looks_like_transient_assistant_error(text: str) -> bool:
    trimmed = (text or "").strip()
    if not trimmed:
        return False
    if len(trimmed) > 300:
        return False
    return bool(_TRANSIENT_ASSISTANT_ERROR_RE.search(trimmed))


_ANSWER_ID_RE = re.compile(r"^[0-9a-f]{32}$", re.I)
_CHATGPT_CONVERSATION_ID_ONLY_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)

_CHATGPT_CONVERSATION_URL_RE = re.compile(
    r"^https?://(?:chatgpt\.com|chat\.openai\.com)/c/(?P<cid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:[/?#]|$)",
    re.I,
)


def _normalize_chatgpt_conversation_id(conversation_id: str | None) -> str | None:
    raw = str(conversation_id or "").strip()
    if not raw:
        return None
    if not _CHATGPT_CONVERSATION_ID_ONLY_RE.fullmatch(raw):
        return None
    return raw.lower()

def _normalize_chatgpt_conversation_url(url: str | None) -> str | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    m = _CHATGPT_CONVERSATION_URL_RE.match(raw)
    if not m:
        return None
    cid = _normalize_chatgpt_conversation_id(m.group("cid"))
    if not cid:
        return None
    return f"https://chatgpt.com/c/{cid}"


def _chatgpt_conversation_url_from_id(conversation_id: str) -> str:
    cid = _normalize_chatgpt_conversation_id(conversation_id)
    if not cid:
        raise ValueError("invalid conversation_id")
    return f"https://chatgpt.com/c/{cid}"


def _default_chatgptmcp_root() -> Path:
    raw = (os.environ.get("CHATGPTREST_CHATGPTMCP_ROOT") or "").strip() or _cfg.mcp_root
    if raw:
        return Path(raw).expanduser()
    # Default to sibling repo layout: projects/ChatgptREST ↔ projects/chatgptMCP
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root / "../chatgptMCP").resolve()


def _default_driver_roots() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[2]
    raw_roots: list[Path] = []
    for env_name in ("CHATGPTREST_DRIVER_ROOT", "CHATGPTREST_ARTIFACTS_DIR"):
        raw = os.environ.get(env_name)
        if raw and raw.strip():
            raw_roots.append(Path(raw.strip()).expanduser())
    raw_roots.append(_default_chatgptmcp_root())
    raw_roots.append(repo_root)

    roots: list[Path] = []
    seen: set[str] = set()
    for root in raw_roots:
        try:
            resolved = root.expanduser().resolve()
        except Exception:
            resolved = root.expanduser()
        key = resolved.as_posix()
        if key in seen:
            continue
        seen.add(key)
        roots.append(resolved)
    return roots


def _resolve_chatgptmcp_artifact_path(*, rel_or_abs_path: str, roots: list[Path]) -> Path | None:
    raw = str(rel_or_abs_path or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if p.is_absolute():
        candidates = [p]
    else:
        candidates = [(root.resolve() / p) for root in roots]

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            continue
        if not resolved.exists():
            continue
        for root in roots:
            root = root.resolve()
            if resolved == root:
                continue
            if root in resolved.parents:
                return resolved
    return None


def _read_chatgptmcp_debug_text(*, debug_artifacts: Any, max_chars: int = 200_000) -> str | None:
    if not isinstance(debug_artifacts, dict):
        return None
    text_path = debug_artifacts.get("text")
    if not isinstance(text_path, str) or not text_path.strip():
        return None
    resolved = _resolve_chatgptmcp_artifact_path(rel_or_abs_path=text_path, roots=_default_driver_roots())
    if resolved is None or not resolved.exists():
        return None
    try:
        content = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    return content[: max(0, int(max_chars))]


def _extract_chatgpt_export_model_info(*, export_path: str) -> dict[str, Any] | None:
    resolved = _resolve_chatgptmcp_artifact_path(rel_or_abs_path=export_path, roots=_default_driver_roots())
    if resolved is None:
        return None
    try:
        obj = json.loads(resolved.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None

    mapping = obj.get("mapping")
    if not isinstance(mapping, dict):
        return None
    cur = obj.get("current_node")
    if not isinstance(cur, str) or not cur:
        return None

    seen: set[str] = set()
    last_meta: dict[str, Any] | None = None
    while cur and cur not in seen:
        seen.add(cur)
        node = mapping.get(cur)
        if not isinstance(node, dict):
            cur = ""
            continue
        msg = node.get("message")
        if isinstance(msg, dict):
            author = msg.get("author")
            role = author.get("role") if isinstance(author, dict) else None
            if role == "assistant":
                meta = msg.get("metadata")
                last_meta = meta if isinstance(meta, dict) else {}
                break
        parent = node.get("parent")
        cur = parent if isinstance(parent, str) else ""

    if last_meta is None:
        return None

    finish_details = last_meta.get("finish_details")
    finish_type = finish_details.get("type") if isinstance(finish_details, dict) else None

    return {
        "export_conversation_id": obj.get("conversation_id"),
        "export_default_model_slug": obj.get("default_model_slug"),
        "export_last_assistant_model_slug": (last_meta.get("model_slug") or last_meta.get("default_model_slug")),
        "export_last_assistant_thinking_effort": (last_meta.get("thinking_effort") or last_meta.get("reasoning_effort")),
        "export_last_assistant_finish_type": finish_type,
        "export_last_assistant_is_complete": last_meta.get("is_complete"),
    }


def _augment_with_export_model_info(result: dict[str, Any]) -> None:
    if not isinstance(result, dict):
        return
    export_path = str(result.get("export_path") or "").strip()
    if not export_path:
        return
    info = _extract_chatgpt_export_model_info(export_path=export_path)
    if not isinstance(info, dict) or not info:
        return
    for k, v in info.items():
        result.setdefault(k, v)


def _looks_like_answer_now_writing_code_stuck(debug_text: str) -> bool:
    s = (debug_text or "").strip()
    if not s:
        return False
    lower = s.lower()
    return ("writing code" in lower) and ("answer now" in lower)

def _looks_like_pro_thinking_skipping(debug_text: str) -> bool:
    s = (debug_text or "").strip()
    if not s:
        return False
    # UI marker for the thinking panel being forced into a "skip" state.
    # Example in debug artifacts:
    #   "Pro thinking • Skipping"
    return bool(re.search(r"pro\s+thinking\s*[•·]\s*skipping", s, re.I))


def _thought_guard_min_seconds() -> int:
    val = _cfg.thought_guard_min_seconds
    return max(0, int(val)) if val else 300


def _thought_guard_auto_regenerate_enabled() -> bool:
    return _cfg.thought_guard_auto_regenerate


_truthy_env  # re-exported from _shared_utils above


def _thought_guard_require_thought_for_enabled() -> bool:
    # Strict mode: require the UI footer to contain a "Thought for Xm Ys" style duration.
    # When enabled, missing thinking_observation is treated as abnormal (fail-closed).
    return _cfg.thought_guard_require_thought_for


def _thought_guard_trigger_too_short() -> bool:
    return _cfg.thought_guard_trigger_too_short


def _thought_guard_trigger_skipping() -> bool:
    return _cfg.thought_guard_trigger_skipping


def _thought_guard_trigger_answer_now() -> bool:
    return _cfg.thought_guard_trigger_answer_now


def _extract_thinking_observation(result: dict[str, Any]) -> dict[str, Any] | None:
    obs = result.get("thinking_observation")
    return obs if isinstance(obs, dict) else None


def _thought_guard_is_abnormal(
    *,
    obs: dict[str, Any] | None,
    min_seconds: int,
    require_thought_for: bool,
    trigger_too_short: bool,
    trigger_skipping: bool,
    trigger_answer_now: bool,
) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {
        "min_seconds": int(min_seconds),
        "require_thought_for": bool(require_thought_for),
        "trigger_too_short": bool(trigger_too_short),
        "trigger_skipping": bool(trigger_skipping),
        "trigger_answer_now": bool(trigger_answer_now),
    }
    if not obs:
        details["missing_observation"] = True
        return (True, details) if require_thought_for else (False, details)

    skipping = bool(obs.get("skipping"))
    answer_now_visible = bool(obs.get("answer_now_visible"))
    thought_seconds = obs.get("thought_seconds")
    thought_for_present = obs.get("thought_for_present")
    if isinstance(thought_for_present, bool):
        thought_for_present_bool = bool(thought_for_present)
    else:
        thought_for_present_bool = isinstance(thought_seconds, (int, float)) and int(thought_seconds) > 0
    details["skipping"] = skipping
    details["answer_now_visible"] = answer_now_visible
    details["thought_for_present"] = bool(thought_for_present_bool)

    if require_thought_for and not thought_for_present_bool:
        details["thought_too_short"] = False
        details["reason"] = "missing_thought_for"
        return True, details

    if isinstance(thought_seconds, (int, float)):
        details["thought_seconds"] = int(thought_seconds)
        if trigger_too_short and int(min_seconds) > 0 and int(thought_seconds) < int(min_seconds):
            details["thought_too_short"] = True
            details["reason"] = "thought_too_short"
            return True, details
    details["thought_too_short"] = False
    if trigger_skipping and skipping:
        details["reason"] = "skipping"
        return True, details
    if trigger_answer_now and answer_now_visible:
        details["reason"] = "answer_now"
        return True, details
    return False, details


def _tool_and_args(
    *,
    preset: str,
    question: str,
    conversation_url: str | None,
    idempotency_key: str,
    file_paths: list[str] | None,
    github_repo: str | None,
    timeout_seconds: int,
    deep_research: bool,
    web_search: bool,
    agent_mode: bool,
) -> tuple[str, Dict[str, Any]]:
    base_args: Dict[str, Any] = {
        "idempotency_key": idempotency_key,
        "question": question,
        "timeout_seconds": int(timeout_seconds),
    }
    if conversation_url:
        base_args["conversation_url"] = conversation_url
    if file_paths:
        base_args["file_paths"] = list(file_paths)
    if github_repo:
        base_args["github_repo"] = github_repo
    if agent_mode:
        base_args["agent_mode"] = True

    preset = str(preset or "auto").strip().lower()

    if deep_research:
        return "chatgpt_web_ask_deep_research", base_args
    if web_search:
        # Prefer the generic tool when a specific model/thinking preset is desired.
        if preset == "pro_extended":
            base_args["model"] = "5.2 pro"
            base_args["thinking_time"] = "extended"
            base_args["web_search"] = True
            return "chatgpt_web_ask", base_args
        if preset == "thinking_heavy":
            base_args["model"] = "thinking"
            base_args["thinking_time"] = "heavy"
            base_args["web_search"] = True
            return "chatgpt_web_ask", base_args
        if preset == "thinking_extended":
            base_args["model"] = "thinking"
            base_args["thinking_time"] = "extended"
            base_args["web_search"] = True
            return "chatgpt_web_ask", base_args
        return "chatgpt_web_ask_web_search", base_args

    if preset == "pro_extended":
        return "chatgpt_web_ask_pro_extended", base_args
    if preset == "thinking_heavy":
        base_args["model"] = "thinking"
        base_args["thinking_time"] = "heavy"
        return "chatgpt_web_ask", base_args
    if preset == "thinking_extended":
        base_args["model"] = "thinking"
        base_args["thinking_time"] = "extended"
        return "chatgpt_web_ask", base_args

    # Default: auto model selection.
    return "chatgpt_web_ask", base_args


class ChatGPTWebMcpExecutor(BaseExecutor):
    def __init__(
        self,
        *,
        mcp_url: str | None = None,
        tool_caller: ToolCaller | None = None,
        client_name: str = "chatgptrest",
        client_version: str = "0.1.0",
        pro_fallback_presets: tuple[str, ...] = ("thinking_heavy", "auto"),
    ):
        if tool_caller is None:
            if not mcp_url:
                raise ValueError("mcp_url is required when tool_caller is not provided")
            tool_caller = McpHttpToolCaller(url=mcp_url, client_name=client_name, client_version=client_version)
        self._client = tool_caller
        self._pro_fallback_presets = tuple([p.strip() for p in pro_fallback_presets if p.strip()])

    async def _rehydrate_answer_from_answer_id(
        self,
        *,
        answer_id: str,
        expected_chars: int | None,
        timeout_seconds: float,
        max_total_chars: int = 2_000_000,
    ) -> str | None:
        key = str(answer_id or "").strip().lower()
        if not _ANSWER_ID_RE.fullmatch(key):
            return None

        # chatgptMCP's answer_get is char-offset based.
        offset = 0
        chunks: list[str] = []
        total = 0
        deadline = _now() + float(max(10.0, timeout_seconds))
        for _ in range(1000):
            if _now() > deadline:
                break
            res = await asyncio.to_thread(
                self._client.call_tool,
                tool_name="chatgpt_web_answer_get",
                tool_args={"answer_id": key, "offset": int(offset), "max_chars": 20000},
                timeout_sec=_cfg.answer_get_timeout_seconds,
            )
            if not isinstance(res, dict) or not bool(res.get("ok")):
                return None
            chunk = str(res.get("chunk") or "")
            chunks.append(chunk)
            total += len(chunk)
            if total >= int(max_total_chars):
                break
            if bool(res.get("done")):
                break
            next_offset = res.get("next_offset")
            if not isinstance(next_offset, int) or next_offset <= offset:
                break
            offset = next_offset

        text = "".join(chunks)
        if not text.strip():
            return None
        if expected_chars is not None and expected_chars > 0 and len(text) < max(1, int(expected_chars) - 50):
            # Incomplete rehydration; keep the original truncated answer.
            return None
        return text

    async def run(self, *, job_id: str, kind: str, input: dict[str, Any], params: dict[str, Any]) -> ExecutorResult:  # noqa: A002
        import uuid as _uuid
        _trace_id = f"exec:{job_id}:{_uuid.uuid4().hex[:8]}"

        if kind == "chatgpt_web.conversation_export":
            return await self._run_conversation_export(job_id=job_id, input=input, params=params)
        if kind == "chatgpt_web.extract_answer":
            return await self._run_conversation_export(job_id=job_id, input=input, params=params)
        if kind != "chatgpt_web.ask":
            return ExecutorResult(status="error", answer=f"Unknown kind: {kind}", meta={"error_type": "ValueError", "trace_id": _trace_id})


        question = str(input.get("question") or "").strip()
        if not question:
            return ExecutorResult(status="error", answer="Missing input.question", meta={"error_type": "ValueError"})

        # Preflight: avoid any "send prompt" attempt if the underlying chatgptMCP
        # server is already in a stop-the-world blocked/cooldown state.
        try:
            preflight = await asyncio.to_thread(
                self._client.call_tool,
                tool_name="chatgpt_web_blocked_status",
                tool_args={},
                timeout_sec=_cfg.preflight_timeout_seconds,
            )
            if isinstance(preflight, dict) and bool(preflight.get("blocked")):
                wait_seconds = float(preflight.get("seconds_until_unblocked") or 0.0)
                not_before = float(preflight.get("blocked_until") or (_now() + wait_seconds))
                reason = str(preflight.get("reason") or "").strip() or "blocked"
                status = "cooldown" if wait_seconds > 0 else "blocked"
                return ExecutorResult(
                    status=status,
                    answer=f"chatgptMCP blocked: {reason}",
                    meta={
                        "error_type": "Blocked",
                        "error": f"chatgptMCP blocked: {reason}",
                        "retry_after_seconds": wait_seconds if wait_seconds > 0 else None,
                        "not_before": not_before,
                        "preflight_blocked_status": preflight,
                    },
                )
        except ToolCallError:
            pass
        except Exception:
            pass

        conversation_url = str(input.get("conversation_url") or "").strip() or None
        file_paths = input.get("file_paths")
        if file_paths is not None and not isinstance(file_paths, list):
            file_paths = None
        github_repo = str(input.get("github_repo") or "").strip() or None

        deep_research = bool(params.get("deep_research") or False)
        web_search = bool(params.get("web_search") or False)
        agent_mode = bool(params.get("agent_mode") or False)

        preset = str(params.get("preset") or "auto").strip().lower()
        phase = _normalize_phase(params.get("phase") or params.get("execution_phase"))
        base_timeout = _coerce_int(params.get("timeout_seconds"), 600)
        send_timeout_raw = params.get("send_timeout_seconds")
        send_timeout_seconds = max(30, _coerce_int(send_timeout_raw, base_timeout))
        # Keep the send/ask stage relatively short so we can promptly switch into wait/export recovery
        # without blocking the send queue. Use CHATGPTREST_DEFAULT_SEND_TIMEOUT_SECONDS=0 to disable.
        cap = _cfg.default_send_timeout_seconds
        if not cap:
            cap = 180
        if cap > 0:
            send_timeout_seconds = min(send_timeout_seconds, max(30, cap))
        wait_timeout_seconds = max(30, _coerce_int(params.get("wait_timeout_seconds"), base_timeout))
        max_wait_seconds = max(30, _coerce_int(params.get("max_wait_seconds"), 1800))
        min_chars = max(0, _coerce_int(params.get("min_chars"), 800))
        answer_format = str(params.get("answer_format") or "markdown").strip().lower()
        if answer_format not in {"markdown", "text"}:
            answer_format = "markdown"

        thought_guard_min_seconds = _thought_guard_min_seconds()
        thought_guard_auto_regen = _thought_guard_auto_regenerate_enabled()
        thought_guard_require_thought_for = _thought_guard_require_thought_for_enabled()
        thought_guard_trigger_too_short = _thought_guard_trigger_too_short()
        thought_guard_trigger_skipping = _thought_guard_trigger_skipping()
        thought_guard_trigger_answer_now = _thought_guard_trigger_answer_now()

        contract_signal = detect_missing_attachment_contract(kind=kind, input_obj=input, params_obj=params)
        if phase != "wait" and isinstance(contract_signal, dict) and bool(contract_signal.get("high_risk")):
            message = attachment_contract_missing_message(contract_signal)
            return ExecutorResult(
                status="error",
                answer=message,
                answer_format=answer_format,
                meta={
                    "error_type": "AttachmentContractMissing",
                    "error": message,
                    "family_id": str(contract_signal.get("family_id") or "attachment_contract_missing"),
                    "family_label": str(contract_signal.get("family_label") or "Attachment contract missing"),
                    "attachment_contract": dict(contract_signal),
                },
            )

        async def _resolve_conversation_url_from_idempotency(key: str) -> str:
            if not key:
                return ""
            try:
                idem = await asyncio.to_thread(
                    self._client.call_tool,
                    tool_name="chatgpt_web_idempotency_get",
                    tool_args={"idempotency_key": key, "include_result": False},
                    timeout_sec=_cfg.idempotency_get_timeout_seconds,
                )
            except Exception:
                return ""
            if not isinstance(idem, dict) or not bool(idem.get("ok")):
                return ""
            record = idem.get("record")
            if not isinstance(record, dict):
                return ""
            return str(record.get("conversation_url") or "").strip()

        async def _idempotency_sent_flag(key: str) -> bool | None:
            if not key:
                return None
            try:
                idem = await asyncio.to_thread(
                    self._client.call_tool,
                    tool_name="chatgpt_web_idempotency_get",
                    tool_args={"idempotency_key": key, "include_result": False},
                    timeout_sec=_cfg.idempotency_get_timeout_seconds,
                )
            except Exception:
                return None
            if not isinstance(idem, dict) or not bool(idem.get("ok")):
                return None
            record = idem.get("record")
            if not isinstance(record, dict):
                return None
            sent = record.get("sent")
            if sent is None:
                return None
            return bool(sent)

        async def _wait_loop(*, conversation_url: str | None, idempotency_key: str | None) -> tuple[dict[str, Any], str]:
            url = str(conversation_url or "").strip()
            result: dict[str, Any] = {"status": "in_progress", "conversation_url": url}

            if not url and idempotency_key:
                # Robust "no conversation_url yet" handling:
                # - do NOT treat it as an error (attachment uploads/new-chat init can be slow),
                # - avoid creating duplicate user messages by only polling idempotency state.
                try:
                    idem = await asyncio.to_thread(
                        self._client.call_tool,
                        tool_name="chatgpt_web_idempotency_get",
                        tool_args={"idempotency_key": idempotency_key, "include_result": True},
                        timeout_sec=_cfg.idempotency_get_timeout_seconds,
                    )
                except Exception:
                    idem = None
                if isinstance(idem, dict) and bool(idem.get("ok")):
                    record = idem.get("record")
                    if isinstance(record, dict):
                        url = str(record.get("conversation_url") or "").strip() or url
                        cached = record.get("result")
                        if isinstance(cached, dict):
                            cached_status = str(cached.get("status") or "").strip().lower()
                            if cached_status and cached_status != "in_progress":
                                url = str(cached.get("conversation_url") or "").strip() or url
                                return cached, url

            _run_id_ref = {"run_id": None}

            def _on_chatgpt_wait_result(wait_res: dict[str, Any], cur_url: str) -> tuple[dict[str, Any], str]:
                try:
                    _augment_with_export_model_info(wait_res)
                except Exception:
                    pass
                wait_res["conversation_url"] = cur_url
                wait_res.setdefault("_wait_for", _run_id_ref.get("run_id"))
                return wait_res, cur_url

            return await self._wait_loop_core(
                client=self._client,
                tool_name="chatgpt_web_wait",
                conversation_url=url or "",
                wait_timeout_seconds=wait_timeout_seconds,
                max_wait_seconds=max_wait_seconds,
                min_chars=min_chars,
                on_wait_result=_on_chatgpt_wait_result,
            )

        # For safety, avoid idempotency collisions between presets.
        primary_key = f"chatgptrest:{job_id}:{preset}"
        transient_error_text = None

        if phase == "wait":
            # Only a thread URL is meaningful for wait-phase polling. A base URL like
            # https://chatgpt.com/ can get persisted transiently and would wedge the job in "wait".
            conversation_url = _normalize_chatgpt_conversation_url(conversation_url) or None
            if not conversation_url and primary_key:
                recovered = await _resolve_conversation_url_from_idempotency(primary_key) or ""
                conversation_url = _normalize_chatgpt_conversation_url(recovered) or None
            result, conversation_url = await _wait_loop(conversation_url=conversation_url, idempotency_key=primary_key)
            status = str(result.get("status") or "").strip().lower()
        else:
            tool_name, tool_args = _tool_and_args(
                preset=preset,
                question=question,
                conversation_url=conversation_url,
                idempotency_key=primary_key,
                file_paths=(list(file_paths) if isinstance(file_paths, list) else None),
                github_repo=github_repo,
                timeout_seconds=send_timeout_seconds,
                deep_research=deep_research,
                web_search=web_search,
                agent_mode=agent_mode,
            )
            # Phase 2: fire-and-forget send — return immediately after the prompt
            # is confirmed sent, without waiting for the model's answer.
            if phase == "send":
                tool_args["fire_and_forget"] = True

            try:
                result = await asyncio.to_thread(
                    self._client.call_tool,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    timeout_sec=float(send_timeout_seconds) + 30.0,
                )
            except ToolCallError as exc:
                wait_seconds = 60.0
                return ExecutorResult(
                    status="cooldown",
                    answer=f"tool call failed: {exc}",
                    answer_format=answer_format,
                    meta={
                        "error_type": "ToolCallError",
                        "error": str(exc),
                        "retry_after_seconds": wait_seconds,
                        "not_before": _now() + wait_seconds,
                    },
                )

            # Optional: pro preset fallback when model selection is temporarily disabled.
            if preset == "pro_extended":
                blocked_state = result.get("blocked_state") or {}
                reason = str(blocked_state.get("reason") or "").strip().lower()
                status = str(result.get("status") or "").strip().lower()
                error = str(result.get("error") or "").lower()
                sent = _is_sent(result.get("debug_timeline"))
                may_fallback = (not sent) and status in {"cooldown", "blocked"} and (reason == "unusual_activity" or "unusual activity" in error)
                if may_fallback:
                    # Strongest guardrail: never risk a second user message if the primary idempotency
                    # record indicates the prompt was already sent (even if debug_timeline is missing).
                    idem_sent = await _idempotency_sent_flag(primary_key)
                    if idem_sent is True:
                        result["_fallback_suppressed"] = True
                        result["_fallback_suppressed_reason"] = "idempotency_sent_true"
                        result["status"] = "in_progress"
                        may_fallback = False

                    # Avoid any risk of duplicate user messages: if we already have a thread URL (or can
                    # resolve one via idempotency), treat this as sent and switch to wait instead of
                    # re-asking with a different preset.
                    input_thread_url = _normalize_chatgpt_conversation_url(conversation_url)
                    existing_url_raw = str(result.get("conversation_url") or "").strip()
                    existing_thread_url = _normalize_chatgpt_conversation_url(existing_url_raw)
                    if not existing_thread_url:
                        try:
                            recovered = await _resolve_conversation_url_from_idempotency(primary_key)
                        except Exception:
                            recovered = ""
                        recovered_thread_url = _normalize_chatgpt_conversation_url(recovered)
                        if recovered_thread_url:
                            existing_thread_url = recovered_thread_url
                            result.setdefault("conversation_url", recovered_thread_url)

                    # Only treat a thread URL as evidence of a (possibly) sent prompt when:
                    # - the tool produced a thread URL in a new-chat context, or
                    # - the tool produced a different thread URL than the caller provided.
                    #
                    # A plain https://chatgpt.com/ landing page URL is NOT a thread and must never
                    # suppress fallback; otherwise we can incorrectly switch to wait-phase without
                    # having sent any user message (job gets stuck waiting on a non-thread URL).
                    if existing_thread_url and (not input_thread_url or existing_thread_url != input_thread_url):
                        result["_fallback_suppressed"] = True
                        result["_fallback_suppressed_reason"] = "conversation_url_present"
                        result["status"] = "in_progress"
                        may_fallback = False
                if may_fallback:
                    for fb in self._pro_fallback_presets:
                        fb = str(fb or "").strip().lower()
                        if not fb or fb == preset:
                            continue
                        fb_key = f"chatgptrest:{job_id}:{fb}"
                        fb_tool, fb_args = _tool_and_args(
                            preset=fb,
                            question=question,
                            conversation_url=conversation_url,
                            idempotency_key=fb_key,
                            file_paths=(list(file_paths) if isinstance(file_paths, list) else None),
                            github_repo=github_repo,
                            timeout_seconds=send_timeout_seconds,
                            deep_research=deep_research,
                            web_search=web_search,
                            agent_mode=agent_mode,
                        )
                        fb_res = await asyncio.to_thread(
                            self._client.call_tool,
                            tool_name=fb_tool,
                            tool_args=fb_args,
                            timeout_sec=float(send_timeout_seconds) + 30.0,
                        )
                        fb_res["_fallback_from"] = preset
                        fb_res["_fallback_preset"] = fb
                        result = fb_res
                        break

            # Auto-wait loop for in_progress results (no new prompt).
            status = str(result.get("status") or "").strip().lower()
            raw_url = str(result.get("conversation_url") or "").strip()
            tool_thread_url = _normalize_chatgpt_conversation_url(raw_url)
            input_thread_url = _normalize_chatgpt_conversation_url(conversation_url)
            if tool_thread_url:
                conversation_url = tool_thread_url
                result["conversation_url"] = tool_thread_url
            else:
                # Do not surface non-thread URLs as "conversation_url": they can block single-flight guards
                # and wedge wait-phase polling. Keep the raw value for debugging and allow idempotency-based
                # recovery to discover the eventual thread URL.
                if raw_url:
                    result.setdefault("_non_thread_conversation_url", raw_url)
                    result["conversation_url"] = ""
                conversation_url = input_thread_url or ""
                if conversation_url:
                    result["conversation_url"] = conversation_url

            if status == "in_progress" and not conversation_url:
                recovered = await _resolve_conversation_url_from_idempotency(primary_key)
                if recovered:
                    thread_url = _normalize_chatgpt_conversation_url(recovered)
                    if thread_url:
                        conversation_url = thread_url
                        result["conversation_url"] = conversation_url
                else:
                    # Do not fail-closed here: attachment uploads / new-chat init can be slow and
                    # conversation_url may appear later in the driver idempotency record.
                    # Keep the job `in_progress` and let the worker requeue it (two-phase scheduling).
                    wait_seconds = 60.0 + random.uniform(0.0, 3.0)
                    result["_send_stage_no_conversation_url"] = True
                    result.setdefault("retry_after_seconds", wait_seconds)
                    result.setdefault("not_before", _now() + wait_seconds)
                    result.setdefault("error_type", "SendStuckNoConversationUrl")
                    result.setdefault(
                        "error",
                        "send stage returned in_progress without conversation_url; will retry via idempotency",
                    )

            # If the initial ask timed out and the UI is stuck in "Writing code" with an "Answer now"
            # affordance, waiting longer usually won't produce a final assistant message without
            # manual intervention. Surface this as NEEDS_FOLLOWUP to free the worker.
            if status == "in_progress":
                debug_text = _read_chatgptmcp_debug_text(debug_artifacts=result.get("debug_artifacts"))
                if debug_text and _looks_like_answer_now_writing_code_stuck(debug_text):
                    # This marker is a common false positive: ChatGPT may show "Answer now" while
                    # thinking and "Writing code" can appear in the page even when the UI is not
                    # truly stuck. Keep the job in progress and let the wait phase + export recovery
                    # attempt to collect the final answer without re-sending a prompt.
                    wait_seconds = 60.0 + random.uniform(0.0, 3.0)
                    result.setdefault("_debug_text_markers", {})
                    try:
                        markers = dict(result.get("_debug_text_markers") or {})
                        markers.setdefault("writing_code", True)
                        markers.setdefault("answer_now", True)
                        result["_debug_text_markers"] = markers
                    except Exception:
                        result["_debug_text_markers"] = {"writing_code": True, "answer_now": True}
                    result.setdefault("retry_after_seconds", wait_seconds)
                    result.setdefault("not_before", _now() + wait_seconds)
                    result.setdefault("error_type", "InProgress")
                    result.setdefault(
                        "error",
                        "ui shows 'Answer now'/'Writing code'; continuing wait without re-sending",
                    )
                if debug_text and _looks_like_pro_thinking_skipping(debug_text):
                    try:
                        markers = dict(result.get("_debug_text_markers") or {})
                    except Exception:
                        markers = {}
                    markers.setdefault("pro_thinking_skipping", True)
                    result["_debug_text_markers"] = markers

            if status in {"completed", "error"} and conversation_url:
                cand_answer = str(result.get("answer") or "")
                cand_error = str(result.get("error") or "")
                if _looks_like_transient_assistant_error(cand_answer):
                    transient_error_text = cand_answer.strip()
                elif _looks_like_transient_assistant_error(cand_error):
                    transient_error_text = cand_error.strip()

            if transient_error_text:
                # Treat short "message stream" type errors as retryable network hiccups: don't accept them
                # as a completed answer; wait in-place (same conversation) instead of re-sending the prompt.
                result["_transient_error_detected"] = True
                result["_transient_error_text"] = transient_error_text
                result["status"] = "in_progress"
                status = "in_progress"
                min_chars = max(int(min_chars), 200)

            # ── RC-1 fix: Preamble completion guard for thinking presets ──────
            # When using thinking_extended or pro_extended, ChatGPT often emits a
            # short preamble message (93-217 bytes, channel=commentary,
            # is_thinking_preamble_message=true) before the real answer.  The
            # driver may capture this preamble and report status=completed.  We
            # detect this and force the status back to in_progress so the wait
            # loop continues polling for the actual answer.
            #
            # Detection strategy (layered, any trigger rejects):
            #   1. Length-only: thinking presets ALWAYS produce 1000+ char answers.
            #      Any answer < _PREAMBLE_MIN_ANSWER_CHARS is definitely premature.
            #   2. Regex: catches preamble patterns at borderline lengths.
            #   3. is_complete=False: driver explicitly says it's not done.
            _PREAMBLE_GUARD_PRESETS = {"thinking_extended", "pro_extended", "thinking_heavy"}
            if (
                status in ("completed", "in_progress")
                and preset in _PREAMBLE_GUARD_PRESETS
                and conversation_url
            ):
                cand_answer = str(result.get("answer") or "")
                is_preamble = False
                # Layer 1: hard length gate — these presets never produce short answers
                if len(cand_answer) < _PREAMBLE_MIN_ANSWER_CHARS:
                    is_preamble = True
                    _log.info(
                        "preamble guard [length]: %d chars < %d threshold for preset=%s",
                        len(cand_answer), _PREAMBLE_MIN_ANSWER_CHARS, preset,
                    )
                # Layer 2: regex pattern match (catches borderline-length preambles)
                if not is_preamble:
                    is_preamble = _preamble_heuristic_check(cand_answer)
                # Layer 3: driver's is_complete signal
                is_complete_raw = result.get("is_complete")
                if is_complete_raw is False:
                    is_preamble = True
                if is_preamble:
                    result["_preamble_guard_triggered"] = True
                    result["_preamble_answer_chars"] = len(cand_answer)
                    result["_preamble_answer_preview"] = cand_answer[:200]
                    result["status"] = "in_progress"
                    status = "in_progress"
                    # Bump min_chars so the wait loop won't accept another short answer.
                    min_chars = max(int(min_chars), _PREAMBLE_MIN_ANSWER_CHARS)
                    _log.info(
                        "preamble guard: rejecting %d-char answer for preset=%s, "
                        "forcing in_progress wait",
                        len(cand_answer), preset,
                    )

            if phase == "full" and status == "in_progress" and conversation_url:
                result, conversation_url = await _wait_loop(conversation_url=conversation_url, idempotency_key=primary_key)
                status = str(result.get("status") or "").strip().lower()

            # If we still don't have a real answer, surface a retryable cooldown state with context.
            if phase == "full" and status == "in_progress" and transient_error_text:
                result["status"] = "cooldown"
                result["answer"] = transient_error_text
                result.setdefault("error_type", "TransientAssistantError")
                result.setdefault("retry_after_seconds", 180)
                status = "cooldown"

            # Quality guard (no extra prompt send):
            # When using Pro Extended, a "Thought for" duration < threshold, or a visible Skipping/Answer-now
            # marker, indicates degraded generation. Optionally trigger a single UI Regenerate attempt.
            should_thought_guard = bool(preset == "pro_extended" and (not deep_research or thought_guard_require_thought_for))
            if should_thought_guard:
                obs = _extract_thinking_observation(result)
                abnormal, guard_details = _thought_guard_is_abnormal(
                    obs=obs,
                    min_seconds=thought_guard_min_seconds,
                    require_thought_for=thought_guard_require_thought_for,
                    trigger_too_short=thought_guard_trigger_too_short,
                    trigger_skipping=thought_guard_trigger_skipping,
                    trigger_answer_now=thought_guard_trigger_answer_now,
                )
                if abnormal:
                    result.setdefault("_thought_guard", {})
                    try:
                        result["_thought_guard"] = dict(result.get("_thought_guard") or {})
                    except Exception:
                        result["_thought_guard"] = {}
                    result["_thought_guard"].update({"enabled": True, **guard_details})
                    if thought_guard_auto_regen and conversation_url:
                        try:
                            regen = await asyncio.to_thread(
                                self._client.call_tool,
                                tool_name="chatgpt_web_regenerate",
                                tool_args={
                                    "conversation_url": conversation_url,
                                    "timeout_seconds": int(max(60, min(wait_timeout_seconds, max_wait_seconds))),
                                    "min_chars": int(min_chars),
                                },
                                timeout_sec=float(max(90, min(wait_timeout_seconds, max_wait_seconds))) + 30.0,
                            )
                        except Exception as exc:
                            result["_thought_guard"]["action"] = "regenerate_error"
                            result["_thought_guard"]["regenerate_error"] = f"{type(exc).__name__}: {exc}"
                        else:
                            if isinstance(regen, dict) and bool(regen.get("ok")) and str(regen.get("status") or "").strip().lower() == "completed":
                                regen.setdefault("_thought_guard", {})
                                try:
                                    regen["_thought_guard"] = dict(regen.get("_thought_guard") or {})
                                except Exception:
                                    regen["_thought_guard"] = {}
                                regen["_thought_guard"].update(
                                    {
                                        "enabled": True,
                                        "action": "regenerated",
                                        "prev": guard_details,
                                    }
                                )
                                result = regen
                                status = "completed"
                            else:
                                try:
                                    result["_thought_guard"]["action"] = "regenerate_skipped"
                                    result["_thought_guard"]["regenerate_status"] = (
                                        str((regen or {}).get("status") or "") if isinstance(regen, dict) else type(regen).__name__
                                    )
                                except Exception:
                                    result["_thought_guard"]["action"] = "regenerate_skipped"

        # Normalize into ExecutorResult.
        status = str(result.get("status") or "error").strip().lower()
        answer = str(result.get("answer") or "")
        meta = dict(result)
        meta["answer_format"] = answer_format
        meta["conversation_url"] = conversation_url or ""

        # Rehydrate full answers when the underlying chatgptMCP tool output is truncated
        # but a full answer blob was persisted (answer_id).
        if status == "completed":
            expected_raw = meta.get("answer_chars")
            expected_chars = None
            if isinstance(expected_raw, int):
                expected_chars = int(expected_raw)
            elif isinstance(expected_raw, str) and expected_raw.isdigit():
                expected_chars = int(expected_raw)

            truncated = bool(meta.get("answer_truncated")) or (
                expected_chars is not None and expected_chars > max(0, len(answer) + 200)
            )
            answer_id = meta.get("answer_id")
            if truncated and bool(meta.get("answer_saved")) and isinstance(answer_id, str) and answer_id.strip():
                full = await self._rehydrate_answer_from_answer_id(
                    answer_id=answer_id,
                    expected_chars=expected_chars,
                    timeout_seconds=30.0,
                )
                if full is not None and len(full) > len(answer):
                    answer = full
                    meta["answer_rehydrated"] = True
                    meta["answer_rehydrated_chars"] = len(full)

        return ExecutorResult(status=status, answer=answer, answer_format=answer_format, meta=meta)

    async def _run_conversation_export(self, *, job_id: str, input: dict[str, Any], params: dict[str, Any]) -> ExecutorResult:
        raw_cid = _normalize_chatgpt_conversation_id(str(input.get("conversation_id") or "").strip() or None)
        conversation_url = str(input.get("conversation_url") or "").strip() or None
        if not conversation_url and raw_cid:
            conversation_url = _chatgpt_conversation_url_from_id(raw_cid)
        if not conversation_url:
            return ExecutorResult(
                status="error",
                answer="Missing input.conversation_id or input.conversation_url",
                meta={"error_type": "ValueError"},
            )
        if "/c/" not in str(conversation_url):
            return ExecutorResult(
                status="error",
                answer=f"conversation_url does not look like a ChatGPT thread: {conversation_url}",
                meta={"error_type": "ValueError"},
            )

        timeout_seconds = max(10, _coerce_int(params.get("timeout_seconds"), 60))
        allow_dom_fallback = bool(params.get("allow_dom_fallback", True))
        try:
            export_res = await asyncio.to_thread(
                self._client.call_tool,
                tool_name="chatgpt_web_conversation_export",
                tool_args={
                    "conversation_url": conversation_url,
                    "timeout_seconds": int(timeout_seconds),
                    "allow_dom_fallback": bool(allow_dom_fallback),
                },
                timeout_sec=float(timeout_seconds) + 30.0,
            )
        except Exception as exc:
            msg = f"conversation export failed: {type(exc).__name__}: {exc}"
            return ExecutorResult(status="error", answer=msg, meta={"error_type": type(exc).__name__, "error": msg})

        if not isinstance(export_res, dict):
            return ExecutorResult(
                status="error",
                answer=f"Unexpected conversation export result type: {type(export_res).__name__}",
                meta={"error_type": "TypeError"},
            )

        if bool(export_res.get("ok")) and str(export_res.get("status") or "").strip().lower() == "completed":
            export_res.setdefault("conversation_url", conversation_url)
            if raw_cid:
                export_res.setdefault("conversation_id", raw_cid)
            return ExecutorResult(status="completed", answer="", answer_format="text", meta=export_res)

        status = str(export_res.get("status") or "error").strip().lower() or "error"
        error_type = str(export_res.get("error_type") or "ConversationExportFailed").strip() or "ConversationExportFailed"
        error = str(export_res.get("error") or json.dumps(export_res, ensure_ascii=False)[:800]).strip()
        meta: dict[str, Any] = {"error_type": error_type, "error": error, "conversation_url": conversation_url}
        retry_after = export_res.get("retry_after_seconds")
        if isinstance(retry_after, (int, float)) and float(retry_after) > 0:
            meta["retry_after_seconds"] = float(retry_after)
            meta["not_before"] = _now() + float(retry_after)

        if status not in {"in_progress", "needs_followup", "cooldown", "blocked", "canceled"}:
            status = "error"
        return ExecutorResult(status=status, answer=error, meta=meta)
