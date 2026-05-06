"""Tests for chatgptrest/kernel/team_policy.py — policy-aware team routing."""

import random
import pytest
from chatgptrest.kernel.team_policy import TeamPolicy, TeamPolicyConfig
from chatgptrest.evomap.team_scorecard import TeamScorecardStore
from chatgptrest.kernel.team_types import TeamSpec, TeamRunRecord, RoleSpec


@pytest.fixture
def store():
    s = TeamScorecardStore(db_path=":memory:")
    yield s
    s.close()


def _seed_team(store, team_id_suffix, quality, ok_count, fail_count, repo="test", task_type="review"):
    """Seed a team with some run history."""
    spec = TeamSpec(roles=[RoleSpec(name=f"agent_{team_id_suffix}", model="sonnet")])
    for _ in range(ok_count):
        r = TeamRunRecord(
            team_spec=spec, repo=repo, task_type=task_type,
            result_ok=True, quality_score=quality, cost_usd=0.01,
        )
        store.record_outcome(r)
    for _ in range(fail_count):
        r = TeamRunRecord(
            team_spec=spec, repo=repo, task_type=task_type,
            result_ok=False, quality_score=0.0, cost_usd=0.01,
        )
        store.record_outcome(r)
    return spec


class TestTeamPolicy:
    def test_no_store_returns_none(self):
        policy = TeamPolicy(scorecard_store=None)
        assert policy.recommend(repo="x", task_type="y") is None

    def test_no_history_returns_none(self, store):
        policy = TeamPolicy(scorecard_store=store)
        assert policy.recommend(repo="x", task_type="y") is None

    def test_insufficient_runs_returns_none(self, store):
        """Teams with fewer than min_runs_for_confidence should not be recommended."""
        spec = TeamSpec(roles=[RoleSpec(name="solo", model="sonnet")])
        # Only 1 run, below default min_runs_for_confidence=3
        r = TeamRunRecord(
            team_spec=spec, repo="test", task_type="review",
            result_ok=True, quality_score=1.0, cost_usd=0.01,
        )
        store.record_outcome(r)

        policy = TeamPolicy(scorecard_store=store, config=TeamPolicyConfig(min_runs_for_confidence=3))
        assert policy.recommend(repo="test", task_type="review") is None

    def test_recommends_best_team(self, store):
        """Should recommend the team with the highest composite score."""
        # Team A: great
        _seed_team(store, "A", quality=0.9, ok_count=5, fail_count=0)
        # Team B: mediocre
        _seed_team(store, "B", quality=0.4, ok_count=3, fail_count=2)

        policy = TeamPolicy(
            scorecard_store=store,
            config=TeamPolicyConfig(exploration_rate=0.0),  # no exploration
        )
        recommended = policy.recommend(repo="test", task_type="review")
        assert recommended is not None
        assert len(recommended.roles) > 0
        # Should be team A (agent_A)
        assert recommended.roles[0].name == "agent_A"

    def test_below_threshold_returns_none(self, store):
        """Teams below auto_team_threshold should not be recommended."""
        _seed_team(store, "bad", quality=0.1, ok_count=1, fail_count=4)

        policy = TeamPolicy(
            scorecard_store=store,
            config=TeamPolicyConfig(
                auto_team_threshold=0.5,
                min_runs_for_confidence=3,
            ),
        )
        assert policy.recommend(repo="test", task_type="review") is None

    def test_exploration_mode(self, store):
        """With exploration_rate=1.0, should still return an eligible team."""
        _seed_team(store, "A", quality=0.9, ok_count=5, fail_count=0)
        _seed_team(store, "B", quality=0.7, ok_count=5, fail_count=0)

        rng = random.Random(42)
        policy = TeamPolicy(
            scorecard_store=store,
            config=TeamPolicyConfig(exploration_rate=1.0),
            rng=rng,
        )
        recommended = policy.recommend(repo="test", task_type="review")
        assert recommended is not None  # Should still get something

    def test_blacklist_threshold(self, store):
        """Teams below blacklist_threshold should never be returned."""
        _seed_team(store, "terrible", quality=0.0, ok_count=1, fail_count=9)

        policy = TeamPolicy(
            scorecard_store=store,
            config=TeamPolicyConfig(
                auto_team_threshold=0.0,  # accept any
                blacklist_threshold=0.2,
                min_runs_for_confidence=3,
            ),
        )
        assert policy.recommend(repo="test", task_type="review") is None
