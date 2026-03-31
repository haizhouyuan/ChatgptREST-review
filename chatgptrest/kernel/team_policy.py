"""TeamPolicy — data-driven team selection for dispatch.

Consults the TeamScorecardStore to decide:
  - Whether to use team mode or single-agent mode
  - Which team composition to recommend
  - With configurable exploration for discovering new team layouts

Usage::

    policy = TeamPolicy(scorecard_store=store)
    recommended = policy.recommend(repo="chatgptrest", task_type="code_review")
    if recommended:
        result = await cc.dispatch_team(task, team=recommended)
    else:
        result = await cc.dispatch_headless(task)
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TeamPolicyConfig:
    """Configuration for team selection policy.

    Attributes:
        auto_team_threshold: Minimum composite score to auto-select a team.
            Teams below this are not recommended.
        exploration_rate: Fraction of requests sent to a random known team
            instead of the best, for discovering better compositions.
        blacklist_threshold: Score below which a team is never auto-selected.
        min_runs_for_confidence: Minimum number of runs before a team's
            scorecard is considered reliable for ranking.
    """
    auto_team_threshold: float = 0.5
    exploration_rate: float = 0.1
    blacklist_threshold: float = 0.2
    min_runs_for_confidence: int = 3


class TeamPolicy:
    """Data-driven team selection policy.

    Given a repo + task_type, consults the scorecard store to recommend
    the best team composition. Supports exploration mode.
    """

    def __init__(
        self,
        scorecard_store: Any = None,
        config: TeamPolicyConfig | None = None,
        rng: random.Random | None = None,
    ):
        self._store = scorecard_store
        self._config = config or TeamPolicyConfig()
        self._rng = rng or random.Random()

    def recommend(
        self,
        repo: str = "",
        task_type: str = "",
    ) -> "TeamSpec | None":
        """Recommend a team for a repo/task combination.

        Returns:
            TeamSpec if a team should be used, None for single-agent mode.
        """
        if not self._store:
            return None

        from chatgptrest.kernel.team_types import TeamSpec

        candidates = self._store.rank_teams(
            repo=repo, task_type=task_type, limit=10,
        )

        if not candidates:
            return None

        # Filter: require minimum runs for confidence
        confident = [
            c for c in candidates
            if c.total_runs >= self._config.min_runs_for_confidence
        ]

        if not confident:
            return None

        # Filter: above threshold
        eligible = [
            c for c in confident
            if c.composite_score >= self._config.auto_team_threshold
        ]

        if not eligible:
            return None

        # Exploration: with some probability, pick a random eligible team
        if (
            len(eligible) > 1
            and self._rng.random() < self._config.exploration_rate
        ):
            chosen = self._rng.choice(eligible)
        else:
            chosen = eligible[0]  # best by composite score

        # Blacklist check (shouldn't happen since we filtered, but be safe)
        if chosen.composite_score < self._config.blacklist_threshold:
            return None

        # Reconstruct TeamSpec from stored JSON
        import json
        try:
            spec_data = json.loads(chosen.team_spec_json)
            return TeamSpec.from_dict(spec_data)
        except Exception as e:
            logger.debug("TeamPolicy: failed to reconstruct TeamSpec: %s", e)
            return None
