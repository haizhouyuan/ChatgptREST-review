from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class JobStatus(StrEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    NEEDS_FOLLOWUP = "needs_followup"
    COOLDOWN = "cooldown"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELED = "canceled"


TERMINAL_STATUSES: set[JobStatus] = {JobStatus.COMPLETED, JobStatus.ERROR, JobStatus.CANCELED}


@dataclass(frozen=True)
class TransitionResult:
    ok: bool
    error: str | None = None


def is_terminal(status: JobStatus | str) -> bool:
    try:
        st = JobStatus(str(status))
    except Exception:
        return False
    return st in TERMINAL_STATUSES


def can_transition(src: JobStatus, dst: JobStatus) -> TransitionResult:
    if src == dst:
        return TransitionResult(ok=True)

    if src in TERMINAL_STATUSES:
        return TransitionResult(ok=False, error=f"terminal status cannot transition: {src} -> {dst}")

    allowed: set[tuple[JobStatus, JobStatus]] = {
        (JobStatus.QUEUED, JobStatus.IN_PROGRESS),
        (JobStatus.QUEUED, JobStatus.CANCELED),
        (JobStatus.IN_PROGRESS, JobStatus.COMPLETED),
        (JobStatus.IN_PROGRESS, JobStatus.ERROR),
        (JobStatus.IN_PROGRESS, JobStatus.NEEDS_FOLLOWUP),
        (JobStatus.IN_PROGRESS, JobStatus.COOLDOWN),
        (JobStatus.IN_PROGRESS, JobStatus.BLOCKED),
        (JobStatus.IN_PROGRESS, JobStatus.CANCELED),
        (JobStatus.NEEDS_FOLLOWUP, JobStatus.QUEUED),
        (JobStatus.COOLDOWN, JobStatus.QUEUED),
        (JobStatus.BLOCKED, JobStatus.QUEUED),
    }
    if (src, dst) in allowed:
        return TransitionResult(ok=True)
    return TransitionResult(ok=False, error=f"invalid transition: {src} -> {dst}")

