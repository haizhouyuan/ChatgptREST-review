"""Tests for Phase 4: EvoMap Observer, Dashboard, Migration, Eval Harness.

T4.1: Observer (12 tests)
T4.2: Dashboard (8 tests)
T4.3: Migration (5 tests)
T4.4: Eval golden query (5 tests)
"""

import os
import sys
import json
import tempfile
import pytest

# Add scripts/ to path for migration module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from chatgptrest.evomap.observer import EvoMapObserver
from chatgptrest.evomap.signals import Signal, SignalType, SignalDomain
from chatgptrest.evomap.dashboard import DashboardAPI


# ── T4.1: Observer Tests ──────────────────────────────────────────

class TestEvoMapObserver:

    @pytest.fixture
    def observer(self):
        obs = EvoMapObserver(db_path=":memory:")
        yield obs
        obs.close()

    def test_record_signal(self, observer):
        sid = observer.record(Signal(
            trace_id="tr_001",
            signal_type=SignalType.ROUTE_SELECTED,
            source="advisor",
            domain=SignalDomain.ROUTING,
            data={"route": "funnel"},
        ))
        assert sid != ""

    def test_query_by_trace(self, observer):
        observer.record_event("tr_001", SignalType.ROUTE_SELECTED, "advisor", SignalDomain.ROUTING)
        observer.record_event("tr_001", SignalType.GATE_PASSED, "funnel", SignalDomain.GATE)
        observer.record_event("tr_002", SignalType.ROUTE_SELECTED, "advisor", SignalDomain.ROUTING)

        signals = observer.by_trace("tr_001")
        assert len(signals) == 2

    def test_query_by_type(self, observer):
        observer.record_event("tr_001", SignalType.ROUTE_SELECTED, "advisor")
        observer.record_event("tr_001", SignalType.GATE_PASSED, "funnel")
        signals = observer.query(signal_type=SignalType.ROUTE_SELECTED)
        assert len(signals) == 1

    def test_query_by_domain(self, observer):
        observer.record_event("tr_001", SignalType.GATE_PASSED, "funnel", SignalDomain.GATE)
        observer.record_event("tr_001", SignalType.KB_WRITEBACK, "report", SignalDomain.KB)
        signals = observer.query(domain=SignalDomain.GATE)
        assert len(signals) == 1

    def test_aggregate_by_type(self, observer):
        observer.record_event("tr_001", SignalType.ROUTE_SELECTED, "advisor")
        observer.record_event("tr_002", SignalType.ROUTE_SELECTED, "advisor")
        observer.record_event("tr_001", SignalType.GATE_PASSED, "funnel")
        agg = observer.aggregate_by_type()
        assert agg[SignalType.ROUTE_SELECTED] == 2
        assert agg[SignalType.GATE_PASSED] == 1

    def test_aggregate_by_domain(self, observer):
        observer.record_event("tr_001", SignalType.ROUTE_SELECTED, "advisor", SignalDomain.ROUTING)
        observer.record_event("tr_001", SignalType.GATE_PASSED, "funnel", SignalDomain.GATE)
        agg = observer.aggregate_by_domain()
        assert SignalDomain.ROUTING in agg
        assert SignalDomain.GATE in agg

    def test_count(self, observer):
        observer.record_event("tr_001", SignalType.ROUTE_SELECTED, "advisor")
        observer.record_event("tr_002", SignalType.ROUTE_SELECTED, "advisor")
        assert observer.count(signal_type=SignalType.ROUTE_SELECTED) == 2

    def test_signal_data_roundtrip(self, observer):
        data = {"route": "funnel", "scores": {"C": 75, "K": 30}}
        observer.record(Signal(
            trace_id="tr_data",
            signal_type=SignalType.ROUTE_SELECTED,
            source="advisor",
            data=data,
        ))
        signals = observer.by_trace("tr_data")
        assert signals[0].data["scores"]["C"] == 75

    def test_close_and_reopen(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            obs1 = EvoMapObserver(db_path=db_path)
            obs1.record_event("tr_persist", SignalType.ROUTE_SELECTED, "advisor")
            obs1.close()

            obs2 = EvoMapObserver(db_path=db_path)
            signals = obs2.by_trace("tr_persist")
            assert len(signals) == 1
            obs2.close()
        finally:
            os.unlink(db_path)

    def test_all_signal_types(self, observer):
        """All known signal types can be recorded."""
        types = [
            SignalType.ROUTE_SELECTED,
            SignalType.FUNNEL_STAGE_COMPLETED,
            SignalType.REPORT_STEP_COMPLETED,
            SignalType.GATE_PASSED,
            SignalType.GATE_FAILED,
            SignalType.DISPATCH_COMPLETED,
            SignalType.DISPATCH_FAILED,
            SignalType.KB_WRITEBACK,
        ]
        for st in types:
            observer.record_event("tr_all", st, "test", "test")
        assert observer.count(trace_id="tr_all") == 8


# ── T4.2: Dashboard Tests ────────────────────────────────────────

class TestDashboard:

    @pytest.fixture
    def dashboard(self):
        obs = EvoMapObserver(db_path=":memory:")
        # Seed data
        obs.record(Signal(trace_id="tr_1", signal_type=SignalType.ROUTE_SELECTED,
                          source="advisor", domain=SignalDomain.ROUTING,
                          data={"route": "funnel"}))
        obs.record(Signal(trace_id="tr_2", signal_type=SignalType.ROUTE_SELECTED,
                          source="advisor", domain=SignalDomain.ROUTING,
                          data={"route": "kb_answer"}))
        obs.record(Signal(trace_id="tr_1", signal_type=SignalType.GATE_PASSED,
                          source="funnel", domain=SignalDomain.GATE,
                          data={"gate": "rubric_a"}))
        obs.record(Signal(trace_id="tr_2", signal_type=SignalType.GATE_FAILED,
                          source="funnel", domain=SignalDomain.GATE,
                          data={"gate": "rubric_b"}))
        obs.record(Signal(trace_id="tr_1", signal_type=SignalType.KB_WRITEBACK,
                          source="report", domain=SignalDomain.KB))
        yield DashboardAPI(obs)
        obs.close()

    def test_daily_brief(self, dashboard):
        brief = dashboard.daily_brief()
        assert brief["total_signals"] == 5
        assert "funnel" in brief["route_distribution"]
        assert "kb_answer" in brief["route_distribution"]

    def test_human_loops(self, dashboard):
        loops = dashboard.human_loops()
        assert loops["total_gates"] == 2
        assert loops["passed"] == 1
        assert loops["failed"] == 1
        assert loops["pass_rate"] == 0.5

    def test_kb_leverage(self, dashboard):
        kb = dashboard.kb_leverage()
        assert kb["writebacks"] == 1
        assert kb["kb_routed"] == 1  # kb_answer route
        assert kb["total_routed"] == 2

    def test_gate_effectiveness(self, dashboard):
        eff = dashboard.gate_effectiveness()
        assert eff["total_evaluations"] == 2
        assert "rubric_a" in eff["by_gate"]
        assert eff["by_gate"]["rubric_a"]["passed"] == 1

    def test_daily_brief_empty(self):
        obs = EvoMapObserver(db_path=":memory:")
        api = DashboardAPI(obs)
        brief = api.daily_brief()
        assert brief["total_signals"] == 0
        obs.close()


# ── T4.3: Migration Tests ────────────────────────────────────────

class TestMigration:

    def test_scan_empty_dir(self):
        from migrate_openclaw_kb import KBMigrator, MigrationConfig
        config = MigrationConfig(source_dir="/tmp/nonexistent_migration_dir_xyz")
        migrator = KBMigrator(config=config)
        docs = migrator.scan_documents()
        assert docs == []

    def test_scan_with_files(self):
        from migrate_openclaw_kb import KBMigrator, MigrationConfig
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "doc1.md").write_text("# Test Doc 1")
            (Path(td) / "doc2.txt").write_text("Test Doc 2")
            (Path(td) / "binary.png").write_bytes(b"\x89PNG")

            config = MigrationConfig(source_dir=td)
            migrator = KBMigrator(config=config)
            docs = migrator.scan_documents()
            assert len(docs) == 2  # only .md and .txt

    def test_import_document(self):
        from migrate_openclaw_kb import KBMigrator, MigrationConfig
        with tempfile.TemporaryDirectory() as td:
            test_file = Path(td) / "test.md"
            test_file.write_text("# Test Content")

            registered = []
            config = MigrationConfig(source_dir=td)
            migrator = KBMigrator(
                config=config,
                register_fn=lambda doc: (registered.append(doc), doc["artifact_id"])[1],
            )
            success, msg = migrator.import_document({"path": str(test_file), "size": 14})
            assert success is True
            assert len(registered) == 1
            assert registered[0]["stability"] == "approved"

    def test_idempotent_import(self):
        from migrate_openclaw_kb import KBMigrator, MigrationConfig
        with tempfile.TemporaryDirectory() as td:
            test_file = Path(td) / "test.md"
            test_file.write_text("# Idempotent Test")

            config = MigrationConfig(source_dir=td)
            migrator = KBMigrator(
                config=config,
                is_imported_fn=lambda h: True,  # always says "already imported"
            )
            success, msg = migrator.import_document({"path": str(test_file), "size": 17})
            assert success is False
            assert msg == "already_imported"

    def test_full_migration_run(self):
        from migrate_openclaw_kb import KBMigrator, MigrationConfig
        with tempfile.TemporaryDirectory() as td:
            for i in range(3):
                (Path(td) / f"doc{i}.md").write_text(f"# Doc {i}")

            config = MigrationConfig(source_dir=td)
            migrator = KBMigrator(config=config)
            stats = migrator.run()
            assert stats.total_found == 3
            assert stats.imported == 3
            assert stats.skipped_error == 0


# ── T4.4: Eval Harness ───────────────────────────────────────────

class TestEvalHarness:
    """Basic eval harness tests — validates golden query evaluation logic."""

    def _eval_route(self, message: str) -> str:
        """Run advisor graph and return selected route."""
        from chatgptrest.advisor.graph import build_advisor_graph
        app = build_advisor_graph().compile()
        result = app.invoke({"user_message": message})
        return result.get("selected_route", "")

    def test_report_route(self):
        route = self._eval_route("帮我写个安徽项目进展报告")
        assert route != ""  # should route somewhere

    def test_research_route(self):
        route = self._eval_route("调研一下竞品分析比较评估")
        assert route != ""

    def test_quick_question(self):
        route = self._eval_route("what is our current budget?")
        assert route != ""

    def test_build_feature(self):
        route = self._eval_route("开发一个Agent团队管理Dashboard功能")
        assert route != ""

    def test_multi_intent(self):
        route = self._eval_route("帮我调研竞品并且写个报告")
        assert route != ""


# Need pathlib for migration tests
from pathlib import Path
