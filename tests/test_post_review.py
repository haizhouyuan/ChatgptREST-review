"""Tests for post-ask review generation."""

import pytest

from chatgptrest.advisor.post_review import (
    PostAskReview,
    generate_basic_review,
)
from chatgptrest.advisor.ask_contract import (
    AskContract,
    TaskTemplate,
    RiskClass,
)


class TestPostAskReview:
    """Test PostAskReview dataclass."""

    def test_default_review(self):
        """Test default review values."""
        review = PostAskReview()
        assert review.question_quality == "unknown"
        assert review.contract_completeness == 0.0
        assert review.actionability == "unknown"

    def test_to_dict(self):
        """Test review serialization."""
        review = PostAskReview(
            question_quality="good",
            contract_completeness=0.8,
            actionability="high",
        )
        d = review.to_dict()
        assert d["question_quality"] == "good"
        assert d["contract_completeness"] == 0.8
        assert d["actionability"] == "high"

    def test_from_dict(self):
        """Test review deserialization."""
        data = {
            "question_quality": "excellent",
            "contract_completeness": 0.9,
        }
        review = PostAskReview.from_dict(data)
        assert review.question_quality == "excellent"
        assert review.contract_completeness == 0.9


class TestGenerateBasicReview:
    """Test basic review generation."""

    def test_review_with_complete_contract(self):
        """Test review generation with complete contract."""
        contract = AskContract(
            objective="What is machine learning?",
            decision_to_support="Understanding ML",
            audience="Students",
            output_shape="Explanation",
            constraints="Be concise",
            task_template=TaskTemplate.RESEARCH.value,
            contract_completeness=0.8,
        )

        answer = """## Machine Learning

Machine learning is a subset of artificial intelligence that enables
systems to learn from data without being explicitly programmed.

### Key Points
1. **Supervised Learning** - Learning from labeled data
2. **Unsupervised Learning** - Finding patterns in unlabeled data
3. **Reinforcement Learning** - Learning through trial and error

### Conclusion
Machine learning is fundamental to modern AI applications."""

        review = generate_basic_review(
            contract=contract,
            answer=answer,
            route="research",
            provider="chatgpt",
        )

        assert review.question_quality in {"excellent", "good", "fair"}
        assert review.contract_completeness >= 0.7
        assert review.route_fit in {"excellent", "good"}
        assert review.model_fit in {"excellent", "good", "fair"}
        assert review.answer_length_adequate
        assert review.answer_has_structure
        assert review.has_actionable_steps

    def test_review_with_incomplete_contract(self):
        """Test review with incomplete contract."""
        contract = AskContract(
            objective="Test",
            contract_completeness=0.3,
        )

        answer = "Short answer."

        review = generate_basic_review(
            contract=contract,
            answer=answer,
            route="quick_ask",
            provider="chatgpt",
        )

        assert review.contract_completeness < 0.5
        assert len(review.missing_info_detected) > 0

    def test_review_high_risk(self):
        """Test review for high-risk request."""
        contract = AskContract(
            objective="Critical decision",
            decision_to_support="Production deployment",
            audience="CTO",
            risk_class=RiskClass.HIGH.value,
        )

        review = generate_basic_review(
            contract=contract,
            answer="Recommendation: Deploy to production.",
            route="consult",
            provider="gpt-4",
        )

        assert review.model_fit in {"excellent", "good"}

    def test_review_session_trace_ids(self):
        """Test review includes session and trace IDs."""
        contract = AskContract(objective="Test")

        review = generate_basic_review(
            contract=contract,
            answer="Test answer",
            route="quick_ask",
            provider="chatgpt",
            session_id="test_session_123",
            trace_id="trace_abc",
        )

        assert review.session_id == "test_session_123"
        assert review.trace_id == "trace_abc"

    def test_review_short_answer(self):
        """Test review with short answer."""
        contract = AskContract(objective="Test")

        review = generate_basic_review(
            contract=contract,
            answer="OK",
            route="quick_ask",
            provider="chatgpt",
        )

        assert not review.answer_length_adequate
        assert review.answer_quality == "poor"

    def test_review_structured_answer(self):
        """Test review with structured answer."""
        contract = AskContract(objective="Test")

        answer = """## Summary

This is a comprehensive summary of the topic.

1. First point - This is a detailed explanation of the first point
2. Second point - This provides more information about the second point
3. Third point - Additional details about the third point

### Details
More information here. This section provides additional context and details
about the main points discussed above. The information is organized in a
clear and structured manner for easy understanding."""

        review = generate_basic_review(
            contract=contract,
            answer=answer,
            route="quick_ask",
            provider="chatgpt",
        )

        assert review.answer_has_structure
        assert review.answer_length_adequate
