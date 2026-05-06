"""EvoMap Dashboard API — data endpoints for 4 dashboard views.

Views:
  1. Daily Brief: signal counts, route distribution, gate pass rates
  2. Human Loop: pending/resolved human-in-the-loop interactions
  3. KB Leverage: KB hit rates, writeback counts
  4. Gate Effectiveness: rubric pass/fail rates per gate
"""

from __future__ import annotations

import logging
from typing import Any

from chatgptrest.evomap.observer import EvoMapObserver
from chatgptrest.evomap.signals import SignalType, SignalDomain

logger = logging.getLogger(__name__)


class DashboardAPI:
    """Data API for EvoMap dashboard views.

    Usage::

        api = DashboardAPI(observer)
        brief = api.daily_brief()
        loops = api.human_loops()
    """

    def __init__(self, observer: EvoMapObserver) -> None:
        self._observer = observer

    def daily_brief(
        self, *, since: str = "", until: str = ""
    ) -> dict[str, Any]:
        """Daily brief: signal counts and route distribution.

        All counts respect since/until time window (P1 fix).
        """
        # Get ALL signals in time window, then aggregate
        all_signals = self._observer.query(
            since=since, until=until, limit=10000,
        )

        type_counts: dict[str, int] = {}
        domain_counts: dict[str, int] = {}
        route_dist: dict[str, int] = {}

        for s in all_signals:
            type_counts[s.signal_type] = type_counts.get(s.signal_type, 0) + 1
            if s.domain:
                domain_counts[s.domain] = domain_counts.get(s.domain, 0) + 1
            if s.signal_type == SignalType.ROUTE_SELECTED:
                route = s.data.get("route", "unknown")
                route_dist[route] = route_dist.get(route, 0) + 1

        return {
            "total_signals": len(all_signals),
            "by_type": type_counts,
            "by_domain": domain_counts,
            "route_distribution": route_dist,
        }

    def human_loops(
        self, *, since: str = "", until: str = ""
    ) -> dict[str, Any]:
        """Human-in-the-loop drilldown: pending and resolved gates."""
        gate_passed = self._observer.query(
            signal_type=SignalType.GATE_PASSED,
            since=since, until=until,
        )
        gate_failed = self._observer.query(
            signal_type=SignalType.GATE_FAILED,
            since=since, until=until,
        )

        return {
            "total_gates": len(gate_passed) + len(gate_failed),
            "passed": len(gate_passed),
            "failed": len(gate_failed),
            "pass_rate": (
                len(gate_passed) / (len(gate_passed) + len(gate_failed))
                if (gate_passed or gate_failed)
                else 0.0
            ),
            "recent_failures": [
                {"trace_id": s.trace_id, "data": s.data, "timestamp": s.timestamp}
                for s in gate_failed[:5]
            ],
        }

    def kb_leverage(
        self, *, since: str = "", until: str = ""
    ) -> dict[str, Any]:
        """KB leverage: how much KB is contributing to answers."""
        wb_signals = self._observer.query(
            signal_type=SignalType.KB_WRITEBACK,
            since=since, until=until,
        )
        route_signals = self._observer.query(
            signal_type=SignalType.ROUTE_SELECTED,
            since=since, until=until,
        )

        kb_routes = sum(
            1 for s in route_signals
            if s.data.get("route") in ("kb_answer", "hybrid")
        )

        return {
            "writebacks": len(wb_signals),
            "kb_routed": kb_routes,
            "total_routed": len(route_signals),
            "kb_leverage_pct": (
                kb_routes / len(route_signals) * 100
                if route_signals else 0.0
            ),
        }

    def gate_effectiveness(
        self, *, since: str = "", until: str = ""
    ) -> dict[str, Any]:
        """Gate effectiveness: pass/fail rates per gate type."""
        all_gates = self._observer.query(
            domain=SignalDomain.GATE,
            since=since, until=until,
        )

        by_gate: dict[str, dict[str, int]] = {}
        for s in all_gates:
            gate_name = s.data.get("gate", "unknown")
            if gate_name not in by_gate:
                by_gate[gate_name] = {"passed": 0, "failed": 0}
            if s.signal_type == SignalType.GATE_PASSED:
                by_gate[gate_name]["passed"] += 1
            else:
                by_gate[gate_name]["failed"] += 1

        return {
            "total_evaluations": len(all_gates),
            "by_gate": by_gate,
        }
