"""Tests for chatgptrest/evomap/team_scorecard.py — scorecard persistence."""

import pytest
from chatgptrest.evomap.team_scorecard import TeamScorecardStore, TeamScorecard
from chatgptrest.kernel.team_types import TeamSpec, TeamRunRecord, RoleSpec


@pytest.fixture
def store():
    """In-memory scorecard store for testing."""
    s = TeamScorecardStore(db_path=":memory:")
    yield s
    s.close()


def _make_run(ok=True, quality=0.8, elapsed=10.0, cost=0.05, task_type="review"):
    spec = TeamSpec(roles=[
        RoleSpec(name="lead", model="opus"),
        RoleSpec(name="coder", model="sonnet"),
    ])
    r = TeamRunRecord(
        team_spec=spec,
        trace_id="tr_test",
        task_type=task_type,
        repo="chatgptrest",
        result_ok=ok,
        elapsed_seconds=elapsed,
        quality_score=quality,
        total_input_tokens=1000,
        total_output_tokens=500,
        cost_usd=cost,
    )
    return r


class TestScorecardStore:
    def test_record_creates_scorecard(self, store):
        run = _make_run()
        store.record_outcome(run)
        sc = store.get_scorecard(
            run.team_spec.team_id, repo="chatgptrest", task_type="review",
        )
        assert sc is not None
        assert sc.total_runs == 1
        assert sc.successes == 1
        assert sc.failures == 0

    def test_record_increments(self, store):
        run1 = _make_run(ok=True, quality=0.9)
        run2 = _make_run(ok=False, quality=0.3)
        store.record_outcome(run1)
        store.record_outcome(run2)
        sc = store.get_scorecard(
            run1.team_spec.team_id, repo="chatgptrest", task_type="review",
        )
        assert sc.total_runs == 2
        assert sc.successes == 1
        assert sc.failures == 1

    def test_avg_quality(self, store):
        store.record_outcome(_make_run(quality=0.8))
        store.record_outcome(_make_run(quality=0.6))
        sc = store.get_scorecard(
            _make_run().team_spec.team_id, repo="chatgptrest", task_type="review",
        )
        assert abs(sc.avg_quality - 0.7) < 0.01

    def test_rank_teams(self, store):
        # Team A: good
        for _ in range(3):
            store.record_outcome(_make_run(ok=True, quality=0.9))

        # Team B: mediocre
        spec_b = TeamSpec(roles=[RoleSpec(name="solo", model="haiku")])
        for _ in range(3):
            r = TeamRunRecord(
                team_spec=spec_b, repo="chatgptrest",
                task_type="review", result_ok=True,
                quality_score=0.4, cost_usd=0.01,
            )
            store.record_outcome(r)

        ranked = store.rank_teams(repo="chatgptrest", task_type="review")
        assert len(ranked) == 2
        assert ranked[0].composite_score >= ranked[1].composite_score

    def test_no_spec_skipped(self, store):
        r = TeamRunRecord(team_spec=None)
        store.record_outcome(r)  # Should not crash
        assert store.list_all() == []

    def test_get_nonexistent(self, store):
        assert store.get_scorecard("nonexistent") is None

    def test_list_all(self, store):
        store.record_outcome(_make_run())
        all_cards = store.list_all()
        assert len(all_cards) == 1


class TestTeamScorecard:
    def test_composite_score(self):
        sc = TeamScorecard(total_runs=10, successes=8, avg_quality=0.7)
        # 0.6 * 0.8 + 0.4 * 0.7 = 0.48 + 0.28 = 0.76
        assert abs(sc.composite_score - 0.76) < 0.01

    def test_zero_runs(self):
        sc = TeamScorecard(total_runs=0)
        assert sc.composite_score == 0.0
        assert sc.success_rate == 0.0
