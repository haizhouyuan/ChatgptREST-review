"""P5: Multi-tenant cost attribution and usage tracking.

Tracks per-company, per-provider, per-task spending and quota usage.
Builds on RuntimeStateStore events and reservations.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from runtime_allocator.runtime_state import RuntimeStateStore


class CostAttribution:
    """Compute per-tenant costs from reservation and event records."""

    def __init__(self, store: RuntimeStateStore):
        self.store = store

    def daily_summary(
        self,
        company_id: str = "",
        date: Optional[str] = None,
    ) -> dict:
        """Return daily usage and estimated cost per provider.

        Args:
            company_id: Filter by tenant (empty = all).
            date: YYYY-MM-DD string (default today).
        """
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        with self.store._connect() as conn:
            params = [f"{target_date}%"]
            where = "created_at LIKE ?"
            if company_id:
                where += " AND company_id = ?"
                params.append(company_id)

            rows = conn.execute(
                f"""SELECT provider_id, task_class, status, COUNT(*) as calls,
                           AVG(latency_ms) as avg_latency
                    FROM runtime_events
                    WHERE {where}
                    GROUP BY provider_id, task_class, status""",
                params,
            ).fetchall()

        # Cost estimation (simplified — real costs come from provider APIs)
        _COST_PER_CALL: dict[str, float] = {
            "claudekimi": 0.05,
            "minimax": 0.01,
            "gemini_local": 0.00,
            "ollama_gpu0": 0.00,
        }

        providers: dict[str, dict] = {}
        total_cost = 0.0
        total_calls = 0

        for row in rows:
            pid = row["provider_id"] or "unknown"
            if pid not in providers:
                providers[pid] = {
                    "calls": 0,
                    "cost_usd": 0.0,
                    "avg_latency_ms": 0.0,
                    "tasks": set(),
                }
            providers[pid]["calls"] += row["calls"]
            providers[pid]["cost_usd"] += row["calls"] * _COST_PER_CALL.get(pid, 0.01)
            providers[pid]["avg_latency_ms"] = round(row["avg_latency"] or 0, 2)
            providers[pid]["tasks"].add(row["task_class"])
            total_calls += row["calls"]

        for p in providers.values():
            p["tasks"] = sorted(p["tasks"])
            total_cost += p["cost_usd"]

        return {
            "date": target_date,
            "company_id": company_id or "all",
            "total_calls": total_calls,
            "total_cost_usd": round(total_cost, 4),
            "providers": providers,
        }

    def alert_if_over_budget(
        self,
        company_id: str,
        daily_budget_usd: float = 10.0,
    ) -> Optional[dict]:
        """Return alert dict if today's estimated cost exceeds budget."""
        summary = self.daily_summary(company_id=company_id)
        if summary["total_cost_usd"] > daily_budget_usd:
            return {
                "alert": "budget_exceeded",
                "company_id": company_id,
                "daily_budget_usd": daily_budget_usd,
                "actual_usd": summary["total_cost_usd"],
                "date": summary["date"],
            }
        return None
