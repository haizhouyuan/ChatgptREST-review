from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context

from chatgpt_web_mcp.locks import _flock_exclusive


# Process-scoped recovery marker. Safe under the repo's single live driver assumption;
# overlapping writers against the same idempotency DB are unsupported and may look like stale ownership changes.
_RUNTIME_INSTANCE_ID = f"{os.getpid()}:{time.time_ns()}:{uuid.uuid4().hex}"


def _idempotency_runtime_instance_id() -> str:
    return _RUNTIME_INSTANCE_ID


def _result_has_full_answer_reference(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    if str(result.get("answer_id") or "").strip() or str(result.get("answer_path") or "").strip():
        return True
    if bool(result.get("answer_truncated")) and isinstance(result.get("answer_chars"), int):
        return int(result.get("answer_chars") or 0) > 0
    return False


@dataclass(frozen=True)
class _IdempotencyContext:
    namespace: str
    tool: str
    key: str
    request_hash: str


def _idempotency_db_path() -> Path:
    raw = (os.environ.get("MCP_IDEMPOTENCY_DB") or ".run/mcp_idempotency.sqlite3").strip()
    return Path(raw).expanduser()


def _idempotency_lock_file(db_path: Path) -> Path:
    raw = (os.environ.get("MCP_IDEMPOTENCY_LOCK_FILE") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(str(db_path) + ".lock")


def _idempotency_namespace(ctx: Context | None) -> str:
    if ctx is not None:
        try:
            sess = ctx.session
            params = sess.client_params if sess is not None else None
            info = getattr(params, "clientInfo", None) if params is not None else None
            name = getattr(info, "name", None) if info is not None else None
            if isinstance(name, str) and name.strip():
                return name.strip()
        except Exception:
            pass
        try:
            client_id = getattr(ctx, "client_id", None)
            if isinstance(client_id, str) and client_id.strip():
                return client_id.strip()
        except Exception:
            pass
    return "unknown"


def _normalize_idempotency_key(value: str) -> str:
    key = (value or "").strip()
    if not key:
        raise ValueError("idempotency_key is required")
    if len(key) > 256:
        raise ValueError("idempotency_key too long (>256 chars)")
    return key


def _chatgptrest_blank_in_progress_same_runtime_reclaim_allowed(*, tool: str, key: str) -> bool:
    tool_name = str(tool or "").strip().lower()
    normalized_key = str(key or "").strip()
    if not normalized_key.startswith("chatgptrest:"):
        return False
    return tool_name.startswith("gemini_web_")


def _blank_in_progress_retry_seconds(*, tool: str, key: str, configured_seconds: float) -> float:
    seconds = max(15.0, float(configured_seconds))
    if _chatgptrest_blank_in_progress_same_runtime_reclaim_allowed(tool=tool, key=key):
        return min(seconds, 30.0)
    return seconds


def _run_id(*, tool: str, idempotency_key: str | None = None) -> str:
    """
    Correlation id for logs/artifacts.
    - For send-type tools: prefer a stable id derived from idempotency_key.
    - For non-idempotent tools: generate a best-effort unique run id.
    """
    if isinstance(idempotency_key, str) and idempotency_key.strip():
        return f"{tool}:{_normalize_idempotency_key(idempotency_key)}"
    ts = time.strftime("%Y%m%d_%H%M%S")
    return f"{tool}:{ts}:{uuid.uuid4().hex[:12]}"


def _hash_request(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8", errors="replace")).hexdigest()


def _idempotency_db_init(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS idempotency (
          namespace TEXT NOT NULL,
          tool TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL,
          sent INTEGER NOT NULL DEFAULT 0,
          conversation_url TEXT,
          result_json TEXT,
          error TEXT,
          runtime_instance_id TEXT,
          PRIMARY KEY (namespace, tool, idempotency_key)
        )
        """
    )
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(idempotency)")}
    if "runtime_instance_id" not in columns:
        conn.execute("ALTER TABLE idempotency ADD COLUMN runtime_instance_id TEXT")


def _idempotency_db_row_to_record(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        namespace,
        tool,
        key,
        request_hash,
        status,
        created_at,
        updated_at,
        sent,
        conversation_url,
        result_json,
        error,
        runtime_instance_id,
    ) = row
    record: dict[str, Any] = {
        "namespace": namespace,
        "tool": tool,
        "idempotency_key": key,
        "request_hash": request_hash,
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
        "sent": bool(int(sent or 0)),
        "conversation_url": conversation_url,
        "error": error,
        "runtime_instance_id": runtime_instance_id,
    }
    if isinstance(result_json, str) and result_json.strip():
        try:
            parsed = json.loads(result_json)
            if isinstance(parsed, dict):
                record["result"] = parsed
        except Exception:
            record["result_json_invalid"] = True
    return record


async def _idempotency_begin(ctx: _IdempotencyContext) -> tuple[bool, dict[str, Any] | None]:
    """
    Returns (should_execute, existing_record).
    If a record exists, should_execute=False and existing_record is returned.
    """
    db_path = _idempotency_db_path()
    lock_file = _idempotency_lock_file(db_path)

    async with _flock_exclusive(lock_file):
        def _op() -> tuple[bool, dict[str, Any] | None]:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_path), timeout=30.0)
            try:
                _idempotency_db_init(conn)
                row = conn.execute(
                    """
                    SELECT namespace, tool, idempotency_key, request_hash, status, created_at, updated_at,
                           sent, conversation_url, result_json, error, runtime_instance_id
                    FROM idempotency
                    WHERE namespace = ? AND tool = ? AND idempotency_key = ?
                    """,
                    (ctx.namespace, ctx.tool, ctx.key),
                ).fetchone()
                if row is not None:
                    record = _idempotency_db_row_to_record(row)
                    existing_hash = str(record.get("request_hash") or "")
                    status = str(record.get("status") or "").strip().lower()
                    sent = bool(record.get("sent"))
                    if existing_hash != ctx.request_hash:
                        # Safe override for ChatgptREST internal keys when we know no prompt was sent.
                        #
                        # This can happen across deployments when the effective request payload changes
                        # (e.g. upload handling) but the upstream idempotency_key stays stable.
                        key = str(ctx.key or "")
                        if (not sent) and status in {"error", "blocked", "cooldown"} and key.startswith("chatgptrest:"):
                            now = time.time()
                            conn.execute(
                                """
                                UPDATE idempotency
                                SET request_hash = ?,
                                    status = ?,
                                    created_at = ?,
                                    updated_at = ?,
                                    sent = 0,
                                    conversation_url = NULL,
                                    result_json = NULL,
                                    error = NULL,
                                    runtime_instance_id = ?
                                WHERE namespace = ? AND tool = ? AND idempotency_key = ?
                                """,
                                (ctx.request_hash, "in_progress", now, now, _idempotency_runtime_instance_id(), ctx.namespace, ctx.tool, ctx.key),
                            )
                            conn.commit()
                            record["collision_overridden"] = True
                            record["previous_request_hash"] = existing_hash
                            record["request_hash"] = ctx.request_hash
                            record["status"] = "in_progress"
                            record["sent"] = False
                            record["conversation_url"] = None
                            record.pop("result", None)
                            record.pop("result_json_invalid", None)
                            return True, record
                        # Migration-safe behavior: if a prompt was already sent under this idempotency key,
                        # do not wedge resume/wait behind a hash mismatch.
                        if sent:
                            record["request_hash_mismatch"] = True
                            record["previous_request_hash"] = existing_hash
                            record["requested_request_hash"] = ctx.request_hash
                            return False, record
                            return False, record
                        raise RuntimeError(
                            "idempotency_key collision: same key used with different request payload. "
                            "Use a new idempotency_key."
                        )
                    # If a previous attempt failed BEFORE sending (sent=false), allow an immediate retry.
                    #
                    # Note: we may still have a result_json stored (an error envelope). That's fine: the
                    # critical invariant is that we did not send a prompt, so it is safe to retry.
                    updated_at = record.get("updated_at")
                    try:
                        updated_at_ts = float(updated_at) if updated_at is not None else 0.0
                    except Exception:
                        updated_at_ts = 0.0
                    if (not sent) and status in {"error", "blocked", "cooldown"}:
                        now = time.time()
                        conn.execute(
                            """
                            UPDATE idempotency
                            SET status = ?, error = NULL, updated_at = ?, runtime_instance_id = ?
                            WHERE namespace = ? AND tool = ? AND idempotency_key = ?
                            """,
                            ("in_progress", now, _idempotency_runtime_instance_id(), ctx.namespace, ctx.tool, ctx.key),
                        )
                        conn.commit()
                        return True, record

                    # If the driver crashed/restarted before it could write *any* send-side signal,
                    # an idempotency record can get stuck in a "blank" in_progress state
                    # (sent=false, no conversation_url, no result_json, no error). That state is not a
                    # meaningful replay target; after a short grace window we should let the same job retry.
                    if (not sent) and status == "in_progress":
                        has_conversation_url = bool(str(record.get("conversation_url") or "").strip())
                        has_result = isinstance(record.get("result"), dict) or bool(record.get("result_json_invalid"))
                        has_error = bool(str(record.get("error") or "").strip())
                        record_runtime_instance_id = str(record.get("runtime_instance_id") or "").strip()
                        current_runtime_instance_id = _idempotency_runtime_instance_id()
                        runtime_mismatch = (
                            not record_runtime_instance_id
                            or record_runtime_instance_id != current_runtime_instance_id
                        )
                        now = time.time()
                        is_blank_unsent = not has_conversation_url and not has_result and not has_error
                        if is_blank_unsent:
                            if str(ctx.key or "").startswith("chatgptrest:"):
                                raw_retry = (os.environ.get("CHATGPT_IDEMPOTENCY_EMPTY_IN_PROGRESS_RETRY_SECONDS") or "").strip()
                                try:
                                    empty_retry_seconds = float(raw_retry) if raw_retry else 120.0
                                except Exception:
                                    empty_retry_seconds = 120.0
                                empty_retry_seconds = _blank_in_progress_retry_seconds(
                                    tool=ctx.tool,
                                    key=ctx.key,
                                    configured_seconds=empty_retry_seconds,
                                )
                                age = (now - updated_at_ts) if updated_at_ts else empty_retry_seconds + 1.0
                                can_reclaim_same_runtime = _chatgptrest_blank_in_progress_same_runtime_reclaim_allowed(
                                    tool=ctx.tool,
                                    key=ctx.key,
                                )
                                should_reset_blank_in_progress = age >= empty_retry_seconds and (
                                    runtime_mismatch or can_reclaim_same_runtime
                                )
                                if should_reset_blank_in_progress:
                                    conn.execute(
                                        """
                                        UPDATE idempotency
                                        SET status = ?, error = NULL, updated_at = ?, runtime_instance_id = ?
                                        WHERE namespace = ? AND tool = ? AND idempotency_key = ?
                                        """,
                                        ("in_progress", now, current_runtime_instance_id, ctx.namespace, ctx.tool, ctx.key),
                                    )
                                    conn.commit()
                                    record["empty_in_progress_reset"] = True
                                    record["empty_in_progress_age_seconds"] = round(float(age), 3)
                                    record["empty_in_progress_threshold_seconds"] = float(empty_retry_seconds)
                                    record["previous_runtime_instance_id"] = record_runtime_instance_id or None
                                    record["runtime_instance_id"] = current_runtime_instance_id
                                    if not runtime_mismatch and can_reclaim_same_runtime:
                                        record["empty_in_progress_same_runtime_reset"] = True
                                    return True, record
                            return False, record

                        # Broader stale recovery for in-progress records that already captured partial state.
                        raw = (os.environ.get("CHATGPT_IDEMPOTENCY_IN_PROGRESS_STALE_SECONDS") or "").strip()
                        try:
                            stale_seconds = float(raw) if raw else 600.0
                        except Exception:
                            stale_seconds = 600.0
                        stale_seconds = max(30.0, stale_seconds)
                        age = (now - updated_at_ts) if updated_at_ts else stale_seconds + 1.0
                        if age >= stale_seconds:
                            conn.execute(
                                """
                                UPDATE idempotency
                                SET status = ?, error = NULL, updated_at = ?, runtime_instance_id = ?
                                WHERE namespace = ? AND tool = ? AND idempotency_key = ?
                                """,
                                ("in_progress", now, current_runtime_instance_id, ctx.namespace, ctx.tool, ctx.key),
                            )
                            conn.commit()
                            record["stale_in_progress_reset"] = True
                            record["stale_in_progress_age_seconds"] = round(float(age), 3)
                            record["stale_in_progress_threshold_seconds"] = float(stale_seconds)
                            record["runtime_instance_id"] = current_runtime_instance_id
                            return True, record

                    return False, record

                now = time.time()
                conn.execute(
                    """
                    INSERT INTO idempotency(namespace, tool, idempotency_key, request_hash, status, created_at, updated_at, sent, runtime_instance_id)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (ctx.namespace, ctx.tool, ctx.key, ctx.request_hash, "in_progress", now, now, 0, _idempotency_runtime_instance_id()),
                )
                conn.commit()
                return True, None
            finally:
                conn.close()

        return await asyncio.to_thread(_op)


async def _idempotency_update(
    ctx: _IdempotencyContext,
    *,
    status: str | None = None,
    sent: bool | None = None,
    conversation_url: str | None = None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    db_path = _idempotency_db_path()
    lock_file = _idempotency_lock_file(db_path)

    async with _flock_exclusive(lock_file):
        def _op() -> None:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_path), timeout=30.0)
            try:
                _idempotency_db_init(conn)
                row = conn.execute(
                    """
                    SELECT status, sent, conversation_url, result_json
                    FROM idempotency
                    WHERE namespace = ? AND tool = ? AND idempotency_key = ?
                    """,
                    (ctx.namespace, ctx.tool, ctx.key),
                ).fetchone()
                existing_status = str(row[0] or "") if row else ""
                existing_sent = bool(int(row[1] or 0)) if row else False
                existing_url = str(row[2] or "") if row else ""
                existing_result: dict[str, Any] | None = None
                if row and isinstance(row[3], str) and row[3].strip():
                    try:
                        parsed = json.loads(row[3])
                        if isinstance(parsed, dict):
                            existing_result = parsed
                    except Exception:
                        existing_result = None

                desired_status = status
                desired_sent = sent
                desired_url = conversation_url
                desired_result = result

                # Monotonic invariants: once sent/URL are known, don't regress them.
                if existing_sent and desired_sent is False:
                    desired_sent = None
                if desired_status is not None:
                    if existing_status.strip().lower() == "completed" and str(desired_status).strip().lower() != "completed":
                        desired_status = None

                if desired_url is not None:
                    new_url = str(desired_url or "").strip()
                    old_url = str(existing_url or "").strip()
                    if not new_url:
                        desired_url = None
                    elif "/c/" in old_url:
                        if "/c/" in new_url and new_url == old_url:
                            desired_url = new_url
                        else:
                            desired_url = None
                    elif "/c/" in new_url:
                        desired_url = new_url
                    elif not old_url:
                        desired_url = new_url
                    else:
                        desired_url = None

                if desired_result is not None and isinstance(desired_result, dict) and existing_result is not None:
                    existing_answer = str(existing_result.get("answer") or "").strip()
                    new_answer = str(desired_result.get("answer") or "").strip()
                    if existing_answer and (not new_answer or len(new_answer) < len(existing_answer)):
                        # Allow replacing a stored full answer with a shorter preview, as long as the
                        # new result points to a persisted full answer blob.
                        if _result_has_full_answer_reference(desired_result):
                            desired_result.setdefault("answer_chars", len(existing_answer))
                        else:
                            merged = dict(desired_result)
                            merged["answer"] = existing_answer
                            if existing_result.get("answer_format") and not merged.get("answer_format"):
                                merged["answer_format"] = existing_result.get("answer_format")
                            desired_result = merged

                sets: list[str] = ["updated_at = ?"]
                params: list[Any] = [time.time()]
                if desired_status is not None:
                    sets.append("status = ?")
                    params.append(desired_status)
                if desired_sent is not None:
                    sets.append("sent = ?")
                    params.append(1 if desired_sent else 0)
                if desired_url is not None:
                    sets.append("conversation_url = ?")
                    params.append(str(desired_url))
                if desired_result is not None:
                    sets.append("result_json = ?")
                    params.append(json.dumps(desired_result, ensure_ascii=False))
                if error is not None:
                    sets.append("error = ?")
                    params.append(str(error))

                params.extend([ctx.namespace, ctx.tool, ctx.key])
                conn.execute(
                    f"UPDATE idempotency SET {', '.join(sets)} WHERE namespace = ? AND tool = ? AND idempotency_key = ?",
                    tuple(params),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_op)


async def _idempotency_lookup(
    *,
    namespace: str,
    tool: str,
    idempotency_key: str,
) -> dict[str, Any] | None:
    db_path = _idempotency_db_path()
    lock_file = _idempotency_lock_file(db_path)

    async with _flock_exclusive(lock_file):
        def _op() -> dict[str, Any] | None:
            if not db_path.exists():
                return None
            conn = sqlite3.connect(str(db_path), timeout=30.0)
            try:
                _idempotency_db_init(conn)
                row = conn.execute(
                    """
                    SELECT namespace, tool, idempotency_key, request_hash, status, created_at, updated_at,
                           sent, conversation_url, result_json, error, runtime_instance_id
                    FROM idempotency
                    WHERE namespace = ? AND tool = ? AND idempotency_key = ?
                    """,
                    (namespace, tool, idempotency_key),
                ).fetchone()
                if row is None:
                    return None
                return _idempotency_db_row_to_record(row)
            finally:
                conn.close()

        return await asyncio.to_thread(_op)
