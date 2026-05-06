"""Tests for Eval Harness module."""

import pytest
from chatgptrest.eval.datasets import EvalDataset, EvalItem
from chatgptrest.eval.scorers import RougeScorer, SemanticSimilarityScorer
from chatgptrest.eval.harness import EvalHarness, load_dataset_builtin


def test_load_dataset_builtin():
    """Test loading built-in default dataset."""
    dataset = load_dataset_builtin("default")
    assert len(dataset) == 10
    assert dataset.name == "default"


def test_eval_item():
    """Test EvalItem creation."""
    item = EvalItem(
        input="test input",
        expected_intent="query",
        expected_route="funnel",
        reference_answer="expected output"
    )
    assert item.input == "test input"
    assert item.expected_route == "funnel"


def test_eval_dataset_from_dict():
    """Test creating dataset from items."""
    items = [
        EvalItem(input="q1", reference_answer="a1"),
        EvalItem(input="q2", reference_answer="a2"),
    ]
    dataset = EvalDataset(name="test", items=items)
    assert len(dataset) == 2


def test_eval_dataset_save_load(tmp_path):
    """Test saving and loading dataset."""
    items = [
        EvalItem(input="q1", reference_answer="a1"),
    ]
    dataset = EvalDataset(name="test", items=items)

    # Save
    path = tmp_path / "test.json"
    dataset.save(str(path))

    # Load
    loaded = EvalDataset.from_file(str(path))
    assert len(loaded) == 1
    assert loaded.name == "test"


def test_rouge_scorer():
    """Test ROUGE scorer."""
    scorer = RougeScorer()
    score = scorer.score("hello world", "hello world")
    assert score == 1.0

    score = scorer.score("hello world", "goodbye world")
    assert 0 < score < 1


def test_semantic_similarity_scorer():
    """Test semantic similarity scorer."""
    scorer = SemanticSimilarityScorer()
    score = scorer.score("The cat sat on the mat", "A cat was sitting on a rug")
    assert 0 <= score <= 1.0


def test_harness_run():
    """Test running evaluation harness."""
    items = [
        EvalItem(input="q1", reference_answer="a1"),
        EvalItem(input="q2", reference_answer="a2"),
    ]
    dataset = EvalDataset(name="test", items=items)
    scorers = [RougeScorer()]
    harness = EvalHarness(dataset, scorers)

    def mock_advisor(input_text: str) -> str:
        return "a1" if "q1" in input_text else "a2"

    report = harness.run(mock_advisor)
    assert report.num_items == 2
    assert report.num_success == 2
    assert "rouge_l" in report.avg_scores


def test_harness_compare():
    """Test comparing two reports."""
    items = [
        EvalItem(input="q1", reference_answer="a1"),
    ]
    dataset = EvalDataset(name="test", items=items)
    scorers = [RougeScorer()]
    harness = EvalHarness(dataset, scorers)

    def mock_advisor_a(_):
        return "wrong"
    def mock_advisor_b(_):
        return "a1"

    report_a = harness.run(mock_advisor_a)
    report_b = harness.run(mock_advisor_b)

    comparison = harness.compare(report_a, report_b)
    assert comparison.winner == "b"
    assert comparison.score_deltas["rouge_l"] > 0


def test_harness_error_handling():
    """Test error handling in harness."""
    items = [
        EvalItem(input="q1", reference_answer="a1"),
    ]
    dataset = EvalDataset(name="test", items=items)
    scorers = [RougeScorer()]
    harness = EvalHarness(dataset, scorers)

    def broken_advisor(_):
        raise ValueError("Simulated error")

    report = harness.run(broken_advisor)
    assert report.num_errors == 1
    assert report.num_success == 0
