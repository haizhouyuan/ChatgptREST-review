"""Subsystem protocol and runner — the structural backbone for daemon decomposition.

Each subsystem is a self-contained unit that:
- Has its own tick interval
- Maintains independent circuit breaker state
- Is wrapped in try/except for fault isolation
- Tracks its own last-run timestamp
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger("maint.subsystem")


# ---------------------------------------------------------------------------
# Context passed to each subsystem tick
# ---------------------------------------------------------------------------


@dataclass
class TickContext:
    """Shared context passed to every subsystem on each tick."""

    now: float
    args: Any  # argparse.Namespace
    conn: Any  # sqlite3.Connection
    mcp_client: Any | None = None
    state: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Observation — subsystem output
# ---------------------------------------------------------------------------


@dataclass
class Observation:
    """A discrete observation emitted by a subsystem during a tick."""

    subsystem: str
    kind: str  # e.g. "incident", "action", "metric", "alert"
    data: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Subsystem protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Subsystem(Protocol):
    """Protocol for daemon subsystems."""

    name: str
    interval_seconds: float

    def tick(self, ctx: TickContext) -> list[Observation]:
        """Execute one iteration. Returns observations for the coordinator."""
        ...


# ---------------------------------------------------------------------------
# Circuit breaker state
# ---------------------------------------------------------------------------


@dataclass
class CircuitState:
    """Per-subsystem circuit breaker state."""

    last_ok_ts: float = 0.0
    last_error_ts: float = 0.0
    failure_count: int = 0
    disabled_until: float = 0.0
    last_error_msg: str = ""

    _BACKOFF = [0, 30, 120, 600]  # seconds: immediate, 30s, 2min, 10min

    def record_ok(self, now: float) -> None:
        self.last_ok_ts = now
        self.failure_count = 0
        self.disabled_until = 0.0

    def record_error(self, now: float, error: str) -> None:
        self.last_error_ts = now
        self.failure_count += 1
        self.last_error_msg = error[:500]
        idx = min(self.failure_count, len(self._BACKOFF) - 1)
        self.disabled_until = now + self._BACKOFF[idx]

    def is_open(self, now: float) -> bool:
        """True if the circuit breaker is open (subsystem disabled)."""
        return now < self.disabled_until


# ---------------------------------------------------------------------------
# Subsystem runner
# ---------------------------------------------------------------------------


class SubsystemRunner:
    """Wraps subsystems with scheduling, circuit breakers, and fault isolation."""

    def __init__(self, subsystems: list[Subsystem]) -> None:
        self._subsystems = subsystems
        self._last_run: dict[str, float] = {s.name: 0.0 for s in subsystems}
        self._circuits: dict[str, CircuitState] = {s.name: CircuitState() for s in subsystems}

    def tick_all(self, ctx: TickContext) -> list[Observation]:
        """Run all due subsystems and collect observations."""
        observations: list[Observation] = []
        for sub in self._subsystems:
            name = sub.name
            circuit = self._circuits[name]

            # Skip if circuit breaker is open
            if circuit.is_open(ctx.now):
                continue

            # Skip if not yet due
            elapsed = ctx.now - self._last_run[name]
            if elapsed < sub.interval_seconds:
                continue

            # Execute with fault isolation
            self._last_run[name] = ctx.now
            try:
                obs = sub.tick(ctx)
                circuit.record_ok(ctx.now)
                if obs:
                    observations.extend(obs)
            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                circuit.record_error(ctx.now, error_msg)
                logger.error(
                    "[%s] tick error (fail #%d, disabled %.0fs): %s",
                    name,
                    circuit.failure_count,
                    max(0, circuit.disabled_until - ctx.now),
                    error_msg,
                    exc_info=True,
                )
                observations.append(
                    Observation(
                        subsystem=name,
                        kind="error",
                        data={"error_type": type(exc).__name__, "error": error_msg},
                    )
                )

        return observations

    def status(self) -> dict[str, dict[str, Any]]:
        """Return status of all subsystems for monitoring."""
        out: dict[str, dict[str, Any]] = {}
        now = time.time()
        for sub in self._subsystems:
            name = sub.name
            circuit = self._circuits[name]
            out[name] = {
                "interval_seconds": sub.interval_seconds,
                "last_run_ts": self._last_run[name],
                "circuit_ok": not circuit.is_open(now),
                "failure_count": circuit.failure_count,
                "last_error": circuit.last_error_msg or None,
            }
        return out
