"""P7: Intelligence layer — predictive routing and anomaly detection.

Uses historical events to score providers and detect unusual patterns.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from runtime_allocator.runtime_state import RuntimeStateStore


class PredictiveRouter:
    """Score providers using historical latency and success rate."""

    def __init__(self, store: RuntimeStateStore, lookback_hours: int = 24):
        self.store = store
        self.lookback_hours = lookback_hours

    def score_providers(self, task_class: str = "") -> dict[str, float]:
        """Return provider_id -> score (0-1) based on recent history.

        Higher score = better predicted performance.
        """
        since = (datetime.now() - timedelta(hours=self.lookback_hours)).isoformat()
        with self.store._connect() as conn:
            rows = conn.execute(
                """SELECT provider_id, status, latency_ms
                   FROM runtime_events
                   WHERE created_at > ?
                     AND (task_class = ? OR ? = '')""",
                (since, task_class, task_class),
            ).fetchall()

        stats: dict[str, dict] = defaultdict(lambda: {"success": 0, "fail": 0, "latency_sum": 0, "count": 0})
        for row in rows:
            pid = row["provider_id"] or "unknown"
            if row["status"] in ("committed", "success"):
                stats[pid]["success"] += 1
            else:
                stats[pid]["fail"] += 1
            if row["latency_ms"]:
                stats[pid]["latency_sum"] += row["latency_ms"]
                stats[pid]["count"] += 1

        scores = {}
        for pid, s in stats.items():
            total = s["success"] + s["fail"]
            if total == 0:
                scores[pid] = 0.5
                continue
            success_rate = s["success"] / total
            avg_latency = s["latency_sum"] / max(s["count"], 1)
            # Normalize latency: lower is better, scale 0-1 against 10s max
            latency_score = max(0, 1 - avg_latency / 10000)
            scores[pid] = round(0.7 * success_rate + 0.3 * latency_score, 3)

        return scores

    def recommend_provider(self, candidates: list[str], task_class: str = "") -> Optional[str]:
        """Recommend the best provider from a candidate list."""
        scores = self.score_providers(task_class)
        best = None
        best_score = -1.0
        for pid in candidates:
            score = scores.get(pid, 0.5)
            if score > best_score:
                best_score = score
                best = pid
        return best


class AnomalyDetector:
    """Detect unusual token usage or latency patterns."""

    def __init__(self, store: RuntimeStateStore):
        self.store = store

    def check_recent_anomalies(self, window_minutes: int = 60) -> list[dict]:
        """Return list of anomaly alerts from recent events."""
        since = (datetime.now() - timedelta(minutes=window_minutes)).isoformat()
        with self.store._connect() as conn:
            rows = conn.execute(
                """SELECT provider_id, latency_ms, tokens_actual, task_class, created_at
                   FROM runtime_events
                   WHERE created_at > ?""",
                (since,),
            ).fetchall()

        if not rows:
            return []

        latencies = [r["latency_ms"] for r in rows if r["latency_ms"]]
        tokens = [r["tokens_actual"] for r in rows if r["tokens_actual"]]

        if len(latencies) < 3 or len(tokens) < 3:
            return []

        avg_lat = sum(latencies) / len(latencies)
        avg_tok = sum(tokens) / len(tokens)
        anomalies = []

        for row in rows:
            lat = row["latency_ms"] or 0
            tok = row["tokens_actual"] or 0
            if lat > avg_lat * 3:
                anomalies.append({
                    "type": "latency_spike",
                    "provider_id": row["provider_id"],
                    "task_class": row["task_class"],
                    "latency_ms": lat,
                    "expected_ms": round(avg_lat, 1),
                    "created_at": row["created_at"],
                })
            if tok > avg_tok * 5:
                anomalies.append({
                    "type": "token_spike",
                    "provider_id": row["provider_id"],
                    "task_class": row["task_class"],
                    "tokens_actual": tok,
                    "expected": round(avg_tok, 1),
                    "created_at": row["created_at"],
                })

        return anomalies
