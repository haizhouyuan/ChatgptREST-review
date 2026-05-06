#!/usr/bin/env python3
"""Eval CLI — run evaluation on advisor models.

Usage:
    python scripts/run_eval.py --dataset default
    python scripts/run_eval.py --dataset default --scorers rouge,similarity
    python scripts/run_eval.py --compare baseline.json new_model.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from chatgptrest.eval.harness import EvalHarness, load_dataset_builtin
from chatgptrest.eval.scorers import RougeScorer, SemanticSimilarityScorer, LLMJudgeScorer


def parse_args():
    parser = argparse.ArgumentParser(description="Run evaluation on advisor models")
    parser.add_argument(
        "--dataset",
        default="default",
        help="Dataset name (default, or path to JSON file)",
    )
    parser.add_argument(
        "--scorers",
        default="rouge,similarity",
        help="Comma-separated scorer names (rouge,similarity,llm_judge)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output JSON file for results",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("REPORT_A", "REPORT_B"),
        help="Compare two JSON report files",
    )
    return parser.parse_args()


def load_scorers(scorer_names: str) -> list:
    """Load scorers by name."""
    scorers = []
    for name in scorer_names.split(","):
        name = name.strip().lower()
        if name == "rouge":
            scorers.append(RougeScorer())
        elif name == "similarity":
            scorers.append(SemanticSimilarityScorer())
        elif name == "llm_judge":
            scorers.append(LLMJudgeScorer())
    return scorers


def load_dataset(name: str):
    """Load dataset by name or path."""
    path = Path(name)
    if path.exists() and path.suffix == ".json":
        from chatgptrest.eval.datasets import EvalDataset
        return EvalDataset.from_file(path)
    return load_dataset_builtin(name)


def run_evaluation(args):
    """Run evaluation and output results."""
    # Load dataset
    dataset = load_dataset(args.dataset)
    print(f"Loaded dataset: {dataset.name} ({len(dataset)} items)")

    # Load scorers
    scorers = load_scorers(args.scorers)
    print(f"Scorers: {[s.name for s in scorers]}")

    # Create harness
    harness = EvalHarness(dataset, scorers)

    # Simple mock advisor for demonstration
    def mock_advisor(input_text: str) -> str:
        """Mock advisor - returns simple response."""
        # In real usage, this would call the actual advisor
        return f"Response to: {input_text[:50]}..."

    # Run evaluation
    print("\nRunning evaluation...")
    report = harness.run(mock_advisor, verbose=args.verbose)

    # Output results
    print(f"\n=== Evaluation Results ===")
    print(f"Dataset: {report.dataset_name}")
    print(f"Items: {report.num_items}, Success: {report.num_success}, Errors: {report.num_errors}")
    print(f"\nAverage Scores:")
    for name, score in report.avg_scores.items():
        print(f"  {name}: {score:.4f}")

    # Output to file if requested
    if args.output:
        output_data = {
            "dataset_name": report.dataset_name,
            "num_items": report.num_items,
            "num_success": report.num_success,
            "num_errors": report.num_errors,
            "avg_scores": report.avg_scores,
            "timestamp": report.timestamp,
            "item_results": [
                {
                    "input": r.item.input,
                    "prediction": r.prediction,
                    "scores": r.scores,
                    "error": r.error,
                }
                for r in report.item_results
            ],
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to: {args.output}")

    return report


def compare_reports(args):
    """Compare two evaluation reports."""
    with open(args.compare[0], encoding="utf-8") as f:
        report_a_data = json.load(f)
    with open(args.compare[1], encoding="utf-8") as f:
        report_b_data = json.load(f)

    from chatgptrest.eval.harness import EvalReport, ItemResult
    from chatgptrest.eval.datasets import EvalItem

    # Convert back to EvalReport
    report_a = EvalReport(
        dataset_name=report_a_data["dataset_name"],
        num_items=report_a_data["num_items"],
        num_success=report_a_data["num_success"],
        num_errors=report_a_data["num_errors"],
        item_results=[],
        scorer_names=list(report_a_data.get("avg_scores", {}).keys()),
        avg_scores=report_a_data["avg_scores"],
        timestamp=report_a_data.get("timestamp", ""),
    )
    report_b = EvalReport(
        dataset_name=report_b_data["dataset_name"],
        num_items=report_b_data["num_items"],
        num_success=report_b_data["num_success"],
        num_errors=report_b_data["num_errors"],
        item_results=[],
        scorer_names=list(report_b_data.get("avg_scores", {}).keys()),
        avg_scores=report_b_data["avg_scores"],
        timestamp=report_b_data.get("timestamp", ""),
    )

    # Calculate deltas
    deltas = {}
    for scorer_name in report_a.avg_scores:
        score_a = report_a.avg_scores.get(scorer_name, 0.0)
        score_b = report_b.avg_scores.get(scorer_name, 0.0)
        deltas[scorer_name] = round(score_b - score_a, 4)

    # Print comparison
    print(f"\n=== Comparison Report ===")
    print(f"Report A: {report_a.dataset_name}")
    print(f"Report B: {report_b.dataset_name}")
    print(f"\nScore Deltas (B - A):")
    for name, delta in deltas.items():
        sign = "+" if delta > 0 else ""
        print(f"  {name}: {sign}{delta:.4f}")

    return deltas


def main():
    args = parse_args()

    if args.compare:
        compare_reports(args)
    else:
        run_evaluation(args)


if __name__ == "__main__":
    main()
