"""P8: Compliance & Governance — audit trails and retention policies.

Exports structured audit trails from runtime_events for SOC2/GDPR review.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from runtime_allocator.runtime_state import RuntimeStateStore


class AuditTrailExporter:
    """Export runtime events as structured audit trails."""

    def __init__(self, store: RuntimeStateStore):
        self.store = store

    def export_range(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        company_id: str = "",
        output_path: Optional[Path] = None,
    ) -> Path:
        """Export events in a date range to NDJSON audit file.

        Args:
            start: ISO datetime string (default 30 days ago).
            end: ISO datetime string (default now).
            company_id: Filter by tenant.
            output_path: Destination file path.
        """
        if end is None:
            end = datetime.now().isoformat()
        if start is None:
            start = (datetime.now() - timedelta(days=30)).isoformat()
        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path.home() / ".paperclip" / f"audit_trail_{ts}.ndjson"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with self.store._connect() as conn:
            params = [start, end]
            where = "created_at >= ? AND created_at <= ?"
            if company_id:
                where += " AND company_id = ?"
                params.append(company_id)

            rows = conn.execute(
                f"SELECT * FROM runtime_events WHERE {where} ORDER BY id",
                params,
            ).fetchall()

        with open(output_path, "w", encoding="utf-8") as f:
            for row in rows:
                record = {
                    "event_id": row["id"],
                    "company_id": row.get("company_id", ""),
                    "provider_id": row["provider_id"],
                    "task_class": row["task_class"],
                    "status": row["status"],
                    "error_class": row["error_class"],
                    "latency_ms": row["latency_ms"],
                    "tokens_actual": row["tokens_actual"],
                    "fallback_from": row["fallback_from"],
                    "fallback_to": row["fallback_to"],
                    "timestamp": row["created_at"],
                    "schema_uri": "urn:paperclip:audit:v1",
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return output_path


class RetentionPolicy:
    """Enforce data retention policies on runtime state."""

    def __init__(self, store: RuntimeStateStore):
        self.store = store

    def apply(self, retention_days: int = 90) -> dict:
        """Delete events and reservations older than retention_days.

        Returns counts of deleted records.
        """
        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
        with self.store._connect() as conn:
            events_deleted = conn.execute(
                "DELETE FROM runtime_events WHERE created_at < ?",
                (cutoff,),
            ).rowcount
            reservations_deleted = conn.execute(
                "DELETE FROM runtime_reservations WHERE created_at < ?",
                (cutoff,),
            ).rowcount
            conn.commit()

        return {
            "events_deleted": events_deleted or 0,
            "reservations_deleted": reservations_deleted or 0,
            "retention_days": retention_days,
            "cutoff": cutoff,
        }
