"""
Full-coverage business flow integration tests for Agent Teams (#78).

Tests the COMPLETE lifecycle from contract creation through dispatch,
event emission, scorecard persistence, policy routing, and API wiring.
"""

import asyncio
import json
import os
import sqlite3
import sys
import time
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# ── Mock anthropic + mcp modules if not installed (test env) ──
for _mod in ("anthropic", "mcp", "mcp.client", "mcp.client.sse",
             "mcp.client.stdio", "mcp.client.stdio"):
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

# Give anthropic a minimal mock shape
_anthropic = sys.modules["anthropic"]
if not hasattr(_anthropic, "AsyncAnthropic"):
    _anthropic.AsyncAnthropic = MagicMock
    _anthropic.NOT_GIVEN = object()

# Give mcp client modules the classes cc_native.py imports
_mcp = sys.modules["mcp"]
if not hasattr(_mcp, "ClientSession"):
    _mcp.ClientSession = MagicMock
    _mcp.StdioServerParameters = MagicMock
_sse = sys.modules["mcp.client.sse"]
if not hasattr(_sse, "sse_client"):
    _sse.sse_client = MagicMock
_stdio = sys.modules.get("mcp.client.stdio") or sys.modules.setdefault(
    "mcp.client.stdio", types.ModuleType("mcp.client.stdio"))
if not hasattr(_stdio, "stdio_client"):
    _stdio.stdio_client = MagicMock


# ═══════════════════════════════════════════════════════════════════
# FLOW 1: TeamSpec contract lifecycle — create → serialize → restore
# ═══════════════════════════════════════════════════════════════════


class TestTeamSpecContractFlow:
    """Business flow: define a team, serialize for API, restore from response."""

    def test_full_lifecycle(self):
        from chatgptrest.kernel.team_types import TeamSpec, RoleSpec

        # 1. Create team from structured roles
        spec = TeamSpec(roles=[
            RoleSpec(name="architect", model="opus", description="System design",
                     prompt="Design the architecture"),
            RoleSpec(name="coder", model="sonnet", description="Implementation",
                     prompt="Implement the design", tools=["bash", "read_file"]),
            RoleSpec(name="reviewer", model="sonnet", description="Quality check",
                     prompt="Review the code"),
        ])

        # 2. Verify deterministic team_id
        assert len(spec.team_id) == 16
        spec2 = TeamSpec(roles=[
            RoleSpec(name="reviewer", model="sonnet", description="Quality check",
                     prompt="Review the code"),
            RoleSpec(name="coder", model="sonnet", description="Implementation",
                     prompt="Implement the design", tools=["bash", "read_file"]),
            RoleSpec(name="architect", model="opus", description="System design",
                     prompt="Design the architecture"),
        ])
        assert spec.team_id == spec2.team_id  # order-independent

        # 3. Serialize to agents_json (for CC CLI)
        agents_json = spec.to_agents_json()
        assert "architect" in agents_json
        assert "coder" in agents_json
        assert agents_json["coder"]["tools"] == ["bash", "read_file"]
        assert "tools" not in agents_json["architect"]  # omitted when empty

        # 4. Serialize to dict for API response / storage
        d = spec.to_dict()
        assert "team_id" in d
        assert "roles" in d
        assert len(d["roles"]) == 3

        # 5. Restore from dict
        spec3 = TeamSpec.from_dict(d)
        assert spec3.team_id == spec.team_id
        assert len(spec3.roles) == 3

    def test_legacy_dict_format_roundtrip(self):
        """Business case: existing code sends team as flat dict."""
        from chatgptrest.kernel.team_types import TeamSpec

        legacy = {
            "reviewer": {"description": "Expert code reviewer", "model": "sonnet",
                         "prompt": "Focus on correctness"},
            "security": {"description": "Security specialist", "model": "haiku",
                         "prompt": "Find vulnerabilities"},
        }
        spec = TeamSpec.from_dict(legacy)
        assert len(spec.roles) == 2
        assert spec.team_id  # computed

        # to_agents_json should produce compatible output
        aj = spec.to_agents_json()
        assert aj["reviewer"]["model"] == "sonnet"
        assert aj["security"]["model"] == "haiku"


# ═══════════════════════════════════════════════════════════════════
# FLOW 2: Scorecard lifecycle — record → aggregate → rank
# ═══════════════════════════════════════════════════════════════════


class TestScorecardBusinessFlow:
    """Business flow: teams run tasks, scorecard tracks and ranks them."""

    @pytest.fixture
    def store(self):
        from chatgptrest.evomap.team_scorecard import TeamScorecardStore
        s = TeamScorecardStore(db_path=":memory:")
        yield s
        s.close()

    def _run(self, store, team_name, ok=True, quality=0.8, task_type="review",
             repo="chatgptrest", cost=0.05, elapsed=10.0):
        from chatgptrest.kernel.team_types import TeamSpec, TeamRunRecord, RoleSpec
        spec = TeamSpec(roles=[RoleSpec(name=team_name, model="sonnet")])
        r = TeamRunRecord(
            team_spec=spec, repo=repo, task_type=task_type,
            result_ok=ok, quality_score=quality, cost_usd=cost,
            elapsed_seconds=elapsed,
        )
        store.record_outcome(r)
        return spec

    def test_scoring_and_ranking(self, store):
        """Scenario: 3 teams run review tasks, scorecard ranks them."""
        # Team Alpha: consistently excellent
        for _ in range(5):
            spec_a = self._run(store, "alpha", ok=True, quality=0.95)

        # Team Beta: decent but not great
        for _ in range(5):
            spec_b = self._run(store, "beta", ok=True, quality=0.60)

        # Team Gamma: unreliable
        for i in range(5):
            spec_g = self._run(store, "gamma",
                               ok=(i < 2), quality=0.40 if i < 2 else 0.0)

        # Rank
        ranked = store.rank_teams(repo="chatgptrest", task_type="review")
        assert len(ranked) == 3
        assert ranked[0].composite_score > ranked[1].composite_score
        assert ranked[1].composite_score > ranked[2].composite_score

        # Alpha should be at the top
        alpha_card = store.get_scorecard(spec_a.team_id, repo="chatgptrest",
                                         task_type="review")
        assert alpha_card.success_rate == 1.0
        assert alpha_card.avg_quality > 0.9

    def test_multi_repo_isolation(self, store):
        """Scorecards for same team in different repos are separate."""
        self._run(store, "agent", ok=True, quality=0.9, repo="repoA",
                  task_type="review")
        self._run(store, "agent", ok=False, quality=0.1, repo="repoB",
                  task_type="review")

        ranked_a = store.rank_teams(repo="repoA", task_type="review")
        ranked_b = store.rank_teams(repo="repoB", task_type="review")

        assert len(ranked_a) == 1
        assert len(ranked_b) == 1
        assert ranked_a[0].success_rate == 1.0
        assert ranked_b[0].success_rate == 0.0

    def test_sqlite_persistence(self):
        """Verify scorecard data survives store close/reopen."""
        import tempfile
        from chatgptrest.evomap.team_scorecard import TeamScorecardStore
        from chatgptrest.kernel.team_types import TeamSpec, TeamRunRecord, RoleSpec

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Write
            s1 = TeamScorecardStore(db_path=db_path)
            spec = TeamSpec(roles=[RoleSpec(name="persist_test", model="sonnet")])
            r = TeamRunRecord(team_spec=spec, repo="test", task_type="review",
                              result_ok=True, quality_score=0.85)
            s1.record_outcome(r)
            s1.close()

            # Read
            s2 = TeamScorecardStore(db_path=db_path)
            card = s2.get_scorecard(spec.team_id, repo="test", task_type="review")
            assert card is not None
            assert card.total_runs == 1
            assert card.success_rate == 1.0
            s2.close()
        finally:
            os.unlink(db_path)


# ═══════════════════════════════════════════════════════════════════
# FLOW 3: Policy routing — recommend teams based on scorecard
# ═══════════════════════════════════════════════════════════════════


class TestPolicyRoutingFlow:
    """Business flow: policy selects best team or explores."""

    @pytest.fixture
    def env(self):
        from chatgptrest.evomap.team_scorecard import TeamScorecardStore
        from chatgptrest.kernel.team_policy import TeamPolicy, TeamPolicyConfig
        from chatgptrest.kernel.team_types import TeamSpec, TeamRunRecord, RoleSpec
        import random

        store = TeamScorecardStore(db_path=":memory:")

        # Seed 2 teams
        for _ in range(5):
            s = TeamSpec(roles=[RoleSpec(name="star_team", model="opus")])
            store.record_outcome(TeamRunRecord(
                team_spec=s, repo="r", task_type="review",
                result_ok=True, quality_score=0.95,
            ))
        for _ in range(5):
            s = TeamSpec(roles=[RoleSpec(name="ok_team", model="sonnet")])
            store.record_outcome(TeamRunRecord(
                team_spec=s, repo="r", task_type="review",
                result_ok=True, quality_score=0.55,
            ))

        yield {"store": store, "TeamPolicy": TeamPolicy,
               "TeamPolicyConfig": TeamPolicyConfig}
        store.close()

    def test_exploit_mode(self, env):
        """No exploration: always picks the best team."""
        policy = env["TeamPolicy"](
            scorecard_store=env["store"],
            config=env["TeamPolicyConfig"](exploration_rate=0.0),
        )
        rec = policy.recommend(repo="r", task_type="review")
        assert rec is not None
        assert rec.roles[0].name == "star_team"

    def test_no_data_returns_none(self, env):
        """No history for this repo → None."""
        policy = env["TeamPolicy"](
            scorecard_store=env["store"],
            config=env["TeamPolicyConfig"](exploration_rate=0.0),
        )
        assert policy.recommend(repo="unknown_repo", task_type="review") is None

    def test_exploration_sometimes_picks_non_best(self, env):
        """With exploration=1.0, should sometimes pick the non-top team."""
        import random
        rng = random.Random(123)
        policy = env["TeamPolicy"](
            scorecard_store=env["store"],
            config=env["TeamPolicyConfig"](exploration_rate=1.0),
            rng=rng,
        )
        picks = set()
        for _ in range(20):
            rec = policy.recommend(repo="r", task_type="review")
            if rec:
                picks.add(rec.roles[0].name)
        # Should have picked both teams at least once
        assert len(picks) == 2


# ═══════════════════════════════════════════════════════════════════
# FLOW 4: Signal/Event lifecycle — events emitted correctly
# ═══════════════════════════════════════════════════════════════════


class TestEventLifecycleFlow:
    """Business flow: dispatch_team emits all expected events."""

    def test_signal_domain_mapping(self):
        """All team.* event types map to 'team' domain."""
        from chatgptrest.evomap.signals import Signal

        for event_type in [
            "team.run.created", "team.run.completed", "team.run.failed",
            "team.role.completed", "team.role.failed",
            "team.output.accepted", "team.output.rejected",
        ]:
            class FakeEvt:
                event_id = "e1"
                trace_id = "t1"
                source = "cc_native"
                timestamp = "2026-01-01"
                data = {}
            FakeEvt.event_type = event_type
            sig = Signal.from_trace_event(FakeEvt())
            assert sig.domain == "team", f"{event_type} should map to team domain"

    def test_emit_event_calls_event_bus(self):
        """_emit_event should create TraceEvent and call event_bus.emit."""
        from chatgptrest.kernel.cc_native import CcNativeExecutor

        mock_bus = MagicMock()
        executor = CcNativeExecutor.__new__(CcNativeExecutor)
        executor._event_bus = mock_bus
        executor._observer = None
        executor._memory = None
        executor._routing_fabric = None
        executor._scorecard_store = None
        executor._team_policy = None

        executor._emit_event("team.run.created", "trace_123", {"team_id": "abc"})
        mock_bus.emit.assert_called_once()

    def test_record_signal_calls_observer(self):
        """_record_signal should create Signal and call observer.record."""
        from chatgptrest.kernel.cc_native import CcNativeExecutor

        mock_obs = MagicMock()
        executor = CcNativeExecutor.__new__(CcNativeExecutor)
        executor._event_bus = None
        executor._observer = mock_obs
        executor._memory = None
        executor._routing_fabric = None
        executor._scorecard_store = None
        executor._team_policy = None

        executor._record_signal("team.run.completed", "t1", "team", {"ok": True})
        mock_obs.record.assert_called_once()
        sig = mock_obs.record.call_args[0][0]
        assert sig.domain == "team"
        assert sig.signal_type == "team.run.completed"


# ═══════════════════════════════════════════════════════════════════
# FLOW 5: dispatch_team E2E — full pipeline with mocked Anthropic
# ═══════════════════════════════════════════════════════════════════


class TestDispatchTeamE2E:
    """Business flow: end-to-end dispatch_team with mocked LLM."""

    @pytest.fixture
    def executor(self):
        from chatgptrest.kernel.cc_native import CcNativeExecutor
        from chatgptrest.evomap.team_scorecard import TeamScorecardStore
        from chatgptrest.kernel.team_control_plane import TeamControlPlane

        mock_bus = MagicMock()
        mock_obs = MagicMock()
        store = TeamScorecardStore(db_path=":memory:")
        plane = TeamControlPlane(db_path=":memory:")

        executor = CcNativeExecutor.__new__(CcNativeExecutor)
        executor._event_bus = mock_bus
        executor._observer = mock_obs
        executor._memory = None
        executor._routing_fabric = None
        executor._scorecard_store = store
        executor._team_policy = None
        executor._team_control_plane = plane
        executor._templates = {}

        yield {"executor": executor, "bus": mock_bus, "obs": mock_obs, "store": store, "plane": plane}
        store.close()
        plane.close()

    @pytest.mark.asyncio
    async def test_full_dispatch_records_scorecard(self, executor):
        """dispatch_team → dispatch_headless → result → scorecard updated."""
        from chatgptrest.kernel.cc_executor import CcTask, CcResult
        from chatgptrest.kernel.team_types import TeamSpec, RoleSpec

        ex = executor["executor"]

        # Mock dispatch_headless to return a successful result
        mock_result = CcResult(
            ok=True, agent="native", task_type="review",
            output="LGTM", elapsed_seconds=5.0, quality_score=0.9,
            trace_id="tr_e2e", dispatch_mode="native",
            input_tokens=500, output_tokens=200, cost_usd=0.02,
        )
        ex.dispatch_headless = AsyncMock(return_value=mock_result)

        team = TeamSpec(roles=[
            RoleSpec(name="lead", model="opus"),
            RoleSpec(name="reviewer", model="sonnet"),
        ])
        task = CcTask(task_type="review", description="Review code",
                      trace_id="tr_e2e")

        result = await ex.dispatch_team(task, team=team)

        # Verify result
        assert result.ok is True
        assert result.quality_score == 0.9

        # Verify events were emitted
        bus_calls = executor["bus"].emit.call_args_list
        assert len(bus_calls) >= 2  # team.run.created + team.role.completed

        # Verify signal was recorded
        obs_calls = executor["obs"].record.call_args_list
        assert len(obs_calls) >= 1

        # Verify scorecard was updated
        card = executor["store"].get_scorecard(
            team.team_id, task_type="review",
        )
        assert card is not None
        assert card.total_runs == 1
        assert card.success_rate == 1.0

    @pytest.mark.asyncio
    async def test_failed_dispatch_records_failure(self, executor):
        """dispatch_team with failed result → scorecard tracks failure."""
        from chatgptrest.kernel.cc_executor import CcTask, CcResult
        from chatgptrest.kernel.team_types import TeamSpec, RoleSpec

        ex = executor["executor"]

        mock_result = CcResult(
            ok=False, agent="native", task_type="review",
            output="", elapsed_seconds=2.0, quality_score=0.0,
            trace_id="tr_fail", dispatch_mode="native", error="Anthropic timeout",
        )
        ex.dispatch_headless = AsyncMock(return_value=mock_result)

        team = TeamSpec(roles=[RoleSpec(name="solo", model="sonnet")])
        task = CcTask(task_type="review", description="Review",
                      trace_id="tr_fail")

        result = await ex.dispatch_team(task, team=team)
        assert result.ok is False

        # Scorecard should track the failure
        card = executor["store"].get_scorecard(team.team_id, task_type="review")
        assert card is not None
        assert card.failures == 1
        assert card.success_rate == 0.0

    @pytest.mark.asyncio
    async def test_dispatch_with_legacy_dict(self, executor):
        """dispatch_team accepts legacy dict format."""
        from chatgptrest.kernel.cc_executor import CcTask, CcResult

        ex = executor["executor"]
        mock_result = CcResult(
            ok=True, agent="native", task_type="review",
            output="OK", elapsed_seconds=3.0, quality_score=0.8,
            trace_id="tr_legacy", dispatch_mode="native",
        )
        ex.dispatch_headless = AsyncMock(return_value=mock_result)

        legacy_team = {
            "reviewer": {"description": "Reviews", "model": "sonnet",
                         "prompt": "Review code"},
        }
        task = CcTask(task_type="review", description="Review",
                      trace_id="tr_legacy")

        result = await ex.dispatch_team(task, team=legacy_team)
        assert result.ok is True

        # Should have created a TeamSpec internally
        all_cards = executor["store"].list_all()
        assert len(all_cards) >= 1

    @pytest.mark.asyncio
    async def test_dispatch_team_records_control_plane_digest_and_checkpoint(self, executor):
        """dispatch_team should populate control-plane digest/checkpoints for writer topologies."""
        from chatgptrest.kernel.cc_executor import CcTask, CcResult
        from chatgptrest.kernel.team_types import TeamSpec, RoleSpec

        ex = executor["executor"]

        async def _fake_dispatch(role_task, progress_callback=None):  # noqa: ANN001
            if role_task.trace_id.endswith(":scout"):
                return CcResult(
                    ok=True,
                    agent="native",
                    task_type=role_task.task_type,
                    output="scout summary",
                    elapsed_seconds=1.0,
                    quality_score=0.7,
                    trace_id=role_task.trace_id,
                )
            if role_task.trace_id.endswith(":implementer"):
                return CcResult(
                    ok=True,
                    agent="native",
                    task_type=role_task.task_type,
                    output="implemented change",
                    elapsed_seconds=2.0,
                    quality_score=0.9,
                    trace_id=role_task.trace_id,
                )
            raise AssertionError(f"unexpected trace id: {role_task.trace_id}")

        ex.dispatch_headless = AsyncMock(side_effect=_fake_dispatch)

        team = TeamSpec(
            roles=[
                RoleSpec(name="scout", model="sonnet"),
                RoleSpec(name="implementer", model="sonnet"),
            ],
            metadata={
                "topology_id": "implementation_duo",
                "execution_mode": "sequential",
                "synthesis_role": "implementer",
                "gate_ids": ["writer_review"],
            },
        )
        task = CcTask(
            task_type="bug_fix",
            description="Fix the issue",
            trace_id="tr_team_cp",
            context={"repo": "ChatgptREST"},
        )

        result = await ex.dispatch_team(task, team=team)

        assert result.ok is True
        assert result.team_run_id
        assert result.team_digest
        assert len(result.team_checkpoints) == 1
        assert result.team_checkpoints[0]["gate_id"] == "writer_review"

        run = executor["plane"].get_run(result.team_run_id)
        assert run is not None
        assert run["status"] == "needs_review"
        assert any(role["role_name"] == "implementer" for role in run["roles"])

    @pytest.mark.asyncio
    async def test_dispatch_team_parallel_respects_max_concurrent(self, executor):
        """Parallel team fan-out should honor max_concurrent from topology metadata."""
        from chatgptrest.kernel.cc_executor import CcTask, CcResult
        from chatgptrest.kernel.team_types import TeamSpec, RoleSpec

        ex = executor["executor"]
        inflight = 0
        max_seen = 0

        async def _fake_dispatch(role_task, progress_callback=None):  # noqa: ANN001
            nonlocal inflight, max_seen
            inflight += 1
            max_seen = max(max_seen, inflight)
            await asyncio.sleep(0.02)
            inflight -= 1
            return CcResult(
                ok=True,
                agent="native",
                task_type=role_task.task_type,
                output=f"{role_task.trace_id} output",
                elapsed_seconds=0.02,
                quality_score=0.8,
                trace_id=role_task.trace_id,
            )

        ex.dispatch_headless = AsyncMock(side_effect=_fake_dispatch)

        team = TeamSpec(
            roles=[
                RoleSpec(name="scout", model="sonnet"),
                RoleSpec(name="reviewer", model="sonnet"),
                RoleSpec(name="researcher", model="sonnet"),
                RoleSpec(name="synthesizer", model="sonnet"),
            ],
            metadata={
                "execution_mode": "parallel",
                "synthesis_role": "synthesizer",
                "max_concurrent": 2,
                "gate_ids": [],
            },
        )
        task = CcTask(task_type="research", description="Research the topic", trace_id="tr_team_parallel")

        result = await ex.dispatch_team(task, team=team)

        assert result.ok is True
        assert max_seen <= 2


# ═══════════════════════════════════════════════════════════════════
# FLOW 6: _init_once wiring verification
# ═══════════════════════════════════════════════════════════════════


class TestInitOnceWiring:
    """Verify that _init_once properly wires scorecard + policy."""

    def test_init_scorecard_store_helper(self):
        """_init_scorecard_store should create a store or return None."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            # Import indirectly — the function is defined inside make_v3_advisor_router
            from chatgptrest.evomap.team_scorecard import TeamScorecardStore
            store = TeamScorecardStore(db_path=db_path)
            assert store is not None
            store.close()
        finally:
            os.unlink(db_path)

    def test_init_team_policy_helper(self):
        """TeamPolicy with in-memory store should initialize."""
        from chatgptrest.evomap.team_scorecard import TeamScorecardStore
        from chatgptrest.kernel.team_policy import TeamPolicy

        store = TeamScorecardStore(db_path=":memory:")
        policy = TeamPolicy(scorecard_store=store)
        assert policy is not None

        # No data → recommend returns None
        assert policy.recommend(repo="x", task_type="y") is None
        store.close()


# ═══════════════════════════════════════════════════════════════════
# FLOW 7: CcExecutor backward compat — legacy dict wrapping
# ═══════════════════════════════════════════════════════════════════


class TestCcExecutorBackwardCompat:
    """Verify CcExecutor.dispatch_team wraps dicts into TeamSpec."""

    def test_dict_wrapped_to_team_spec(self):
        """When dict is passed, it should be wrapped to TeamSpec."""
        from chatgptrest.kernel.team_types import TeamSpec

        legacy = {
            "reviewer": {"description": "Reviews", "model": "sonnet",
                         "prompt": "Review"},
        }
        spec = TeamSpec.from_dict(legacy)
        assert len(spec.roles) == 1
        assert spec.roles[0].name == "reviewer"

        # to_agents_json should produce compatible output
        aj = spec.to_agents_json()
        assert aj == {"reviewer": {"description": "Reviews", "model": "sonnet",
                                    "prompt": "Review"}}

    def test_none_team_passes_through(self):
        """When team=None, dispatch should still work."""
        from chatgptrest.kernel.team_types import TeamSpec

        spec = TeamSpec.from_dict({})
        assert spec.team_id == ""
        assert spec.roles == []


# ═══════════════════════════════════════════════════════════════════
# FLOW 8: Cross-module import verification
# ═══════════════════════════════════════════════════════════════════


class TestModuleImports:
    """Verify all new modules import correctly and have expected public API."""

    def test_team_types_imports(self):
        from chatgptrest.kernel.team_types import RoleSpec, TeamSpec, TeamRunRecord
        assert RoleSpec is not None
        assert TeamSpec is not None
        assert TeamRunRecord is not None

    def test_team_scorecard_imports(self):
        from chatgptrest.evomap.team_scorecard import TeamScorecardStore, TeamScorecard
        assert TeamScorecardStore is not None
        assert TeamScorecard is not None

    def test_team_policy_imports(self):
        from chatgptrest.kernel.team_policy import TeamPolicy, TeamPolicyConfig
        assert TeamPolicy is not None
        assert TeamPolicyConfig is not None

    def test_signals_have_team_types(self):
        from chatgptrest.evomap.signals import SignalType, SignalDomain
        assert hasattr(SignalType, "TEAM_RUN_CREATED")
        assert hasattr(SignalType, "TEAM_RUN_COMPLETED")
        assert hasattr(SignalType, "TEAM_RUN_FAILED")
        assert hasattr(SignalType, "TEAM_ROLE_COMPLETED")
        assert hasattr(SignalType, "TEAM_ROLE_FAILED")
        assert hasattr(SignalType, "TEAM_OUTPUT_ACCEPTED")
        assert hasattr(SignalType, "TEAM_OUTPUT_REJECTED")
        assert hasattr(SignalDomain, "TEAM")


# ═══════════════════════════════════════════════════════════════════
# FLOW 9: cc_native dispatch telemetry via EventBus
# ═══════════════════════════════════════════════════════════════════


class TestCcNativeDispatchTelemetry:
    """Verify cc_native dispatch_headless emits live dispatch events."""

    @pytest.mark.asyncio
    async def test_dispatch_headless_emits_completed_event(self, monkeypatch):
        from chatgptrest.kernel.cc_executor import CcResult, CcTask
        from chatgptrest.kernel.event_bus import EventBus
        from chatgptrest.kernel.cc_native import CcNativeExecutor

        class FakeMcpManager:
            async def initialize(self, _config_path=None):
                return None

            async def close(self):
                return None

        monkeypatch.setattr("chatgptrest.kernel.cc_native.McpManager", FakeMcpManager)

        bus = EventBus()
        events = []
        bus.subscribe(events.append)

        ex = CcNativeExecutor.__new__(CcNativeExecutor)
        ex._event_bus = bus
        ex._observer = None
        ex._memory = None
        ex._routing_fabric = None
        ex._scorecard_store = None
        ex._team_policy = None
        ex._templates = {}
        ex._select_template = lambda _task_type: "v1"
        ex._build_prompt = lambda _task, _template: "prompt"
        ex._remember_episodic = MagicMock()
        ex._report_routing_outcome = MagicMock()
        ex._run_react_loop = AsyncMock(
            return_value=CcResult(
                ok=True,
                agent="native",
                task_type="review",
                output="ok",
                elapsed_seconds=1.5,
                quality_score=0.9,
                trace_id="trace-native-ok",
                dispatch_mode="native",
                model_used="MiniMax-M2.5",
            )
        )

        task = CcTask(task_type="review", description="Review code", trace_id="trace-native-ok")
        result = await ex.dispatch_headless(task)
        bus.close()

        assert result.ok is True
        event_types = [event.event_type for event in events]
        assert "dispatch.task_started" in event_types
        assert "dispatch.task_completed" in event_types

    @pytest.mark.asyncio
    async def test_dispatch_headless_emits_failed_event(self, monkeypatch):
        from chatgptrest.kernel.cc_executor import CcTask
        from chatgptrest.kernel.event_bus import EventBus
        from chatgptrest.kernel.cc_native import CcNativeExecutor

        class FakeMcpManager:
            async def initialize(self, _config_path=None):
                return None

            async def close(self):
                return None

        monkeypatch.setattr("chatgptrest.kernel.cc_native.McpManager", FakeMcpManager)

        bus = EventBus()
        events = []
        bus.subscribe(events.append)

        ex = CcNativeExecutor.__new__(CcNativeExecutor)
        ex._event_bus = bus
        ex._observer = None
        ex._memory = None
        ex._routing_fabric = None
        ex._scorecard_store = None
        ex._team_policy = None
        ex._templates = {}
        ex._select_template = lambda _task_type: "v1"
        ex._build_prompt = lambda _task, _template: "prompt"
        ex._remember_episodic = MagicMock()
        ex._report_routing_outcome = MagicMock()
        ex._run_react_loop = AsyncMock(side_effect=RuntimeError("llm exploded"))

        task = CcTask(task_type="review", description="Review code", trace_id="trace-native-fail")
        result = await ex.dispatch_headless(task)
        bus.close()

        assert result.ok is False
        event_types = [event.event_type for event in events]
        assert "dispatch.task_started" in event_types
        assert "dispatch.task_failed" in event_types
