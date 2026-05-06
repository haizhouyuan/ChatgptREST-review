"""Eval Harness — core evaluation orchestration."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from chatgptrest.eval.datasets import EvalDataset, EvalItem
from chatgptrest.eval.scorers import Scorer

logger = logging.getLogger(__name__)


@dataclass
class ItemResult:
    """Result for a single eval item."""
    item: EvalItem
    prediction: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    error: str = ""


@dataclass
class EvalReport:
    """Complete evaluation report."""
    dataset_name: str
    num_items: int
    num_success: int
    num_errors: int
    item_results: list[ItemResult]
    scorer_names: list[str]
    avg_scores: dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ComparisonReport:
    """Comparison between two eval reports."""
    report_a: EvalReport
    report_b: EvalReport
    score_deltas: dict[str, float] = field(default_factory=dict)
    winner: str = ""


class EvalHarness:
    """Standardized evaluation harness.

    Usage::

        dataset = EvalDataset.from_file("eval_datasets/default.json")
        scorers = [RougeScorer(), SemanticSimilarityScorer()]
        harness = EvalHarness(dataset, scorers)

        # Define your advisor function
        def my_advisor(input_text: str) -> str:
            return "Model output here..."

        report = harness.run(my_advisor)
        print(report.avg_scores)

        # Compare two reports
        report2 = harness.run(other_advisor)
        comparison = harness.compare(report, report2)
    """

    def __init__(self, dataset: EvalDataset, scorers: list[Scorer]) -> None:
        self.dataset = dataset
        self.scorers = scorers

    def run(
        self,
        advisor_fn: Callable[[str], str],
        *,
        verbose: bool = False,
    ) -> EvalReport:
        """Run evaluation on all items.

        Args:
            advisor_fn: Function that takes input text and returns prediction
            verbose: Print progress

        Returns:
            EvalReport with scores
        """
        results: list[ItemResult] = []
        scorer_names = [s.name for s in self.scorers]
        success_count = 0
        error_count = 0

        for i, item in enumerate(self.dataset):
            if verbose:
                print(f"Evaluating {i+1}/{len(self.dataset)}: {item.input[:50]}...")

            try:
                prediction = advisor_fn(item.input)
                scores = {}

                for scorer in self.scorers:
                    try:
                        score = scorer.score(prediction, item.reference_answer)
                        scores[scorer.name] = round(score, 4)
                    except Exception as e:
                        logger.warning(f"Scorer {scorer.name} failed: {e}")
                        scores[scorer.name] = 0.0

                results.append(ItemResult(
                    item=item,
                    prediction=prediction,
                    scores=scores,
                ))
                success_count += 1

            except Exception as e:
                logger.error(f"Error on item {i}: {e}")
                results.append(ItemResult(
                    item=item,
                    prediction="",
                    scores={},
                    error=str(e),
                ))
                error_count += 1

        # Calculate averages
        avg_scores: dict[str, float] = {}
        for scorer in self.scorers:
            scores_for_scorer = [
                r.scores.get(scorer.name, 0.0)
                for r in results if r.scores
            ]
            if scores_for_scorer:
                avg_scores[scorer.name] = round(sum(scores_for_scorer) / len(scores_for_scorer), 4)

        return EvalReport(
            dataset_name=self.dataset.name,
            num_items=len(results),
            num_success=success_count,
            num_errors=error_count,
            item_results=results,
            scorer_names=scorer_names,
            avg_scores=avg_scores,
        )

    def compare(self, report_a: EvalReport, report_b: EvalReport) -> ComparisonReport:
        """Compare two evaluation reports.

        Args:
            report_a: First report (typically baseline)
            report_b: Second report (typically new model)

        Returns:
            ComparisonReport with deltas
        """
        deltas: dict[str, float] = {}

        for scorer_name in report_a.scorer_names:
            score_a = report_a.avg_scores.get(scorer_name, 0.0)
            score_b = report_b.avg_scores.get(scorer_name, 0.0)
            deltas[scorer_name] = round(score_b - score_a, 4)

        # Determine winner (best average across all scorers)
        total_a = sum(report_a.avg_scores.values())
        total_b = sum(report_b.avg_scores.values())

        winner = "tie"
        if total_b > total_a:
            winner = "b"
        elif total_a > total_b:
            winner = "a"

        return ComparisonReport(
            report_a=report_a,
            report_b=report_b,
            score_deltas=deltas,
            winner=winner,
        )


def load_dataset_builtin(name: str = "default") -> EvalDataset:
    """Load a built-in dataset.

    Args:
        name: Dataset name (e.g., "default", "routing", "quality")

    Returns:
        EvalDataset
    """
    # Built-in default dataset (10 items)
    if name == "default":
        items = [
            EvalItem(
                input="What is the status of the 安徽 project?",
                expected_route="funnel",
                reference_answer="The 安徽 project is in progress with phase 2 completed."
            ),
            EvalItem(
                input="Show me the Q3 financial report",
                expected_route="report",
                reference_answer="Here is the Q3 financial report summary..."
            ),
            EvalItem(
                input="How do I configure the API?",
                expected_route="kb_answer",
                reference_answer="To configure the API, edit the config.yaml file..."
            ),
            EvalItem(
                input="Build a feature to track user login",
                expected_route="build",
                reference_answer="I'll create a login tracking feature with the following components..."
            ),
            EvalItem(
                input="What's the weather like?",
                expected_route="funnel",
                reference_answer="I can help you with project management, documentation, and development tasks."
            ),
            EvalItem(
                input="Find all documents about security",
                expected_route="kb_probe",
                reference_answer="Found 5 security-related documents in the knowledge base."
            ),
            EvalItem(
                input="Write a test for the user service",
                expected_route="build",
                reference_answer="Here is a test file for the user service..."
            ),
            EvalItem(
                input="What meetings do I have today?",
                expected_route="funnel",
                reference_answer="You have 3 meetings scheduled for today."
            ),
            EvalItem(
                input="Explain how the cache works",
                expected_route="kb_answer",
                reference_answer="The cache system works by storing frequently accessed data in memory..."
            ),
            EvalItem(
                input="Create a bug report for the login issue",
                expected_route="funnel",
                reference_answer="Bug report created: Login issue on production environment."
            ),
        ]
        return EvalDataset(name="default", items=items)

    raise ValueError(f"Unknown dataset: {name}")
