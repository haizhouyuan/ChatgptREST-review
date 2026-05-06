#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chatgptrest.core import artifacts
from chatgptrest.core.db import connect, insert_event


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


@dataclass(frozen=True)
class RepairResult:
    job_id: str
    repaired: bool
    reason: str


def _resolve_answer_src_path(src: str, *, chatgptmcp_root: Path | None) -> Path | None:
    raw = str(src or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if p.is_absolute():
        return p
    if chatgptmcp_root is None:
        return None
    return (chatgptmcp_root / p).resolve()


def _repair_job_if_needed(
    *,
    db_path: Path,
    artifacts_dir: Path,
    job_id: str,
    chatgptmcp_root: Path | None,
    dry_run: bool,
) -> RepairResult:
    job_dir = artifacts_dir / "jobs" / job_id
    run_meta_path = job_dir / "run_meta.json"
    run_meta = _read_json(run_meta_path) if run_meta_path.exists() else None
    if not run_meta:
        return RepairResult(job_id=job_id, repaired=False, reason="missing run_meta.json")

    if not bool(run_meta.get("answer_truncated")):
        return RepairResult(job_id=job_id, repaired=False, reason="not truncated")

    if not bool(run_meta.get("answer_saved")):
        return RepairResult(job_id=job_id, repaired=False, reason="no saved answer_id")

    answer_id = str(run_meta.get("answer_id") or "").strip()
    answer_src = str(run_meta.get("answer_path") or "").strip()
    if not answer_id or not answer_src:
        return RepairResult(job_id=job_id, repaired=False, reason="missing answer_id/answer_path")

    src_path = _resolve_answer_src_path(answer_src, chatgptmcp_root=chatgptmcp_root)
    if src_path is None or not src_path.exists():
        return RepairResult(job_id=job_id, repaired=False, reason=f"missing src answer file: {answer_src}")

    full_answer = src_path.read_text(encoding="utf-8", errors="replace")

    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT answer_path, answer_format, answer_sha256, answer_chars, status FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return RepairResult(job_id=job_id, repaired=False, reason="job missing in DB")
        if str(row["status"] or "") != "completed":
            return RepairResult(job_id=job_id, repaired=False, reason=f"job status is {row['status']}")

        answer_format = str(row["answer_format"] or "text")
        computed_meta, _ = artifacts.compute_answer_meta(job_id=job_id, answer=full_answer, answer_format=answer_format)
        if str(row["answer_sha256"] or "") == computed_meta.answer_sha256 and int(row["answer_chars"] or 0) == int(
            computed_meta.answer_chars
        ):
            return RepairResult(job_id=job_id, repaired=False, reason="already full")

        if dry_run:
            return RepairResult(job_id=job_id, repaired=True, reason="dry_run")

        # Preserve the current on-disk answer as answer_raw.* once (best-effort).
        try:
            cur_path = str(row["answer_path"] or "")
            if cur_path:
                cur_abs = artifacts.resolve_artifact_path(artifacts_dir, cur_path)
                raw_rel = artifacts.answer_raw_rel_path(job_id=job_id, answer_format=answer_format)
                raw_abs = artifacts.resolve_artifact_path(artifacts_dir, raw_rel)
                if cur_abs.exists() and not raw_abs.exists():
                    artifacts.write_answer_raw(
                        artifacts_dir,
                        job_id,
                        answer=cur_abs.read_text(encoding="utf-8", errors="replace"),
                        answer_format=answer_format,
                    )
        except Exception:
            pass

        repaired_meta = artifacts.write_answer(
            artifacts_dir,
            job_id,
            answer=full_answer,
            answer_format=answer_format,
        )
        payload = {
            "answer_id": answer_id,
            "src_answer_path": answer_src,
            "repaired_answer_path": repaired_meta.answer_path,
            "repaired_answer_sha256": repaired_meta.answer_sha256,
            "repaired_answer_chars": repaired_meta.answer_chars,
        }
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE jobs SET answer_sha256 = ?, answer_chars = ?, answer_format = ?, updated_at = ? WHERE job_id = ?",
            (repaired_meta.answer_sha256, repaired_meta.answer_chars, repaired_meta.answer_format, time.time(), job_id),
        )
        insert_event(conn, job_id=job_id, type="answer_repaired_from_answer_id", payload=payload)
        conn.commit()
        artifacts.append_event(artifacts_dir, job_id, type="answer_repaired_from_answer_id", payload=payload)

        result_path = job_dir / "result.json"
        result_obj = _read_json(result_path) if result_path.exists() else None
        if isinstance(result_obj, dict):
            result_obj["path"] = repaired_meta.answer_path
            result_obj["answer_sha256"] = repaired_meta.answer_sha256
            result_obj["answer_chars"] = repaired_meta.answer_chars
            result_obj["answer_format"] = repaired_meta.answer_format
            _atomic_write_json(result_path, result_obj)

    return RepairResult(job_id=job_id, repaired=True, reason="repaired")


def main() -> int:
    ap = argparse.ArgumentParser(description="Repair completed jobs whose answer.md is truncated but a full answer_id exists.")
    ap.add_argument("--db-path", type=Path, default=Path(os.environ.get("CHATGPTREST_DB_PATH") or "state/jobdb.sqlite3"))
    ap.add_argument("--artifacts-dir", type=Path, default=Path(os.environ.get("CHATGPTREST_ARTIFACTS_DIR") or "artifacts"))
    ap.add_argument(
        "--chatgptmcp-root",
        type=Path,
        default=Path(os.environ.get("CHATGPTMCP_ROOT") or "/vol1/1000/projects/chatgptMCP/artifacts"),
    )
    ap.add_argument("--job-id", action="append", default=[], help="Repair a specific job_id (repeatable).")
    ap.add_argument("--all", action="store_true", help="Scan DB for completed jobs and repair as needed.")
    ap.add_argument("--dry-run", action="store_true", help="Print what would be repaired without writing.")
    args = ap.parse_args()

    db_path = Path(args.db_path)
    artifacts_dir = Path(args.artifacts_dir)
    chatgptmcp_root = Path(args.chatgptmcp_root) if args.chatgptmcp_root else None

    job_ids: list[str] = [str(x).strip() for x in (args.job_id or []) if str(x).strip()]
    if not job_ids and not bool(args.all):
        ap.error("pass --job-id or --all")

    if bool(args.all):
        with connect(db_path) as conn:
            rows = conn.execute("SELECT job_id FROM jobs WHERE status = 'completed' ORDER BY created_at ASC").fetchall()
        job_ids = [str(r["job_id"]) for r in rows]

    repaired = 0
    for jid in job_ids:
        res = _repair_job_if_needed(
            db_path=db_path,
            artifacts_dir=artifacts_dir,
            job_id=jid,
            chatgptmcp_root=chatgptmcp_root,
            dry_run=bool(args.dry_run),
        )
        if res.repaired and res.reason != "dry_run":
            repaired += 1
        print(f"{jid}\t{('REPAIRED' if res.repaired else 'SKIP')}\t{res.reason}")

    print(f"repaired_total\t{repaired}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
