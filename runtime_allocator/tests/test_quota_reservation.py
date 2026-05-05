"""D2: Quota/reservation tests — concurrent reserve, hard limits."""

from __future__ import annotations

import concurrent.futures
import tempfile

import pytest

from runtime_allocator.runtime_state import RuntimeStateStore


class TestReservationLifecycle:
    @pytest.fixture
    def store(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        s = RuntimeStateStore(tmp.name)
        s.init_budget("test_provider", hard_rpd=5, soft_rpd=3)
        yield s
        import os

        os.unlink(tmp.name)

    def test_reserve_and_commit(self, store):
        rid = store.reserve("test_provider", request_id="r1", task_class="test")
        store.commit(rid, actual_input_tokens=100, actual_output_tokens=50)
        count = store.count_today("test_provider", "committed")
        assert count == 1

    def test_refund_does_not_count(self, store):
        rid = store.reserve("test_provider", request_id="r1", task_class="test")
        store.refund(rid)
        count = store.count_today_units("test_provider")
        assert count == 0

    def test_hard_budget_enforced(self, store):
        # Reserve up to hard limit
        for i in range(5):
            rid = store.reserve("test_provider", request_id=f"r{i}", task_class="test")
            store.commit(rid, 0, 0)
        # 6th should fail can_reserve
        assert not store.can_reserve("test_provider")

    def test_count_today_units_includes_reserved(self, store):
        rid1 = store.reserve("test_provider", request_id="r1", task_class="test")
        # Not committed yet — should still count in units
        assert store.count_today_units("test_provider") == 1
        store.commit(rid1, 0, 0)
        assert store.count_today_units("test_provider") == 1

    def test_concurrent_reserve_race(self, store):
        """Concurrent reservations should all succeed (no race)."""
        results = []

        def do_reserve(i):
            try:
                rid = store.reserve("test_provider", request_id=f"c{i}", task_class="test")
                return rid
            except Exception as e:
                return str(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(do_reserve, i) for i in range(10)]
            results = [f.result() for f in futures]

        # All 10 reservations should have succeeded (SQLite handles concurrency)
        assert all(r is not None for r in results)
        assert len(set(results)) == 10  # All unique
