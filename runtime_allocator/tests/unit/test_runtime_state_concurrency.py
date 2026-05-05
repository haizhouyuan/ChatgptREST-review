"""RuntimeStateStore concurrency stress tests."""

from __future__ import annotations

import concurrent.futures
import tempfile

import pytest

from runtime_allocator.runtime_state import RuntimeStateStore


class TestConcurrentReserve:
    @pytest.fixture
    def store(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        s = RuntimeStateStore(tmp.name)
        s.init_budget("test_provider", hard_rpd=20, soft_rpd=10)
        yield s
        import os
        os.unlink(tmp.name)

    def test_concurrent_reserve_race(self, store):
        """20 threads simultaneously reserve — all should succeed within budget."""
        results = []

        def do_reserve(i):
            try:
                rid = store.reserve("test_provider", request_id=f"r{i}", task_class="test")
                return rid
            except Exception as e:
                return str(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(do_reserve, i) for i in range(20)]
            results = [f.result() for f in futures]

        assert all(r is not None for r in results)
        assert len(set(results)) == 20

    def test_concurrent_try_reserve_enforces_hard_limit(self, store):
        """try_reserve must never exceed hard_rpd even under concurrent load."""
        results = []

        def do_try_reserve(i):
            return store.try_reserve("test_provider", request_id=f"r{i}", task_class="test")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(do_try_reserve, i) for i in range(30)]
            results = [f.result() for f in futures]

        successful = [r for r in results if r is not None]
        failed = [r for r in results if r is None]

        # hard_rpd=20, so at most 20 should succeed
        assert len(successful) <= 20, f"Budget breached: {len(successful)} succeeded"
        assert len(failed) >= 10, f"Expected at least 10 failures, got {len(failed)}"

    def test_concurrent_reserve_no_operational_error(self, store):
        """Concurrent writes must not raise OperationalError."""
        errors = []

        def do_reserve(i):
            try:
                store.reserve("test_provider", request_id=f"r{i}", task_class="test")
                return None
            except Exception as e:
                return type(e).__name__

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(do_reserve, i) for i in range(50)]
            errors = [f.result() for f in futures]

        operational_errors = [e for e in errors if e is not None]
        assert not operational_errors, f"Got errors: {operational_errors}"

    def test_stability_20_iterations(self, store):
        """Run concurrent reserve 20 times to prove not flaky."""
        for _ in range(20):
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
                futures = [ex.submit(store.reserve, "test_provider", f"r{i}", "test") for i in range(10)]
                results = [f.result() for f in futures]
            assert len(set(results)) == 10
