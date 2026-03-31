import sqlite3
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class SessionState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SessionRecord:
    session_id: str
    prompt: str
    state: SessionState
    created_at: datetime
    updated_at: datetime
    options: dict = field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    total_cost: Optional[float] = None
    total_tokens: Optional[int] = None
    parent_session_id: Optional[str] = None
    continue_mode: Optional[str] = None
    backend: Optional[str] = None
    backend_run_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class SessionRegistry:
    """Durable session storage using SQLite."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                prompt TEXT NOT NULL,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                options TEXT,
                result TEXT,
                error TEXT,
                total_cost REAL,
                total_tokens INTEGER,
                parent_session_id TEXT,
                continue_mode TEXT,
                backend TEXT,
                backend_run_id TEXT
            )
        """)
        self._migrate()
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_state ON sessions(state)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_parent ON sessions(parent_session_id)
        """)
        self.conn.commit()

    def _migrate(self):
        """Migrate existing database to new schema."""
        try:
            self.conn.execute("SELECT parent_session_id FROM sessions LIMIT 1")
        except sqlite3.OperationalError:
            self.conn.execute("ALTER TABLE sessions ADD COLUMN parent_session_id TEXT")
        try:
            self.conn.execute("SELECT continue_mode FROM sessions LIMIT 1")
        except sqlite3.OperationalError:
            self.conn.execute("ALTER TABLE sessions ADD COLUMN continue_mode TEXT")
        try:
            self.conn.execute("SELECT backend FROM sessions LIMIT 1")
        except sqlite3.OperationalError:
            self.conn.execute("ALTER TABLE sessions ADD COLUMN backend TEXT")
        try:
            self.conn.execute("SELECT backend_run_id FROM sessions LIMIT 1")
        except sqlite3.OperationalError:
            self.conn.execute("ALTER TABLE sessions ADD COLUMN backend_run_id TEXT")

    def create(
        self,
        prompt: str,
        options: Optional[dict] = None,
        parent_session_id: Optional[str] = None,
        continue_mode: Optional[str] = None,
    ) -> SessionRecord:
        session_id = uuid.uuid4().hex[:12]
        now = datetime.now()
        
        self.conn.execute(
            """
            INSERT INTO sessions (session_id, prompt, state, created_at, updated_at, options, parent_session_id, continue_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                prompt,
                SessionState.PENDING.value,
                now.isoformat(),
                now.isoformat(),
                json.dumps(options or {}),
                parent_session_id,
                continue_mode,
            ),
        )
        self.conn.commit()
        
        return SessionRecord(
            session_id=session_id,
            prompt=prompt,
            state=SessionState.PENDING,
            created_at=now,
            updated_at=now,
            options=options or {},
            parent_session_id=parent_session_id,
            continue_mode=continue_mode,
        )

    def get(self, session_id: str) -> Optional[SessionRecord]:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        
        if not row:
            return None
        
        return self._row_to_record(row)

    def update_state(
        self,
        session_id: str,
        state: SessionState,
        result: Optional[dict] = None,
        error: Optional[str] = None,
        total_cost: Optional[float] = None,
        total_tokens: Optional[int] = None,
    ):
        now = datetime.now().isoformat()
        
        self.conn.execute(
            """
            UPDATE sessions 
            SET state = ?, updated_at = ?, result = ?, error = ?, total_cost = ?, total_tokens = ?
            WHERE session_id = ?
            """,
            (
                state.value,
                now,
                json.dumps(result) if result else None,
                error,
                total_cost,
                total_tokens,
                session_id,
            ),
        )
        self.conn.commit()

    def update_backend(
        self,
        session_id: str,
        backend: str,
        backend_run_id: str,
    ):
        now = datetime.now().isoformat()
        
        self.conn.execute(
            """
            UPDATE sessions 
            SET backend = ?, backend_run_id = ?, updated_at = ?
            WHERE session_id = ?
            """,
            (
                backend,
                backend_run_id,
                now,
                session_id,
            ),
        )
        self.conn.commit()

    def list(
        self,
        state: Optional[SessionState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SessionRecord]:
        query = "SELECT * FROM sessions"
        params = []
        
        if state:
            query += " WHERE state = ?"
            params.append(state.value)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_record(row) for row in rows]

    def delete(self, session_id: str):
        self.conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self.conn.commit()

    def _row_to_record(self, row: sqlite3.Row) -> SessionRecord:
        return SessionRecord(
            session_id=row["session_id"],
            prompt=row["prompt"],
            state=SessionState(row["state"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            options=json.loads(row["options"] or "{}"),
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
            total_cost=row["total_cost"],
            total_tokens=row["total_tokens"],
            parent_session_id=row["parent_session_id"],
            continue_mode=row["continue_mode"],
            backend=row["backend"],
            backend_run_id=row["backend_run_id"],
        )

    def close(self):
        self.conn.close()
