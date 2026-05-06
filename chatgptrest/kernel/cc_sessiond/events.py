import sqlite3
import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import AsyncIterator, Optional
import asyncio


class EventType(str, Enum):
    STARTED = "started"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    COST_UPDATE = "cost_update"
    STATUS_CHANGE = "status_change"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    MESSAGE = "message"


@dataclass
class Event:
    id: int
    session_id: str
    event_type: EventType
    timestamp: datetime
    data: dict

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
        }


class EventLog:
    """Structured event log for session debugging & analytics."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
        self._subscribers: dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    def _init_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                data TEXT
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)
        """)
        self.conn.commit()

    def emit(self, session_id: str, event_type: EventType, data: Optional[dict] = None):
        """Emit a synchronous event (for use in sync context)."""
        now = datetime.now()
        
        self.conn.execute(
            """
            INSERT INTO events (session_id, event_type, timestamp, data)
            VALUES (?, ?, ?, ?)
            """,
            (
                session_id,
                event_type.value,
                now.isoformat(),
                json.dumps(data or {}),
            ),
        )
        self.conn.commit()
        
        # Notify subscribers
        self._notify_subscribers(session_id, event_type, data or {})

    async def emit_async(self, session_id: str, event_type: EventType, data: Optional[dict] = None):
        """Emit an async event with subscriber notification."""
        now = datetime.now()
        
        self.conn.execute(
            """
            INSERT INTO events (session_id, event_type, timestamp, data)
            VALUES (?, ?, ?, ?)
            """,
            (
                session_id,
                event_type.value,
                now.isoformat(),
                json.dumps(data or {}),
            ),
        )
        self.conn.commit()
        
        # Notify subscribers
        await self._notify_subscribers_async(session_id, event_type, data or {})

    def query(
        self,
        session_id: str,
        after_id: int = 0,
        limit: int = 100,
    ) -> list[Event]:
        """Query events for a session."""
        rows = self.conn.execute(
            """
            SELECT * FROM events 
            WHERE session_id = ? AND id > ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (session_id, after_id, limit),
        ).fetchall()
        
        return [self._row_to_event(row) for row in rows]

    def get_latest_id(self, session_id: str) -> int:
        """Get the latest event ID for a session."""
        row = self.conn.execute(
            "SELECT MAX(id) as max_id FROM events WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row["max_id"] or 0

    def subscribe(self, session_id: str) -> asyncio.Queue:
        """Subscribe to events for a session."""
        if session_id not in self._subscribers:
            self._subscribers[session_id] = asyncio.Queue()
        return self._subscribers[session_id]

    def unsubscribe(self, session_id: str):
        """Unsubscribe from events for a session."""
        if session_id in self._subscribers:
            del self._subscribers[session_id]

    def _notify_subscribers(self, session_id: str, event_type: EventType, data: dict):
        """Notify synchronous subscribers."""
        if session_id in self._subscribers:
            try:
                self._subscribers[session_id].put_nowait(
                    {"type": event_type.value, "data": data}
                )
            except asyncio.QueueFull:
                pass

    async def _notify_subscribers_async(self, session_id: str, event_type: EventType, data: dict):
        """Notify async subscribers."""
        async with self._lock:
            if session_id in self._subscribers:
                try:
                    self._subscribers[session_id].put_nowait(
                        {"type": event_type.value, "data": data}
                    )
                except asyncio.QueueFull:
                    pass

    def _row_to_event(self, row: sqlite3.Row) -> Event:
        return Event(
            id=row["id"],
            session_id=row["session_id"],
            event_type=EventType(row["event_type"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            data=json.loads(row["data"] or "{}"),
        )

    def close(self):
        self.conn.close()
