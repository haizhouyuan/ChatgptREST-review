#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _ts() -> float:
    return time.time()


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _sha256_hex(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def _normalize_text(raw: str) -> str:
    return " ".join(str(raw or "").split()).strip()


def _truthy(v: str | None, default: bool = False) -> bool:
    val = str(v or "").strip().lower()
    if not val:
        return bool(default)
    return val in {"1", "true", "yes", "y", "on", "enabled", "enable"}


def _parse_csv(raw: str | None) -> list[str]:
    parts = [p.strip() for p in re.split(r"[\s,;]+", str(raw or "").strip()) if p and p.strip()]
    return [p for p in parts if p]


def _sanitize_header_token(raw: str | None, *, default: str, max_len: int = 64) -> str:
    candidate = str(raw or "").strip()
    if not candidate:
        candidate = default
    candidate = re.sub(r"[^A-Za-z0-9._~-]+", "-", candidate)
    candidate = candidate.strip(".-_~")
    if not candidate:
        candidate = default
    return candidate[: max(8, int(max_len))]


@dataclass
class TurnRecord:
    turn: int
    turn_id: str
    job_id: str
    question_hash: str
    status: str
    started_at: float
    updated_at: float
    answer: str | None = None
    conversation_url: str | None = None
    retry_count: int = 0
    parent_job_id: str | None = None
    idempotency_key: str | None = None
    blocked_reason: str | None = None


@dataclass
class SessionState:
    session_id: str
    created_at: float
    updated_at: float
    status: str
    last_job_id: str | None
    turn: int
    conversation_url: str | None
    total_turns: int
    max_turns: int
    preset: str
    answer_format: str
    agent_mode: bool
    timeout_seconds: int
    send_timeout_seconds: int
    wait_timeout_seconds: int
    max_wait_seconds: int
    min_chars: int
    poll_seconds: float
    max_retries: int
    retry_base_seconds: int
    retry_max_seconds: int
    turn_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    turns: list[dict[str, Any]] = field(default_factory=list)
    last_error: str | None = None
    last_error_at: float | None = None

    @staticmethod
    def from_dict(obj: dict[str, Any]) -> "SessionState":
        return SessionState(
            session_id=str(obj.get("session_id") or ""),
            created_at=float(obj.get("created_at") or _ts()),
            updated_at=float(obj.get("updated_at") or _ts()),
            status=str(obj.get("status") or "idle"),
            last_job_id=(
                str(obj.get("last_job_id")).strip()
                if str(obj.get("last_job_id") or "").strip()
                else None
            ),
            turn=int(obj.get("turn") or 0),
            conversation_url=(str(obj.get("conversation_url") or "").strip() or None),
            total_turns=int(obj.get("total_turns") or 0),
            max_turns=int(obj.get("max_turns") or 3),
            preset=str(obj.get("preset") or "auto"),
            answer_format=str(obj.get("answer_format") or "markdown"),
            agent_mode=bool(obj.get("agent_mode") if obj.get("agent_mode") is not None else True),
            timeout_seconds=int(obj.get("timeout_seconds") or 600),
            send_timeout_seconds=int(obj.get("send_timeout_seconds") or 180),
            wait_timeout_seconds=int(obj.get("wait_timeout_seconds") or 600),
            max_wait_seconds=int(obj.get("max_wait_seconds") or 1800),
            min_chars=int(obj.get("min_chars") or 800),
            poll_seconds=float(obj.get("poll_seconds") or 1.5),
            max_retries=int(obj.get("max_retries") or 2),
            retry_base_seconds=int(obj.get("retry_base_seconds") or 30),
            retry_max_seconds=int(obj.get("retry_max_seconds") or 180),
            turn_cache=dict(obj.get("turn_cache") or {}),
            turns=list(obj.get("turns") or []),
            last_error=(str(obj.get("last_error") or "") if obj.get("last_error") is not None else None),
            last_error_at=(float(obj.get("last_error_at")) if obj.get("last_error_at") is not None else None),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "last_job_id": self.last_job_id,
            "turn": self.turn,
            "conversation_url": self.conversation_url,
            "total_turns": self.total_turns,
            "max_turns": self.max_turns,
            "preset": self.preset,
            "answer_format": self.answer_format,
            "agent_mode": self.agent_mode,
            "timeout_seconds": self.timeout_seconds,
            "send_timeout_seconds": self.send_timeout_seconds,
            "wait_timeout_seconds": self.wait_timeout_seconds,
            "max_wait_seconds": self.max_wait_seconds,
            "min_chars": self.min_chars,
            "poll_seconds": self.poll_seconds,
            "max_retries": self.max_retries,
            "retry_base_seconds": self.retry_base_seconds,
            "retry_max_seconds": self.retry_max_seconds,
            "turn_cache": self.turn_cache,
            "turns": self.turns,
            "last_error": self.last_error,
            "last_error_at": self.last_error_at,
        }


class ChatGPTAgentV0:
    """
    V0 wrapper for multi-turn advisor mode.

    Interface:
      - 维持会话态：conversation_url/turn cache/状态转移。
      - 支持自动重试：blocked/cooldown/in_progress 待恢复。
      - 可回滚：在每轮操作前备份会话快照。
      - 可灰度：通过开关决定是否启用外壳层。
    """

    class Error(RuntimeError):
        pass

    ALLOWED_STATES = {"idle", "submitting", "waiting", "cooldown", "followup", "done", "failed"}
    STATE_TRANSITION = {
        "idle": {"submitting", "failed", "done"},
        "submitting": {"waiting", "failed"},
        "waiting": {"followup", "completed", "cooldown", "failed"},
        "cooldown": {"submitting", "failed", "idle"},
        "followup": {"submitting", "failed", "idle"},
        "done": {"submitting", "idle"},
        "failed": {"submitting", "idle"},
    }

    def __init__(
        self,
        *,
        base_url: str,
        api_token: str | None,
        state_root: Path,
        session_id: str | None = None,
        preset: str = "auto",
        max_turns: int = 3,
        max_retries: int = 2,
        retry_base_seconds: int = 30,
        retry_max_seconds: int = 180,
        timeout_seconds: int = 600,
        send_timeout_seconds: int = 180,
        wait_timeout_seconds: int = 600,
        max_wait_seconds: int = 1800,
        min_chars: int = 800,
        poll_seconds: float = 1.5,
        answer_format: str = "markdown",
        agent_mode: bool = True,
        dry_run: bool = False,
        auto_rollback: bool = True,
        client_name: str | None = None,
        client_instance: str | None = None,
        request_id_prefix: str | None = None,
        auto_client_name_repair: bool | None = None,
        client_name_repair_allowlist: list[str] | None = None,
        persist_client_name_repair: bool | None = None,
    ) -> None:
        self.base_url = str(base_url or "http://127.0.0.1:18711").rstrip("/")
        self.api_token = str(api_token or "").strip() or None
        self.state_root = state_root
        self.dry_run = bool(dry_run)
        self.auto_rollback = bool(auto_rollback)
        resolved_client_name = _sanitize_header_token(
            client_name
            or os.environ.get("CHATGPTREST_CLIENT_NAME")
            or "chatgpt_agent_shell_v0",
            default="chatgpt_agent_shell_v0",
            max_len=64,
        )
        self.client_name = resolved_client_name
        self.request_id_prefix = _sanitize_header_token(
            request_id_prefix
            or os.environ.get("CHATGPTREST_REQUEST_ID_PREFIX")
            or "chatgpt-agent-v0",
            default="chatgpt-agent-v0",
            max_len=48,
        )
        self.auto_client_name_repair = (
            _truthy(os.environ.get("CHATGPT_AGENT_V0_AUTO_CLIENT_NAME_REPAIR"), default=False)
            if auto_client_name_repair is None
            else bool(auto_client_name_repair)
        )
        self.persist_client_name_repair = (
            _truthy(os.environ.get("CHATGPT_AGENT_V0_PERSIST_CLIENT_NAME_REPAIR"), default=False)
            if persist_client_name_repair is None
            else bool(persist_client_name_repair)
        )
        allowlist_raw = (
            client_name_repair_allowlist
            if client_name_repair_allowlist is not None
            else _parse_csv(os.environ.get("CHATGPT_AGENT_V0_CLIENT_NAME_REPAIR_ALLOWLIST"))
        )
        self.client_name_repair_allowlist = {
            _sanitize_header_token(str(v), default="", max_len=64).lower()
            for v in list(allowlist_raw or [])
            if str(v).strip()
        }
        self.client_name_repair_allowlist.discard("")
        resolved_client_instance = str(
            client_instance
            or os.environ.get("CHATGPTREST_CLIENT_INSTANCE")
            or ""
        ).strip()
        self.max_turns = max(1, int(max_turns))
        self.max_retries = max(0, int(max_retries))
        self.retry_base_seconds = max(1, int(retry_base_seconds))
        self.retry_max_seconds = max(self.retry_base_seconds, int(retry_max_seconds))
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.send_timeout_seconds = max(1, int(send_timeout_seconds))
        self.wait_timeout_seconds = max(1, int(wait_timeout_seconds))
        self.max_wait_seconds = max(1, int(max_wait_seconds))
        self.min_chars = max(1, int(min_chars))
        self.poll_seconds = max(0.2, float(poll_seconds))
        self.preset = str(preset or "auto").strip() or "auto"
        self.answer_format = str(answer_format or "markdown").strip() or "markdown"
        self.agent_mode = bool(agent_mode)

        _ensure_dir(self.state_root)
        self._sessions_dir = self.state_root / "sessions"
        _ensure_dir(self._sessions_dir)

        sid = str(session_id or "").strip() or f"agnt_{uuid.uuid4().hex[:16]}"
        self.session_id = sid
        if not resolved_client_instance:
            resolved_client_instance = f"{self.session_id}"
        self.client_instance = _sanitize_header_token(
            resolved_client_instance,
            default=self.session_id,
            max_len=80,
        )
        self._session_path = self._sessions_dir / f"{self.session_id}.json"
        if not self._session_path.exists():
            self.state = SessionState(
                session_id=self.session_id,
                created_at=_ts(),
                updated_at=_ts(),
                status="idle",
                last_job_id=None,
                turn=0,
                conversation_url=None,
                total_turns=0,
                max_turns=self.max_turns,
                preset=self.preset,
                answer_format=self.answer_format,
                agent_mode=self.agent_mode,
                timeout_seconds=self.timeout_seconds,
                send_timeout_seconds=self.send_timeout_seconds,
                wait_timeout_seconds=self.wait_timeout_seconds,
                max_wait_seconds=self.max_wait_seconds,
                min_chars=self.min_chars,
                poll_seconds=self.poll_seconds,
                max_retries=self.max_retries,
                retry_base_seconds=self.retry_base_seconds,
                retry_max_seconds=self.retry_max_seconds,
            )
            self._save_state()
        else:
            self.state = self._load_state()
            self.state.max_turns = self.max_turns
            self.state.preset = self.preset or self.state.preset
            self.state.answer_format = self.answer_format or self.state.answer_format
            self.state.agent_mode = self.agent_mode if self.agent_mode is not None else self.state.agent_mode
            self.state.max_retries = self.max_retries
            self.state.retry_base_seconds = self.retry_base_seconds
            self.state.retry_max_seconds = self.retry_max_seconds
            self.state.timeout_seconds = self.timeout_seconds
            self.state.send_timeout_seconds = self.send_timeout_seconds
            self.state.wait_timeout_seconds = self.wait_timeout_seconds
            self.state.max_wait_seconds = self.max_wait_seconds
            self.state.min_chars = self.min_chars
            self.state.poll_seconds = self.poll_seconds
            self._save_state()

    # ---------- state persistence ----------
    def _snapshot_path(self) -> Path:
        return self._session_path.with_suffix(".bak")

    def _backup_state(self) -> None:
        if self._session_path.exists():
            shutil.copy2(self._session_path, self._snapshot_path())

    def _restore_state(self) -> None:
        sp = self._snapshot_path()
        if sp.exists():
            shutil.copy2(sp, self._session_path)
            self.state = self._load_state()

    def _load_state(self) -> SessionState:
        raw = json.loads(self._session_path.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(raw, dict):
            raise self.Error("invalid session state format")
        state = SessionState.from_dict(raw)
        # 兼容性：补齐新字段
        state.max_turns = max(1, int(state.max_turns or 1))
        state.total_turns = max(0, int(state.total_turns or 0))
        state.turn = max(0, int(state.turn or 0))
        if state.status not in self.ALLOWED_STATES:
            state.status = "idle"
        return state

    def _save_state(self) -> None:
        self.state.updated_at = _ts()
        self._session_path.write_text(
            json.dumps(self.state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _transition(self, new_state: str) -> None:
        if new_state not in self.ALLOWED_STATES:
            raise self.Error(f"invalid state: {new_state}")
        allowed = self.STATE_TRANSITION.get(self.state.status, set())
        if new_state not in allowed and self.state.status != new_state:
            # 对于恢复类操作或首次加载，允许有限修正
            # 其它异常转移记录到 failed，避免静默陷入循环。
            raise self.Error(
                f"invalid transition: {self.state.status} -> {new_state}"
            )
        self.state.status = new_state

    def _cache_key(self, question: str) -> str:
        norm = _normalize_text(question)
        return _sha256_hex(f"{self.session_id}|{self.state.preset}|{str(self.agent_mode)}|{norm}")[:24]

    def _emit_event(self, event: str, payload: dict[str, Any]) -> None:
        row = {
            "ts": _now_iso(),
            "event": str(event or "").strip() or "event",
            "session_id": self.session_id,
        }
        row.update(payload)
        try:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        except Exception:
            return

    def _idempotency_key(self, turn: int, question: str, parent_job_id: str | None = None) -> str:
        norm = _normalize_text(question)
        base = f"{self.session_id}|{turn}|{self.state.preset}|{norm}"
        if parent_job_id:
            base += f"|{parent_job_id}"
        return "agent-v0:" + _sha256_hex(base)

    def _http_request(
        self,
        *,
        method: str,
        url: str,
        json_body: dict[str, Any] | None = None,
        timeout_seconds: float,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        req_headers = {"Accept": "application/json"}
        if self.api_token:
            req_headers["Authorization"] = f"Bearer {self.api_token}"
        if extra_headers:
            req_headers.update(extra_headers)

        data = None
        if json_body is not None:
            data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            req_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url=url, data=data, headers=req_headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=float(timeout_seconds)) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                parsed = json.loads(raw) if raw.strip() else {}
                return int(getattr(resp, "status", 200)), parsed
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw.strip() else {"error": str(raw)}
            except Exception:
                parsed = {"error": raw}
            return int(exc.code), parsed
        except urllib.error.URLError as exc:
            raise self.Error(f"request failed: {type(exc).__name__}: {exc}") from exc

    def _post_submit(
        self,
        *,
        question: str,
        parent_job_id: str | None,
        turn_id: str,
        turn_no: int,
        input_override: dict[str, Any] | None = None,
        agent_mode: bool | None = None,
    ) -> dict[str, Any]:
        payload_input: dict[str, Any] = (
            dict(input_override)
            if input_override is not None
            else {"question": question}
        )
        if not payload_input:
            payload_input["question"] = question

        if self.state.conversation_url:
            payload_input.setdefault("conversation_url", self.state.conversation_url)
        elif parent_job_id:
            payload_input.setdefault("parent_job_id", parent_job_id)

        params_obj = {
            "preset": self.state.preset,
            "timeout_seconds": self.state.timeout_seconds,
            "send_timeout_seconds": self.state.send_timeout_seconds,
            "wait_timeout_seconds": self.state.wait_timeout_seconds,
            "max_wait_seconds": self.state.max_wait_seconds,
            "min_chars": self.state.min_chars,
            "answer_format": self.state.answer_format,
            "agent_mode": bool(self.state.agent_mode if agent_mode is None else agent_mode),
        }

        if self.dry_run:
            return {
                "dry_run": True,
                "job_id": f"dryrun-{turn_id}",
                "status": "in_progress",
                "phase": "send",
                "input": payload_input,
                "params": params_obj,
                "turn_id": turn_id,
            }

        current_client_name = _sanitize_header_token(
            self.client_name,
            default="chatgpt_agent_shell_v0",
            max_len=64,
        )
        request_id = f"{self.request_id_prefix}-{uuid.uuid4().hex[:12]}"

        def _build_payload(client_name_for_payload: str) -> dict[str, Any]:
            return {
                "kind": "chatgpt_web.ask",
                "input": payload_input,
                "params": params_obj,
                "client": {
                    "name": client_name_for_payload,
                    "session_id": self.session_id,
                    "turn": turn_no,
                },
            }

        def _build_headers(client_name_for_header: str) -> dict[str, str]:
            return {
                "Idempotency-Key": turn_id,
                "X-Request-ID": request_id,
                "X-Client-Name": client_name_for_header,
                "X-Client-Instance": self.client_instance,
            }

        payload = _build_payload(current_client_name)
        headers = _build_headers(current_client_name)
        url = f"{self.base_url}/v1/jobs"
        status, obj = self._http_request(
            method="POST",
            url=url,
            json_body=payload,
            timeout_seconds=20.0,
            extra_headers=headers,
        )
        repair_attempted = False
        repair_result = "not_attempted"
        repaired_client_name: str | None = None
        if status == 403 and self.auto_client_name_repair:
            retry_client_name = self._suggest_client_name_retry(obj=obj, current_client_name=current_client_name)
            if retry_client_name:
                repair_attempted = True
                repaired_client_name = retry_client_name
                status, obj = self._http_request(
                    method="POST",
                    url=url,
                    json_body=_build_payload(retry_client_name),
                    timeout_seconds=20.0,
                    extra_headers=_build_headers(retry_client_name),
                )
                if status < 400:
                    repair_result = "retry_succeeded"
                    if self.persist_client_name_repair:
                        self.client_name = retry_client_name
                else:
                    repair_result = f"retry_http_{status}"
            else:
                repair_result = "no_local_repair_candidate"
            self._emit_event(
                "submit_client_name_repair",
                {
                    "request_id": request_id,
                    "from_client_name": current_client_name,
                    "to_client_name": repaired_client_name,
                    "repair_attempted": repair_attempted,
                    "repair_result": repair_result,
                    "http_status": status,
                },
            )
        if status >= 400:
            raise self.Error(f"submit failed: HTTP {status}: {obj}")
        if not isinstance(obj, dict) or not obj.get("job_id"):
            raise self.Error(f"invalid submit response: {obj}")
        return obj

    def _suggest_client_name_retry(
        self,
        *,
        obj: Any,
        current_client_name: str | None,
    ) -> str | None:
        if not isinstance(obj, dict):
            return None
        detail = obj.get("detail")
        if not isinstance(detail, dict):
            return None
        err = str(detail.get("error") or "").strip().lower()
        if err != "client_not_allowed":
            return None
        allowed = detail.get("allowed_client_names")
        if not isinstance(allowed, list):
            return None
        local_allowlist = set(self.client_name_repair_allowlist)
        if not local_allowlist:
            return None
        current = str(current_client_name or "").strip().lower()
        for candidate_raw in allowed:
            candidate = _sanitize_header_token(str(candidate_raw or "").strip(), default="", max_len=64)
            if not candidate:
                continue
            candidate_lc = candidate.lower()
            if candidate_lc == current:
                continue
            if candidate_lc not in local_allowlist:
                continue
            return candidate
        return None

    def _wait_job(self, job_id: str) -> dict[str, Any]:
        if self.dry_run:
            return {
                "job_id": job_id,
                "status": "completed",
                "conversation_url": self.state.conversation_url,
                "retry_after_seconds": None,
                "reason_type": None,
                "reason": "dry-run",
            }

        deadline = _ts() + float(self.state.max_wait_seconds)
        last_obj: dict[str, Any] = {"job_id": job_id, "status": "in_progress"}
        while _ts() < deadline:
            status, obj = self._http_request(
                method="GET",
                url=f"{self.base_url}/v1/jobs/{urllib.parse.quote(str(job_id))}/wait",
                json_body=None,
                timeout_seconds=max(1.0, float(self.state.timeout_seconds)),
            )
            if status >= 400:
                # HTTP 503/4xx：等待可能短暂波动，按冷却重试。
                break
            if not isinstance(obj, dict):
                break
            last_obj = obj
            st = str(obj.get("status") or "").lower()
            if st in {"completed", "error", "canceled", "blocked", "needs_followup", "cooldown"}:
                return obj
            if st not in {"queued", "in_progress", "waiting", "done", "running", "retry"}:
                return obj
            time.sleep(max(0.2, float(self.poll_seconds)))
        return last_obj

    def _get_answer(self, job_id: str, *, max_chars: int = 16000) -> str:
        if self.dry_run:
            return ""
        offset = 0
        chunks: list[str] = []
        total = 0
        while True:
            status, obj = self._http_request(
                method="GET",
                url=f"{self.base_url}/v1/jobs/{urllib.parse.quote(str(job_id))}/answer?offset={offset}&max_chars=2000",
                json_body=None,
                timeout_seconds=20.0,
            )
            if status >= 400 or not isinstance(obj, dict):
                break
            chunk = str(obj.get("chunk") or "")
            if chunk:
                chunks.append(chunk)
                total += len(chunk.encode("utf-8", errors="replace"))
            if bool(obj.get("done")):
                break
            next_offset = obj.get("next_offset")
            if next_offset is None:
                break
            try:
                offset = int(next_offset)
            except Exception:
                break
            if total >= int(max_chars):
                break
        return "".join(chunks)

    def restore(self) -> dict[str, Any]:
        if not self._snapshot_path().exists():
            return {
                "ok": False,
                "reason": "no_snapshot",
                "session_id": self.session_id,
            }
        self._restore_state()
        return {
            "ok": True,
            "session_id": self.session_id,
            "status": self.state.status,
            "last_job_id": self.state.last_job_id,
            "conversation_url": self.state.conversation_url,
        }

    def legacy_ask(self, question: str) -> dict[str, Any]:
        """Fallback single-round path: no follow-up loop, no cache, no transition lock-in."""
        question = _normalize_text(question)
        if not question:
            return {
                "ok": False,
                "status": "failed",
                "error": "question is empty",
                "mode": "legacy",
            }

        submit = self._post_submit(
            question=question,
            parent_job_id=self.state.last_job_id,
            turn_id=self._idempotency_key(1, question, self.state.last_job_id),
            turn_no=1,
            input_override={"question": question},
            agent_mode=False,
        )
        job_id = str(submit.get("job_id") or "")
        if not job_id:
            return {
                "ok": False,
                "status": "failed",
                "error": "submit failed, no job_id",
                "mode": "legacy",
            }

        self.state.last_job_id = job_id
        waited = self._wait_job(job_id)
        status = str(waited.get("status") or "").strip().lower()
        if status != "completed":
            return {
                "ok": False,
                "session_id": self.session_id,
                "mode": "legacy",
                "status": status or "unknown",
                "job_id": job_id,
                "answer": None,
                "conversation_url": str(waited.get("conversation_url") or self.state.conversation_url or ""),
            }

        answer = self._get_answer(job_id)
        convo = str(waited.get("conversation_url") or "").strip() or self.state.conversation_url
        self.state.conversation_url = convo
        self._save_state()
        return {
            "ok": True,
            "session_id": self.session_id,
            "mode": "legacy",
            "status": "completed",
            "job_id": job_id,
            "answer": answer,
            "conversation_url": self.state.conversation_url,
        }

    def _backoff_seconds(self, retry_count: int) -> int:
        base = float(self.state.retry_base_seconds)
        cap = float(self.state.retry_max_seconds)
        raw = base * (2 ** max(0, retry_count))
        capped = min(cap, raw)
        jitter = random.uniform(0.85, 1.15)
        return int(round(max(1.0, capped * jitter)))

    def _advance_turn_cache(self, key: str, turn: TurnRecord) -> None:
        self.state.turn_cache[key] = {
            "turn": turn.turn,
            "job_id": turn.job_id,
            "status": turn.status,
            "conversation_url": turn.conversation_url,
            "answer": turn.answer,
            "updated_at": turn.updated_at,
        }
        # 保持 cache 适度：仅保留最新 200 条
        if len(self.state.turn_cache) > 200:
            ordered = sorted(
                ((v.get("updated_at") or 0.0, k) for k, v in self.state.turn_cache.items())
            )
            for _, old_key in ordered[: max(0, len(ordered) - 200)]:
                self.state.turn_cache.pop(old_key, None)

    def _record_turn(self, rec: TurnRecord) -> None:
        self.state.turns.append({
            "turn": rec.turn,
            "turn_id": rec.turn_id,
            "job_id": rec.job_id,
            "question_hash": rec.question_hash,
            "status": rec.status,
            "started_at": rec.started_at,
            "updated_at": rec.updated_at,
            "answer_chars": len(rec.answer or ""),
            "conversation_url": rec.conversation_url,
            "retry_count": rec.retry_count,
            "parent_job_id": rec.parent_job_id,
            "idempotency_key": rec.idempotency_key,
            "blocked_reason": rec.blocked_reason,
        })
        if len(self.state.turns) > 50:
            self.state.turns = self.state.turns[-50:]

    def ask(
        self,
        *,
        question: str,
        followup_prompt: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        question = _normalize_text(question)
        if not question:
            raise self.Error("question is empty")

        cache_key = self._cache_key(question)
        self.state.last_error = None
        self.state.last_error_at = None

        cached = self.state.turn_cache.get(cache_key)
        if not force and isinstance(cached, dict) and str(cached.get("status") or "") == "completed":
            return {
                "ok": True,
                "session_id": self.session_id,
                "mode": "cache_hit",
                "status": "completed",
                "job_id": cached.get("job_id"),
                "answer": cached.get("answer"),
                "conversation_url": cached.get("conversation_url"),
                "turn": int(cached.get("turn") or 0),
                "cache": True,
            }

        if self.state.status not in {"idle", "done", "failed", "followup", "cooldown"}:
            raise self.Error(f"session in invalid state {self.state.status}")

        self._backup_state()

        try:
            self._transition("submitting")
            self.state.total_turns += 1
            if self.state.total_turns > self.max_turns:
                self.state.status = "failed"
                self.state.last_error = "max_turns_exceeded"
                self.state.last_error_at = _ts()
                self._save_state()
                return {
                    "ok": False,
                    "session_id": self.session_id,
                    "status": "failed",
                    "error": self.state.last_error,
                }

            current_turn = self.state.total_turns
            parent_job_id = self.state.last_job_id
            follow_prompt = followup_prompt or "请继续完成刚才任务并给出完整可执行结果。"
            current_question = question
            retries = 0
            round_no = 1

            while True:
                turn_id = self._idempotency_key(current_turn, current_question, parent_job_id)
                submit = self._post_submit(question=current_question, parent_job_id=parent_job_id, turn_id=turn_id, turn_no=current_turn)
                job_id = str(submit.get("job_id") or "")
                if not job_id:
                    raise self.Error("submit response missing job_id")
                self.state.last_job_id = job_id
                self.state.status = "waiting"
                tr = TurnRecord(
                    turn=current_turn,
                    turn_id=turn_id,
                    job_id=job_id,
                    question_hash=cache_key,
                    status="waiting",
                    started_at=_ts(),
                    updated_at=_ts(),
                    parent_job_id=parent_job_id,
                    idempotency_key=turn_id,
                )
                self._save_state()

                waited = self._wait_job(job_id)
                status = str(waited.get("status") or "").strip().lower()
                tr.updated_at = _ts()
                tr.status = status

                if status == "completed":
                    answer = self._get_answer(job_id)
                    convo = str(waited.get("conversation_url") or "").strip() or self.state.conversation_url
                    tr.answer = answer
                    tr.conversation_url = convo or None
                    self.state.conversation_url = tr.conversation_url or self.state.conversation_url
                    self.state.status = "done"
                    self.state.turn = current_turn
                    self._record_turn(tr)
                    self._advance_turn_cache(cache_key, tr)
                    self._save_state()
                    return {
                        "ok": True,
                        "session_id": self.session_id,
                        "mode": "live",
                        "status": "completed",
                        "turn": current_turn,
                        "job_id": job_id,
                        "conversation_url": tr.conversation_url,
                        "answer": answer,
                        "retries": tr.retry_count,
                        "cache": False,
                        "round": round_no,
                    }

                if status in {"error", "canceled"}:
                    self.state.status = "failed"
                    self.state.last_error = f"turn_{round_no}_{status}"
                    self.state.last_error_at = _ts()
                    tr.blocked_reason = str(waited.get("reason") or waited.get("error") or status)
                    self._record_turn(tr)
                    self._save_state()
                    return {
                        "ok": False,
                        "session_id": self.session_id,
                        "status": status,
                        "turn": current_turn,
                        "job_id": job_id,
                        "error": tr.blocked_reason,
                        "round": round_no,
                    }

                if status in {"blocked", "cooldown", "in_progress"}:
                    # 重试：优先等待不超过 max_wait_seconds + 退避。
                    if status == "in_progress":
                        # in_progress 先给一个短窗口再次 wait，后续仍 in_progress 则进入 cooldown。
                        retry_after = 0
                    else:
                        retry_after_raw = waited.get("retry_after_seconds")
                        try:
                            retry_after = int(float(retry_after_raw)) if retry_after_raw is not None else self._backoff_seconds(retries)
                        except Exception:
                            retry_after = self._backoff_seconds(retries)
                    if retries >= self.max_retries:
                        self.state.status = "failed"
                        self.state.last_error = f"max_retries_exceeded:{status}"
                        self.state.last_error_at = _ts()
                        tr.blocked_reason = f"status={status}"
                        self._record_turn(tr)
                        self._save_state()
                        return {
                            "ok": False,
                            "session_id": self.session_id,
                            "status": status,
                            "turn": current_turn,
                            "job_id": job_id,
                            "error": "max_retries_exceeded",
                            "retry_count": retries,
                        }

                    retries += 1
                    tr.retry_count = retries
                    self.state.status = "cooldown"
                    tr.blocked_reason = f"status={status},retry_after={retry_after}"
                    self._record_turn(tr)
                    self._save_state()

                    wait_seconds = max(0, int(retry_after))
                    if wait_seconds > 0:
                        time.sleep(wait_seconds)
                    # 同一 job，继续 wait，不重发。
                    continue

                if status == "needs_followup":
                    self.state.status = "followup"
                    tr.blocked_reason = "needs_followup"
                    self._record_turn(tr)
                    if self.state.total_turns >= self.max_turns:
                        self.state.status = "failed"
                        self.state.last_error = "needs_followup_exhausted"
                        self.state.last_error_at = _ts()
                        self._save_state()
                        return {
                            "ok": False,
                            "session_id": self.session_id,
                            "status": "needs_followup",
                            "turn": current_turn,
                            "job_id": job_id,
                            "error": "needs_followup_exhausted",
                        }
                    # 自动多轮：基于同一会话继续 follow-up
                    self.state.total_turns += 1
                    current_turn = self.state.total_turns
                    current_question = follow_prompt
                    parent_job_id = job_id
                    self.state.last_error = "needs_followup_auto_round"
                    self.state.last_error_at = _ts()
                    round_no += 1
                    self._save_state()
                    continue

                # 未知状态：返回一次性失败，避免死循环
                self.state.status = "failed"
                self.state.last_error = f"unexpected_status:{status}"
                self.state.last_error_at = _ts()
                self._record_turn(tr)
                self._save_state()
                return {
                    "ok": False,
                    "session_id": self.session_id,
                    "status": status,
                    "turn": current_turn,
                    "job_id": job_id,
                    "error": self.state.last_error,
                }

        except Exception as exc:
            # 按回滚策略恢复到上一个快照
            if self.auto_rollback:
                try:
                    self._restore_state()
                except Exception:
                    pass
            self.state.last_error = f"runtime_error:{type(exc).__name__}:{exc}"
            self.state.last_error_at = _ts()
            self.state.status = "failed"
            self._save_state()
            return {
                "ok": False,
                "session_id": self.session_id,
                "status": "failed",
                "error": self.state.last_error,
            }

    def get_status(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.state.status,
            "conversation_url": self.state.conversation_url,
            "turn": self.state.turn,
            "total_turns": self.state.total_turns,
            "max_turns": self.state.max_turns,
            "last_job_id": self.state.last_job_id,
            "preset": self.state.preset,
            "agent_mode": self.state.agent_mode,
            "cache_size": len(self.state.turn_cache),
            "updated_at": self.state.updated_at,
            "last_error": self.state.last_error,
            "last_error_at": self.state.last_error_at,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ChatGPTAgent v0 外壳层（多轮顾问模式）")
    parser.add_argument("--base-url", default=os.environ.get("CHATGPTREST_BASE_URL", "http://127.0.0.1:18711"))
    parser.add_argument("--api-token", default=os.environ.get("CHATGPTREST_API_TOKEN", ""))
    parser.add_argument("--state-root", default=str(Path(__file__).resolve().parents[1] / "state" / "chatgpt_agent_shell_v0"))
    parser.add_argument("--client-name", default=os.environ.get("CHATGPTREST_CLIENT_NAME", "chatgpt_agent_shell_v0"))
    parser.add_argument("--client-instance", default=os.environ.get("CHATGPTREST_CLIENT_INSTANCE", ""))
    parser.add_argument("--request-id-prefix", default=os.environ.get("CHATGPTREST_REQUEST_ID_PREFIX", "chatgpt-agent-v0"))
    parser.add_argument("--auto-client-name-repair", action="store_true", help="启用 403 client_not_allowed 自动修复重试")
    parser.add_argument("--no-auto-client-name-repair", action="store_true", help="关闭 403 client_not_allowed 自动重试")
    parser.add_argument(
        "--client-name-repair-allowlist",
        default=os.environ.get("CHATGPT_AGENT_V0_CLIENT_NAME_REPAIR_ALLOWLIST", ""),
        help="自动修复允许切换到的 client name 列表，逗号分隔",
    )
    parser.add_argument("--persist-client-name-repair", action="store_true", help="自动修复成功后持久化覆盖默认 client name")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--preset", default="auto")
    parser.add_argument("--max-turns", type=int, default=3)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--retry-base-seconds", type=int, default=30)
    parser.add_argument("--retry-max-seconds", type=int, default=180)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--send-timeout-seconds", type=int, default=180)
    parser.add_argument("--wait-timeout-seconds", type=int, default=600)
    parser.add_argument("--max-wait-seconds", type=int, default=1800)
    parser.add_argument("--min-chars", type=int, default=800)
    parser.add_argument("--poll-seconds", type=float, default=1.5)
    parser.add_argument("--answer-format", default="markdown")
    parser.add_argument("--agent-mode", choices=["auto", "on", "off"], default="on")
    parser.add_argument("--question", default="", help="提交给顾问的一条用户提问")
    parser.add_argument("--followup-prompt", default="请继续完成刚才任务并给出完整结果。")
    parser.add_argument("--force", action="store_true", help="忽略同问复用缓存")
    parser.add_argument("--dry-run", action="store_true", help="仅模拟执行，不触发真实请求")
    parser.add_argument("--no-roll-back", action="store_true", help="失败时不回滚会话快照")
    parser.add_argument("--status", action="store_true", help="仅打印会话状态")
    parser.add_argument("--rollback", action="store_true", help="从上次成功前快照回滚会话")
    parser.add_argument("--json", action="store_true", help="强制 JSON 输出")
    args = parser.parse_args(argv)

    agent_mode = True
    if str(args.agent_mode).strip().lower() in {"off", "0", "false", "no"}:
        agent_mode = False
    if bool(args.auto_client_name_repair) and bool(args.no_auto_client_name_repair):
        print('{"ok":false,"error":"--auto-client-name-repair and --no-auto-client-name-repair are mutually exclusive"}')
        return 2
    auto_client_name_repair_opt: bool | None = None
    if bool(args.auto_client_name_repair):
        auto_client_name_repair_opt = True
    elif bool(args.no_auto_client_name_repair):
        auto_client_name_repair_opt = False
    repair_allowlist_opt = _parse_csv(str(args.client_name_repair_allowlist or "")) or None

    enabled = _truthy(os.environ.get("CHATGPT_AGENT_V0_ENABLED"), default=True)

    if not enabled and str(args.question).strip():
        # 灰度关闭时走传统单轮回退链路（不启用 advisor cache/状态机）
        shell = ChatGPTAgentV0(
            base_url=str(args.base_url),
            api_token=str(args.api_token or ""),
            state_root=Path(args.state_root),
            session_id=(str(args.session_id).strip() or None),
            preset=str(args.preset),
            max_turns=1,
            max_retries=int(args.max_retries),
            retry_base_seconds=int(args.retry_base_seconds),
            retry_max_seconds=int(args.retry_max_seconds),
            timeout_seconds=int(args.timeout_seconds),
            send_timeout_seconds=int(args.send_timeout_seconds),
            wait_timeout_seconds=int(args.wait_timeout_seconds),
            max_wait_seconds=int(args.max_wait_seconds),
            min_chars=int(args.min_chars),
            poll_seconds=float(args.poll_seconds),
            answer_format=str(args.answer_format),
            agent_mode=False,
            dry_run=bool(args.dry_run),
            auto_rollback=False,
            client_name=(str(args.client_name).strip() or None),
            client_instance=(str(args.client_instance).strip() or None),
            request_id_prefix=(str(args.request_id_prefix).strip() or None),
            auto_client_name_repair=auto_client_name_repair_opt,
            client_name_repair_allowlist=repair_allowlist_opt,
            persist_client_name_repair=bool(args.persist_client_name_repair),
        )
        result = shell.legacy_ask(str(args.question).strip())
        result["enabled"] = False
        result["ts"] = _now_iso()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if bool(result.get("ok")) else 1

    shell = ChatGPTAgentV0(
        base_url=str(args.base_url),
        api_token=str(args.api_token or ""),
        state_root=Path(args.state_root),
        session_id=(str(args.session_id).strip() or None),
        preset=str(args.preset),
        max_turns=int(args.max_turns),
        max_retries=int(args.max_retries),
        retry_base_seconds=int(args.retry_base_seconds),
        retry_max_seconds=int(args.retry_max_seconds),
        timeout_seconds=int(args.timeout_seconds),
        send_timeout_seconds=int(args.send_timeout_seconds),
        wait_timeout_seconds=int(args.wait_timeout_seconds),
        max_wait_seconds=int(args.max_wait_seconds),
        min_chars=int(args.min_chars),
        poll_seconds=float(args.poll_seconds),
        answer_format=str(args.answer_format),
        agent_mode=bool(agent_mode),
        dry_run=bool(args.dry_run),
        auto_rollback=not bool(args.no_roll_back),
        client_name=(str(args.client_name).strip() or None),
        client_instance=(str(args.client_instance).strip() or None),
        request_id_prefix=(str(args.request_id_prefix).strip() or None),
        auto_client_name_repair=auto_client_name_repair_opt,
        client_name_repair_allowlist=repair_allowlist_opt,
        persist_client_name_repair=bool(args.persist_client_name_repair),
    )

    if args.status:
        result = shell.get_status()
        result.update({"ok": True, "enabled": enabled, "session_id": shell.session_id})
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.rollback:
        shell._restore_state()
        result = shell.get_status()
        result.update({"ok": True, "enabled": enabled, "session_id": shell.session_id, "ts": _now_iso()})
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    question = str(args.question).strip()
    if not question:
        print('{"ok":false,"error":"--question is required"}')
        return 2

    result = shell.ask(
        question=question,
        followup_prompt=str(args.followup_prompt),
        force=bool(args.force),
    )
    result["enabled"] = True
    result["session_id"] = shell.session_id
    result["ts"] = _now_iso()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if bool(result.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
