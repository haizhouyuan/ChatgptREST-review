from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any


def hash_request(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8", errors="replace")).hexdigest()


@dataclass(frozen=True)
class IdempotencyOutcome:
    created: bool
    job_id: str


class IdempotencyCollision(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        idempotency_key: str,
        existing_job_id: str,
        existing_hash: str,
        request_hash: str,
    ) -> None:
        super().__init__(message)
        self.idempotency_key = str(idempotency_key)
        self.existing_job_id = str(existing_job_id)
        self.existing_hash = str(existing_hash)
        self.request_hash = str(request_hash)


def begin(
    conn: sqlite3.Connection,
    *,
    idempotency_key: str,
    request_hash: str,
    job_id: str,
) -> IdempotencyOutcome:
    # Atomic path: try insert first; on collision, read existing row.
    # This keeps begin() safe even when the caller doesn't wrap it in a transaction.
    try:
        conn.execute(
            "INSERT INTO idempotency(idempotency_key, request_hash, job_id, created_at) VALUES (?,?,?,?)",
            (idempotency_key, request_hash, job_id, time.time()),
        )
        return IdempotencyOutcome(created=True, job_id=job_id)
    except sqlite3.IntegrityError:
        row = conn.execute(
            "SELECT request_hash, job_id FROM idempotency WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if row is None:
            raise RuntimeError("idempotency record missing after IntegrityError")
        existing_hash = str(row[0] or "")
        existing_job_id = str(row[1] or "")
        if existing_hash != request_hash:
            msg = (
                "idempotency_key collision: same key used with different request payload "
                f"(existing_job_id={existing_job_id}, existing_hash={existing_hash[:12]}, new_hash={request_hash[:12]}). "
                "Common cause: request fields differ only by representation (e.g. file_paths absolute vs relative)."
            )
            raise IdempotencyCollision(
                msg,
                idempotency_key=idempotency_key,
                existing_job_id=existing_job_id,
                existing_hash=existing_hash,
                request_hash=request_hash,
            )
        return IdempotencyOutcome(created=False, job_id=existing_job_id)
