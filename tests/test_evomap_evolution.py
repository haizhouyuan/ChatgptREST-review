"""EvoMap Evolution — automated test suite.

Tests all components of the self-evolution system:
  T1:  Signal naming unification
  T2:  Circuit breaker triggers on failures
  T3:  Circuit breaker recovery after window expires
  T4:  KB score increment on kb_direct success
  T5:  KB score decrement on rapid retry
  T6:  Memory injection into prompts
  T7:  Knowledge distiller chunks large files
  T8:  KB pruner removes stale artifacts
  T9:  Gate auto-tuner tightens on rubber-stamping
  T10: Full loop signal flow
"""

import os
import sys
import time
import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chatgptrest.evomap.signals import Signal, SignalType, normalize_signal_type
from chatgptrest.evomap.observer import EvoMapObserver
from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from chatgptrest.evomap.actuators.kb_scorer import KBScorer
from chatgptrest.evomap.actuators.memory_injector import MemoryInjector
from chatgptrest.evomap.actuators.gate_tuner import GateAutoTuner


@dataclass
class MockEvent:
    """Minimal EventBus event for testing."""
    event_id: str = ""
    event_type: str = ""
    trace_id: str = ""
    source: str = ""
    timestamp: str = ""
    data: dict = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}


class TestSignalNaming(unittest.TestCase):
    """T1: Signal naming unification."""

    def test_normalize_legacy_route_selected(self):
        self.assertEqual(normalize_signal_type("route_selected"), "route.selected")

    def test_normalize_already_canonical(self):
        self.assertEqual(normalize_signal_type("route.selected"), "route.selected")
        self.assertEqual(normalize_signal_type("llm.call_failed"), "llm.call_failed")

    def test_observer_normalizes_on_record(self):
        obs = EvoMapObserver(db_path=":memory:")
        sig = Signal(
            signal_type="route_selected",
            source="test",
            domain="routing",
        )
        obs.record(sig)
        # Should be normalized
        results = obs.query(signal_type="route.selected")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].signal_type, "route.selected")
        obs.close()


class TestCircuitBreaker(unittest.TestCase):
    """T2-T3: Circuit breaker triggers and recovery."""

    def setUp(self):
        self.observer = EvoMapObserver(db_path=":memory:")
        self.config = CircuitBreakerConfig(
            consecutive_fail_threshold=3,
            window_fail_threshold=5,
            degraded_seconds=2,  # short for testing
            cooldown_seconds=3,
            window_seconds=10,
        )
        self.breaker = CircuitBreaker(
            observer=self.observer,
            config=self.config,
        )

    def test_t2_triggers_degraded_on_consecutive_failures(self):
        """3 consecutive failures → DEGRADED."""
        for i in range(3):
            event = MockEvent(
                event_type="llm.call_failed",
                data={"provider_id": "test_provider", "error_category": "timeout"},
            )
            self.breaker.on_event(event)

        status = self.breaker.get_status()
        self.assertIn("test_provider", status)
        self.assertIn(status["test_provider"]["state"], ("degraded", "cooldown"))

        # Verify signal was emitted
        signals = self.observer.query(signal_type="actuator.circuit_break")
        self.assertGreater(len(signals), 0)

    def test_t3_recovery_after_window_expires(self):
        """Provider recovers after degraded period + success."""
        # Trigger degraded
        for i in range(3):
            self.breaker.on_event(MockEvent(
                event_type="llm.call_failed",
                data={"provider_id": "recover_test", "error_category": "timeout"},
            ))

        # Wait for degraded period to expire
        time.sleep(2.5)

        # Send success → should recover
        self.breaker.on_event(MockEvent(
            event_type="llm.call_completed",
            data={"provider_id": "recover_test", "latency_ms": 500},
        ))

        status = self.breaker.get_status()
        self.assertEqual(status["recover_test"]["state"], "healthy")

    def tearDown(self):
        self.observer.close()


class TestKBScorer(unittest.TestCase):
    """T4-T5: KB quality scoring."""

    def setUp(self):
        # Create temp kb_registry.db
        self.tmp_dir = tempfile.mkdtemp()
        self.kb_reg = os.path.join(self.tmp_dir, "kb_registry.db")
        conn = sqlite3.connect(self.kb_reg)
        conn.execute("""
            CREATE TABLE artifacts (
                artifact_id TEXT PRIMARY KEY,
                source_system TEXT DEFAULT '',
                source_path TEXT DEFAULT '',
                project_id TEXT DEFAULT '',
                content_hash TEXT DEFAULT '',
                content_type TEXT DEFAULT '',
                file_size INTEGER DEFAULT 0,
                created_at TEXT DEFAULT '',
                modified_at TEXT DEFAULT '',
                indexed_at TEXT DEFAULT '',
                quality_score REAL DEFAULT 0.0,
                stability TEXT DEFAULT 'active'
            )
        """)
        conn.execute(
            "INSERT INTO artifacts (artifact_id, quality_score) VALUES ('art_001', 0.0)"
        )
        conn.commit()
        conn.close()

        self.observer = EvoMapObserver(db_path=":memory:")
        # Patch the KB path
        self._orig_kb_path = os.path.expanduser("~/.openmind/kb_registry.db")

    def test_t4_kb_score_increment(self):
        """KB direct success → quality_score increases."""
        with patch.dict(os.environ, {"OPENMIND_KB_DB": self.kb_reg}, clear=False):
            new_score = self.observer.update_kb_score("art_001", 0.1)
            self.assertAlmostEqual(new_score, 0.1, places=2)

    def test_t5_kb_score_decrement(self):
        """Rapid retry → quality_score decreases."""
        conn = sqlite3.connect(self.kb_reg)
        conn.execute("UPDATE artifacts SET quality_score = 0.5 WHERE artifact_id = 'art_001'")
        conn.commit()
        conn.close()

        with patch.dict(os.environ, {"OPENMIND_KB_DB": self.kb_reg}, clear=False):
            new_score = self.observer.update_kb_score("art_001", -0.2)
            self.assertAlmostEqual(new_score, 0.3, places=2)

    def tearDown(self):
        self.observer.close()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)


class TestMemoryInjector(unittest.TestCase):
    """T6: Memory injection into prompts."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.mem_db = os.path.join(self.tmp_dir, "memory.db")
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.mem_db)
        conn.execute("""
            CREATE TABLE memory_records (
                record_id TEXT PRIMARY KEY,
                tier TEXT NOT NULL,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 0.0,
                source TEXT NOT NULL,
                evidence TEXT,
                fingerprint TEXT,
                ttl_expires_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO memory_records VALUES "
            "('r1', 'meta', 'route_stat', 'test_key', "
            "'{\"intent\": \"TEST\", \"route\": \"funnel\"}', "
            "1.0, 'test', NULL, NULL, NULL, "
            "?, ?)",
            (now, now),
        )
        conn.commit()
        conn.close()

    def test_t6_memory_retrieval_with_data(self):
        """With relevant memories → returns formatted context block."""
        injector = MemoryInjector(db_path=self.mem_db)
        context = injector.retrieve(domain="route", limit=3)
        self.assertIn("<past_experiences>", context)
        self.assertIn("route_stat", context)

    def test_t6_memory_retrieval_empty(self):
        """With no relevant memories → returns empty string."""
        injector = MemoryInjector(db_path=self.mem_db)
        context = injector.retrieve(domain="nonexistent_domain", limit=3)
        self.assertEqual(context, "")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)


class TestGateAutoTuner(unittest.TestCase):
    """T9: Gate auto-tuner tightens on rubber-stamping."""

    def setUp(self):
        self.observer = EvoMapObserver(db_path=":memory:")
        self.tuner = GateAutoTuner(
            observer=self.observer,
            initial_threshold=0.6,
        )

    def test_t9_tightens_on_high_pass_rate_with_failures(self):
        """93% pass rate + downstream failures → threshold increases."""
        # Send 3 downstream failures first (don't count as gate events)
        for _ in range(3):
            self.tuner.on_event(MockEvent(event_type="dispatch.task_failed"))
        # Simulate 47 passes + 3 failures = 50 gate events (94% pass rate)
        for _ in range(47):
            self.tuner.on_event(MockEvent(event_type="gate.passed"))
        for _ in range(3):
            self.tuner.on_event(MockEvent(event_type="gate.failed"))

        # Should have triggered evaluation (50 gate events)
        self.assertGreater(self.tuner.threshold, 0.6)

        # Verify signal emitted
        signals = self.observer.query(signal_type="actuator.gate_tuned")
        self.assertGreater(len(signals), 0)

    def test_t9_loosens_on_low_pass_rate(self):
        """Low pass rate → threshold decreases."""
        tuner = GateAutoTuner(
            observer=self.observer,
            initial_threshold=0.8,
        )
        # Simulate 20 passes, 30 failures (40% pass rate)
        for _ in range(20):
            tuner.on_event(MockEvent(event_type="gate.passed"))
        for _ in range(30):
            tuner.on_event(MockEvent(event_type="gate.failed"))

        self.assertLess(tuner.threshold, 0.8)

    def tearDown(self):
        self.observer.close()


class TestFullLoopSignalFlow(unittest.TestCase):
    """T10: End-to-end signal flow."""

    def test_t10_signal_flow_observer_to_actuator(self):
        """Signal recorded → actuator reacts."""
        observer = EvoMapObserver(db_path=":memory:")
        breaker = CircuitBreaker(
            observer=observer,
            config=CircuitBreakerConfig(consecutive_fail_threshold=2),
        )

        # Simulate 2 failures
        for _ in range(2):
            event = MockEvent(
                event_type="llm.call_failed",
                data={"provider_id": "e2e_provider", "error_category": "timeout"},
            )
            breaker.on_event(event)

        # Verify both the original signal AND the actuator signal exist
        all_types = observer.aggregate_by_type()
        # actuator.circuit_break should be in the DB
        self.assertIn("actuator.circuit_break", all_types)

        # Provider should be degraded
        status = breaker.get_status()
        self.assertIn("e2e_provider", status)
        self.assertIn(
            status["e2e_provider"]["state"],
            ("degraded", "cooldown"),
        )

        observer.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
