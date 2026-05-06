"""Team Scorecard — aggregate team performance for learning.

Stores and queries team-level performance metrics across runs.
Uses the same SQLite database as EvoMapObserver for co-location.

Usage::

    store = TeamScorecardStore(db_path=":memory:")
    store.record_outcome(team_run_record)

    scores = store.rank_teams(repo="chatgptrest", task_type="code_review")
    best = scores[0] if scores else None
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field, asdict
from typing import Any

from .paths import resolve_evomap_db_path

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS team_scorecards (
    team_id     TEXT NOT NULL,
    repo        TEXT NOT NULL DEFAULT '',
    task_type   TEXT NOT NULL DEFAULT '',
    total_runs  INTEGER NOT NULL DEFAULT 0,
    successes   INTEGER NOT NULL DEFAULT 0,
    failures    INTEGER NOT NULL DEFAULT 0,
    total_quality  REAL NOT NULL DEFAULT 0.0,
    total_latency  REAL NOT NULL DEFAULT 0.0,
    total_input_tokens   INTEGER NOT NULL DEFAULT 0,
    total_output_tokens  INTEGER NOT NULL DEFAULT 0,
    total_cost_usd       REAL NOT NULL DEFAULT 0.0,
    team_spec_json TEXT NOT NULL DEFAULT '{}',
    last_run_at    TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT '',
    updated_at     TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (team_id, repo, task_type)
);

CREATE INDEX IF NOT EXISTS idx_scorecard_repo_task
    ON team_scorecards(repo, task_type);
"""


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now().isoformat()


@dataclass
class TeamScorecard:
    """Aggregated team performance metrics."""
    team_id: str = ""
    repo: str = ""
    task_type: str = ""
    total_runs: int = 0
    successes: int = 0
    failures: int = 0
    avg_quality: float = 0.0
    avg_latency_s: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    success_rate: float = 0.0
    composite_score: float = 0.0
    team_spec_json: str = "{}"
    last_run_at: str = ""

    def __post_init__(self):
        if self.total_runs > 0:
            self.success_rate = self.successes / self.total_runs
            self.avg_quality = self.avg_quality or 0.0
            # Composite: weighted combination of success rate and quality
            self.composite_score = 0.6 * self.success_rate + 0.4 * self.avg_quality


class TeamScorecardStore:
    """SQLite-backed store for team scorecard data.

    Thread-safe via per-thread connections.
    """

    def __init__(self, db_path: str = ""):
        self._db_path = db_path or resolve_evomap_db_path()
        self._local = threading.local()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    @property
    def db_path(self) -> str:
        return self._db_path

    def _init_db(self):
        conn = self._conn
        conn.executescript(_DDL)
        conn.commit()

    def record_outcome(self, run_record: Any) -> None:
        """Upsert scorecard with data from a TeamRunRecord.

        Increments counters and updates averages incrementally.
        """
        if run_record.team_spec is None:
            return

        team_id = run_record.team_spec.team_id
        repo = run_record.repo or ""
        task_type = run_record.task_type or ""
        now = _now_iso()

        conn = self._conn
        row = conn.execute(
            "SELECT * FROM team_scorecards WHERE team_id=? AND repo=? AND task_type=?",
            (team_id, repo, task_type),
        ).fetchone()

        if row is None:
            # Insert new
            conn.execute(
                "INSERT INTO team_scorecards "
                "(team_id, repo, task_type, total_runs, successes, failures, "
                " total_quality, total_latency, total_input_tokens, total_output_tokens, "
                " total_cost_usd, team_spec_json, last_run_at, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    team_id, repo, task_type,
                    1,
                    1 if run_record.result_ok else 0,
                    0 if run_record.result_ok else 1,
                    run_record.quality_score,
                    run_record.elapsed_seconds,
                    run_record.total_input_tokens,
                    run_record.total_output_tokens,
                    run_record.cost_usd,
                    json.dumps(run_record.team_spec.to_dict()),
                    now, now, now,
                ),
            )
        else:
            # Update existing
            total_runs = row["total_runs"] + 1
            successes = row["successes"] + (1 if run_record.result_ok else 0)
            failures = row["failures"] + (0 if run_record.result_ok else 1)
            total_quality = row["total_quality"] + run_record.quality_score
            total_latency = row["total_latency"] + run_record.elapsed_seconds

            conn.execute(
                "UPDATE team_scorecards SET "
                "total_runs=?, successes=?, failures=?, "
                "total_quality=?, total_latency=?, "
                "total_input_tokens=total_input_tokens+?, "
                "total_output_tokens=total_output_tokens+?, "
                "total_cost_usd=total_cost_usd+?, "
                "team_spec_json=?, last_run_at=?, updated_at=? "
                "WHERE team_id=? AND repo=? AND task_type=?",
                (
                    total_runs, successes, failures,
                    total_quality, total_latency,
                    run_record.total_input_tokens,
                    run_record.total_output_tokens,
                    run_record.cost_usd,
                    json.dumps(run_record.team_spec.to_dict()),
                    now, now,
                    team_id, repo, task_type,
                ),
            )

        conn.commit()

    def get_scorecard(
        self, team_id: str, repo: str = "", task_type: str = "",
    ) -> TeamScorecard | None:
        """Get scorecard for a specific team/repo/task combination."""
        row = self._conn.execute(
            "SELECT * FROM team_scorecards WHERE team_id=? AND repo=? AND task_type=?",
            (team_id, repo, task_type),
        ).fetchone()

        if row is None:
            return None

        return self._row_to_scorecard(row)

    def rank_teams(
        self, repo: str = "", task_type: str = "", limit: int = 10,
    ) -> list[TeamScorecard]:
        """Rank teams by composite score for a repo/task combination.

        Returns scorecards sorted by (success_rate * 0.6 + avg_quality * 0.4)
        descending.
        """
        rows = self._conn.execute(
            "SELECT *, "
            "  (CAST(successes AS REAL) / MAX(total_runs, 1)) AS success_rate, "
            "  (total_quality / MAX(total_runs, 1)) AS avg_quality "
            "FROM team_scorecards "
            "WHERE repo=? AND task_type=? AND total_runs > 0 "
            "ORDER BY "
            "  (0.6 * (CAST(successes AS REAL) / MAX(total_runs, 1)) "
            "   + 0.4 * (total_quality / MAX(total_runs, 1))) DESC "
            "LIMIT ?",
            (repo, task_type, limit),
        ).fetchall()

        return [self._row_to_scorecard(r) for r in rows]

    def list_all(self, limit: int = 50) -> list[TeamScorecard]:
        """List all scorecards."""
        rows = self._conn.execute(
            "SELECT * FROM team_scorecards ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_scorecard(r) for r in rows]

    def _row_to_scorecard(self, row: sqlite3.Row) -> TeamScorecard:
        total_runs = row["total_runs"]
        avg_q = row["total_quality"] / max(total_runs, 1)
        avg_l = row["total_latency"] / max(total_runs, 1)
        return TeamScorecard(
            team_id=row["team_id"],
            repo=row["repo"],
            task_type=row["task_type"],
            total_runs=total_runs,
            successes=row["successes"],
            failures=row["failures"],
            avg_quality=avg_q,
            avg_latency_s=avg_l,
            total_input_tokens=row["total_input_tokens"],
            total_output_tokens=row["total_output_tokens"],
            total_cost_usd=row["total_cost_usd"],
            team_spec_json=row["team_spec_json"],
            last_run_at=row["last_run_at"],
        )

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
