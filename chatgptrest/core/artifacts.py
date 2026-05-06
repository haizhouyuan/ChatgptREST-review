from __future__ import annotations

import codecs
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chatgptrest.core.state_machine import JobStatus

try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


@dataclass(frozen=True)
class AnswerMeta:
    answer_path: str
    answer_sha256: str
    answer_chars: int
    answer_format: str


@dataclass(frozen=True)
class ConversationExportMeta:
    conversation_export_path: str
    conversation_export_sha256: str
    conversation_export_chars: int
    conversation_export_format: str


def job_dir(artifacts_dir: Path, job_id: str) -> Path:
    return artifacts_dir / "jobs" / job_id


def normalize_answer_format(answer_format: str | None) -> tuple[str, str]:
    fmt = str(answer_format or "text").strip().lower()
    normalized = "markdown" if fmt == "markdown" else "text"
    ext = "md" if normalized == "markdown" else "txt"
    return normalized, ext


def answer_rel_path(*, job_id: str, answer_format: str | None) -> str:
    _, ext = normalize_answer_format(answer_format)
    return (Path("jobs") / job_id / f"answer.{ext}").as_posix()


def answer_raw_rel_path(*, job_id: str, answer_format: str | None) -> str:
    _, ext = normalize_answer_format(answer_format)
    return (Path("jobs") / job_id / f"answer_raw.{ext}").as_posix()


def conversation_export_rel_path(*, job_id: str) -> str:
    return (Path("jobs") / job_id / "conversation.json").as_posix()


def compute_answer_meta(
    *,
    job_id: str,
    answer: str,
    answer_format: str | None,
) -> tuple[AnswerMeta, str]:
    normalized, _ = normalize_answer_format(answer_format)
    rel_path = answer_rel_path(job_id=job_id, answer_format=answer_format)
    text = answer if answer.endswith("\n") else answer + "\n"
    sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    return (
        AnswerMeta(
            answer_path=rel_path,
            answer_sha256=sha,
            answer_chars=len(text),
            answer_format=normalized,
        ),
        text,
    )


def resolve_artifact_path(artifacts_dir: Path, path: str) -> Path:
    if not path:
        raise ValueError("path is empty")
    p = Path(str(path))
    root = artifacts_dir.resolve()
    if p.is_absolute():
        resolved = p.resolve()
    else:
        resolved = (artifacts_dir / p).resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError("refusing to resolve path outside artifacts_dir")
    return resolved


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _atomic_write_json(path: Path, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    _atomic_write_text(path, text + "\n")


def write_request(artifacts_dir: Path, job_id: str, payload: dict[str, Any]) -> None:
    d = job_dir(artifacts_dir, job_id)
    _atomic_write_json(d / "request.json", payload)


def append_event(artifacts_dir: Path, job_id: str, *, type: str, payload: Any | None) -> None:
    d = job_dir(artifacts_dir, job_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "events.jsonl"
    line = json.dumps(
        {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "type": type,
            "payload": payload,
        },
        ensure_ascii=False,
    )
    with path.open("a", encoding="utf-8") as f:
        if fcntl is not None:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            except Exception:
                pass
        f.write(line + "\n")
        try:
            f.flush()
        except Exception:
            pass
        if fcntl is not None:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass


def write_answer(
    artifacts_dir: Path,
    job_id: str,
    *,
    answer: str,
    answer_format: str = "text",
) -> AnswerMeta:
    meta, text = compute_answer_meta(job_id=job_id, answer=answer, answer_format=answer_format)
    abs_path = resolve_artifact_path(artifacts_dir, meta.answer_path)
    _atomic_write_text(abs_path, text)
    return meta


def write_answer_raw(
    artifacts_dir: Path,
    job_id: str,
    *,
    answer: str,
    answer_format: str = "text",
) -> AnswerMeta:
    normalized, _ = normalize_answer_format(answer_format)
    rel_path = answer_raw_rel_path(job_id=job_id, answer_format=answer_format)
    text = answer if answer.endswith("\n") else answer + "\n"
    sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    abs_path = resolve_artifact_path(artifacts_dir, rel_path)
    _atomic_write_text(abs_path, text)
    return AnswerMeta(
        answer_path=rel_path,
        answer_sha256=sha,
        answer_chars=len(text),
        answer_format=normalized,
    )


def _copy_utf8_text_file_with_meta(*, src: Path, dst: Path) -> tuple[str, int]:
    if not src.exists():
        raise FileNotFoundError(str(src))
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + f".tmp.{os.getpid()}")

    sha = hashlib.sha256()
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    chars = 0
    last_byte: int | None = None

    with src.open("rb") as r, tmp.open("wb") as w:
        while True:
            chunk = r.read(65_536)
            if not chunk:
                break
            sha.update(chunk)
            w.write(chunk)
            last_byte = chunk[-1]
            chars += len(decoder.decode(chunk))

        chars += len(decoder.decode(b"", final=True))

        if last_byte != 0x0A:  # '\n'
            sha.update(b"\n")
            w.write(b"\n")
            chars += 1

    tmp.replace(dst)
    return sha.hexdigest(), int(chars)


def write_conversation_export_from_file(
    artifacts_dir: Path,
    job_id: str,
    *,
    src_path: Path,
) -> ConversationExportMeta:
    rel_path = conversation_export_rel_path(job_id=job_id)
    abs_path = resolve_artifact_path(artifacts_dir, rel_path)
    sha, chars = _copy_utf8_text_file_with_meta(src=Path(src_path), dst=abs_path)
    return ConversationExportMeta(
        conversation_export_path=rel_path,
        conversation_export_sha256=sha,
        conversation_export_chars=chars,
        conversation_export_format="json",
    )


def write_answer_staged(
    artifacts_dir: Path,
    job_id: str,
    *,
    lease_token: str,
    answer: str,
    answer_format: str = "text",
) -> tuple[AnswerMeta, Path]:
    if not lease_token:
        raise ValueError("lease_token is empty")
    meta, text = compute_answer_meta(job_id=job_id, answer=answer, answer_format=answer_format)
    canonical = resolve_artifact_path(artifacts_dir, meta.answer_path)
    stage_path = Path(str(canonical) + f".staging.{lease_token}")
    _atomic_write_text(stage_path, text)
    return meta, stage_path


def write_result(artifacts_dir: Path, job_id: str, payload: dict[str, Any]) -> None:
    d = job_dir(artifacts_dir, job_id)
    _atomic_write_json(d / "result.json", payload)


def write_result_staged(
    artifacts_dir: Path,
    job_id: str,
    *,
    lease_token: str,
    payload: dict[str, Any],
) -> Path:
    if not lease_token:
        raise ValueError("lease_token is empty")
    d = job_dir(artifacts_dir, job_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"result.json.staging.{lease_token}"
    _atomic_write_json(path, payload)
    return path


def write_run_meta(artifacts_dir: Path, job_id: str, payload: dict[str, Any]) -> None:
    d = job_dir(artifacts_dir, job_id)
    _atomic_write_json(d / "run_meta.json", payload)


def reconcile_job_artifacts(*, artifacts_dir: Path, job: Any) -> None:
    job_id = str(getattr(job, "job_id", "")).strip()
    if not job_id:
        return
    try:
        status = getattr(job, "status")
        st = status if isinstance(status, JobStatus) else JobStatus(str(status))
    except Exception:
        return

    if st == JobStatus.COMPLETED:
        answer_path = getattr(job, "answer_path", None)
        if answer_path:
            try:
                canonical = resolve_artifact_path(artifacts_dir, str(answer_path))
                if not canonical.exists():
                    token = getattr(job, "lease_token", None)
                    if token:
                        stage = Path(str(canonical) + f".staging.{token}")
                        if stage.exists():
                            stage.replace(canonical)
            except Exception:
                pass

    if st not in {
        JobStatus.COMPLETED,
        JobStatus.ERROR,
        JobStatus.CANCELED,
        JobStatus.BLOCKED,
        JobStatus.COOLDOWN,
        JobStatus.NEEDS_FOLLOWUP,
    }:
        return

    d = job_dir(artifacts_dir, job_id)
    result_path = d / "result.json"
    if result_path.exists():
        return

    payload: dict[str, Any]
    if st == JobStatus.COMPLETED:
        payload = {
            "ok": True,
            "job_id": job_id,
            "status": st.value,
            "phase": getattr(job, "phase", None),
            "conversation_url": getattr(job, "conversation_url", None),
            "conversation_id": getattr(job, "conversation_id", None),
            "path": getattr(job, "answer_path", None),
            "answer_sha256": getattr(job, "answer_sha256", None),
            "answer_chars": getattr(job, "answer_chars", None),
            "answer_format": getattr(job, "answer_format", None),
        }
    elif st == JobStatus.CANCELED:
        payload = {
            "ok": False,
            "job_id": job_id,
            "status": st.value,
            "phase": getattr(job, "phase", None),
            "conversation_url": getattr(job, "conversation_url", None),
            "conversation_id": getattr(job, "conversation_id", None),
            "canceled": True,
            "reason": getattr(job, "last_error", None),
        }
    elif st in {JobStatus.BLOCKED, JobStatus.COOLDOWN, JobStatus.NEEDS_FOLLOWUP}:
        payload = {
            "ok": False,
            "job_id": job_id,
            "status": st.value,
            "phase": getattr(job, "phase", None),
            "conversation_url": getattr(job, "conversation_url", None),
            "conversation_id": getattr(job, "conversation_id", None),
            "retryable": True,
            "not_before": getattr(job, "not_before", None),
            "error_type": getattr(job, "last_error_type", None),
            "error": getattr(job, "last_error", None),
        }
    else:
        payload = {
            "ok": False,
            "job_id": job_id,
            "status": st.value,
            "phase": getattr(job, "phase", None),
            "conversation_url": getattr(job, "conversation_url", None),
            "conversation_id": getattr(job, "conversation_id", None),
            "error_type": getattr(job, "last_error_type", None),
            "error": getattr(job, "last_error", None),
        }

    try:
        write_result(artifacts_dir, job_id, payload)
    except Exception:
        return


def read_text_preview(*, artifacts_dir: Path, path: str | None, max_chars: int) -> str:
    if not path:
        return ""
    abs_path = resolve_artifact_path(artifacts_dir, path)
    if not abs_path.exists():
        return ""
    text = abs_path.read_text(encoding="utf-8", errors="replace")
    return text[: max(0, int(max_chars))]


def read_text_chunk(
    *,
    artifacts_dir: Path,
    path: str,
    offset: int,
    max_chars: int,
) -> tuple[str, int | None, bool]:
    abs_path = resolve_artifact_path(artifacts_dir, path)
    content = abs_path.read_text(encoding="utf-8", errors="replace")
    total = len(content)
    start = max(0, int(offset))
    size = max(1, min(20000, int(max_chars)))
    chunk = content[start : start + size]
    next_offset = start + len(chunk)
    done = next_offset >= total
    return chunk, (None if done else next_offset), done


def read_utf8_chunk_by_bytes(
    *,
    artifacts_dir: Path,
    path: str,
    offset: int,
    max_bytes: int,
) -> tuple[str, int | None, bool, int]:
    abs_path = resolve_artifact_path(artifacts_dir, path)
    size = abs_path.stat().st_size
    start = max(0, min(int(offset), size))
    max_bytes = max(1, min(20000, int(max_bytes)))

    with abs_path.open("rb") as f:
        if start < size:
            f.seek(start)
            prefix = f.read(4)
            shift = 0
            while shift < len(prefix) and (prefix[shift] & 0xC0) == 0x80:
                shift += 1
            start = min(size, start + shift)

        if start >= size:
            return "", None, True, start

        f.seek(start)
        data = f.read(max_bytes)

    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    text = decoder.decode(data, final=False)
    consumed = len(text.encode("utf-8", errors="strict"))
    next_offset = start + consumed
    done = next_offset >= size
    return text, (None if done else next_offset), done, start
