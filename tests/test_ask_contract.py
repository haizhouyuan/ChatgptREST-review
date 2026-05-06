"""Tests for ask contract schema and normalization."""

import pytest

from chatgptrest.advisor.ask_contract import (
    AskContract,
    normalize_ask_contract,
    RiskClass,
    TaskTemplate,
)


class TestAskContract:
    """Test AskContract dataclass."""

    def test_default_contract(self):
        """Test default contract values."""
        contract = AskContract()
        assert contract.objective == ""
        assert contract.decision_to_support == ""
        assert contract.audience == ""
        assert contract.risk_class == RiskClass.MEDIUM.value
        assert contract.task_template == TaskTemplate.GENERAL.value
        assert contract.contract_source == "server_synthesized"

    def test_to_dict(self):
        """Test contract serialization."""
        contract = AskContract(
            objective="Test objective",
            decision_to_support="Test decision",
            audience="Test audience",
            risk_class=RiskClass.HIGH.value,
            task_template=TaskTemplate.RESEARCH.value,
        )
        d = contract.to_dict()
        assert d["objective"] == "Test objective"
        assert d["decision_to_support"] == "Test decision"
        assert d["risk_class"] == "high"

    def test_from_dict(self):
        """Test contract deserialization."""
        data = {
            "objective": "Test objective",
            "decision_to_support": "Test decision",
            "audience": "Test audience",
        }
        contract = AskContract.from_dict(data)
        assert contract.objective == "Test objective"
        assert contract.decision_to_support == "Test decision"

    def test_calculate_completeness_empty(self):
        """Test completeness calculation for empty contract."""
        contract = AskContract()
        completeness = contract.calculate_completeness()
        assert completeness < 0.5  # Should be low for empty contract

    def test_calculate_completeness_full(self):
        """Test completeness calculation for full contract."""
        contract = AskContract(
            objective="Test objective",
            decision_to_support="Test decision",
            audience="Test audience",
            output_shape="Test output",
            constraints="Test constraints",
            available_inputs="Test inputs",
        )
        completeness = contract.calculate_completeness()
        assert completeness >= 0.7  # Should be high for complete contract


class TestNormalizeAskContract:
    """Test ask contract normalization."""

    def test_client_provided_contract(self):
        """Test normalization when client provides contract."""
        message = "Test message"
        raw_contract = {
            "objective": "Client objective",
            "decision_to_support": "Client decision",
            "audience": "Client audience",
        }

        contract, was_synthesized = normalize_ask_contract(
            message=message,
            raw_contract=raw_contract,
        )

        assert contract.objective == "Client objective"
        assert contract.contract_source == "client"
        assert not was_synthesized

    def test_server_synthesize_from_message(self):
        """Test server synthesis when only message is provided."""
        message = "What is the meaning of life?"
        goal_hint = "research"

        contract, was_synthesized = normalize_ask_contract(
            message=message,
            raw_contract=None,
            goal_hint=goal_hint,
        )

        assert contract.objective == message
        assert contract.task_template == TaskTemplate.RESEARCH.value
        assert contract.contract_source == "server_synthesized"
        assert was_synthesized

    def test_goal_hint_mapping(self):
        """Test goal_hint to task_template mapping."""
        test_cases = [
            ("research", TaskTemplate.RESEARCH.value),
            ("code_review", TaskTemplate.CODE_REVIEW.value),
            ("report", TaskTemplate.REPORT_GENERATION.value),
            ("image", TaskTemplate.IMAGE_GENERATION.value),
            ("consult", TaskTemplate.DECISION_SUPPORT.value),
            ("dual_review", TaskTemplate.DUAL_MODEL_CRITIQUE.value),
        ]

        for goal_hint, expected_template in test_cases:
            contract, _ = normalize_ask_contract(
                message="Test",
                raw_contract=None,
                goal_hint=goal_hint,
            )
            assert contract.task_template == expected_template, f"Failed for {goal_hint}"

    def test_empty_raw_contract_synthesizes(self):
        """Test that empty dict triggers synthesis."""
        message = "Test message"

        contract, was_synthesized = normalize_ask_contract(
            message=message,
            raw_contract={},  # Empty dict
        )

        assert contract.objective == message
        assert was_synthesized

    def test_contract_includes_context(self):
        """Test contract includes context info."""
        message = "Test"
        context = {"files": ["file1.py", "file2.py"]}

        contract, _ = normalize_ask_contract(
            message=message,
            raw_contract=None,
            context=context,
        )

        assert "file1.py" in contract.available_inputs
        assert "file2.py" in contract.available_inputs
