"""Ask Contract Schema and Synthesis — Premium Ingress Front Gate.

This module implements the Ask Contract / Funnel front gate for the premium agent ingress.

Ask Contract Fields:
- objective: What is the goal
- decision_to_support: What decision this answer will support
- audience: Who will use the answer
- constraints: Time, risk, scope, format constraints
- available_inputs: Current available materials
- missing_inputs: What information is missing
- output_shape: Required form of result
- risk_class: low / medium / high stakes
- opportunity_cost: Whether this premium call is worth it
- task_template: Which problem template this belongs to
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional

from chatgptrest.advisor.message_contract_parser import parse_message_contract

logger = logging.getLogger(__name__)


class RiskClass(str, Enum):
    """Risk classification for the ask."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskTemplate(str, Enum):
    """Available task templates for problem classification."""
    RESEARCH = "research"
    DECISION_SUPPORT = "decision_support"
    CODE_REVIEW = "code_review"
    IMPLEMENTATION_PLANNING = "implementation_planning"
    REPORT_GENERATION = "report_generation"
    IMAGE_GENERATION = "image_generation"
    DUAL_MODEL_CRITIQUE = "dual_model_critique"
    REPAIR_DIAGNOSIS = "repair_diagnosis"
    STAKEHOLDER_COMMUNICATION = "stakeholder_communication"
    GENERAL = "general"


@dataclass
class AskContract:
    """
    Minimal ask contract for premium agent ingress.

    This is the structured input that should be provided when making
    a premium ask. If client only sends free-text message, the server
    will synthesize this contract.
    """
    # Core fields
    objective: str = ""
    decision_to_support: str = ""
    audience: str = ""
    constraints: str = ""
    available_inputs: str = ""
    missing_inputs: str = ""
    output_shape: str = ""
    risk_class: str = RiskClass.MEDIUM.value
    opportunity_cost: str = ""
    task_template: str = TaskTemplate.GENERAL.value

    # Metadata
    contract_id: str = field(default_factory=lambda: f"contract_{uuid.uuid4().hex[:12]}")
    contract_source: str = "server_synthesized"  # "client" or "server_synthesized"
    contract_completeness: float = 0.0  # 0.0 - 1.0
    clarify_gate_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AskContract":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def calculate_completeness(self) -> float:
        """
        Calculate contract completeness score.

        Returns a value between 0.0 and 1.0 based on how many
        required fields are filled in.
        """
        required_fields = [
            self.objective,
            self.decision_to_support,
            self.audience,
            self.output_shape,
        ]

        filled_count = sum(1 for f in required_fields if f and f.strip())
        base_score = filled_count / len(required_fields)

        # Bonus for optional fields
        if self.constraints:
            base_score += 0.1
        if self.available_inputs:
            base_score += 0.1
        if self.risk_class and self.risk_class != RiskClass.MEDIUM.value:
            base_score += 0.1
        if self.task_template and self.task_template != TaskTemplate.GENERAL.value:
            base_score += 0.1

        return min(1.0, base_score)


def _synthesize_contract_from_message(
    message: str,
    goal_hint: str = "",
    context: dict[str, Any] | None = None,
) -> AskContract:
    """
    Synthesize an ask contract from a free-text message.

    This is used when the client only sends a message without
    structured contract fields. The server will analyze the message
    and create a best-effort contract.

    Args:
        message: The free-text message from the client
        goal_hint: Optional goal hint from the client
        context: Optional context from the client

    Returns:
        AskContract with synthesized fields
    """
    contract = AskContract()
    parsed = parse_message_contract(message)
    contract.contract_source = "message_parser" if parsed.used else "server_synthesized"

    # Set objective to the parsed task body when available.
    contract.objective = parsed.objective or message.strip()
    contract.decision_to_support = str(parsed.fields.get("decision_to_support") or "").strip()
    contract.audience = str(parsed.fields.get("audience") or "").strip()
    contract.constraints = str(parsed.fields.get("constraints") or "").strip()
    contract.available_inputs = str(parsed.fields.get("available_inputs") or "").strip()
    contract.missing_inputs = str(parsed.fields.get("missing_inputs") or "").strip()
    contract.output_shape = str(parsed.fields.get("output_shape") or "").strip()

    # Infer task template from goal_hint
    if goal_hint:
        goal_to_template = {
            "research": TaskTemplate.RESEARCH.value,
            "code_review": TaskTemplate.CODE_REVIEW.value,
            "report": TaskTemplate.REPORT_GENERATION.value,
            "image": TaskTemplate.IMAGE_GENERATION.value,
            "consult": TaskTemplate.DECISION_SUPPORT.value,
            "dual_review": TaskTemplate.DUAL_MODEL_CRITIQUE.value,
            "gemini_research": TaskTemplate.RESEARCH.value,
            "deep_research": TaskTemplate.RESEARCH.value,
            "repair": TaskTemplate.REPAIR_DIAGNOSIS.value,
        }
        contract.task_template = goal_to_template.get(goal_hint.lower(), TaskTemplate.GENERAL.value)

    # Extract constraints from context if available
    if context:
        if context.get("constraints") and not contract.constraints:
            contract.constraints = str(context.get("constraints"))
        if context.get("files") and not contract.available_inputs:
            contract.available_inputs = f"Files: {', '.join(context.get('files', []))}"

    # Infer output shape from goal_hint
    if not contract.output_shape and goal_hint in {"report", "write_report"}:
        contract.output_shape = "markdown_report"
    elif not contract.output_shape and goal_hint == "image":
        contract.output_shape = "image_url"
    elif not contract.output_shape and goal_hint == "code_review":
        contract.output_shape = "code_review_summary"
    elif not contract.output_shape:
        contract.output_shape = "text_answer"

    # Set default risk class based on goal_hint
    if goal_hint in {"deep_research", "gemini_deep_research", "consult"}:
        contract.risk_class = RiskClass.HIGH.value
    else:
        contract.risk_class = RiskClass.MEDIUM.value

    # Calculate completeness
    contract.contract_completeness = contract.calculate_completeness()

    logger.info(
        f"Synthesized ask contract: id={contract.contract_id}, "
        f"template={contract.task_template}, completeness={contract.contract_completeness:.2f}"
    )

    return contract


def normalize_ask_contract(
    message: str,
    raw_contract: dict[str, Any] | None = None,
    goal_hint: str = "",
    context: dict[str, Any] | None = None,
) -> tuple[AskContract, bool]:
    """
    Normalize and validate ask contract from client input.

    This function handles two cases:
    1. Client provides structured contract fields
    2. Client only provides free-text message (synthesize contract)

    Args:
        message: The user's message
        raw_contract: Raw contract dict from client (optional)
        goal_hint: Optional goal hint
        context: Optional context dict

    Returns:
        Tuple of (AskContract, was_synthesized)
    """
    was_synthesized = False

    # Case 1: Client provides structured contract
    if raw_contract and any(raw_contract.values()):
        # Merge message with contract if message is more specific
        contract = AskContract.from_dict(raw_contract)
        parsed = parse_message_contract(message)

        # If message is provided but objective is empty, use parsed objective or message
        if not contract.objective and message:
            contract.objective = parsed.objective or message.strip()
        if not contract.decision_to_support:
            contract.decision_to_support = str(parsed.fields.get("decision_to_support") or "").strip()
        if not contract.audience:
            contract.audience = str(parsed.fields.get("audience") or "").strip()
        if not contract.constraints:
            contract.constraints = str(parsed.fields.get("constraints") or "").strip()
        if not contract.available_inputs:
            contract.available_inputs = str(parsed.fields.get("available_inputs") or "").strip()
        if not contract.missing_inputs:
            contract.missing_inputs = str(parsed.fields.get("missing_inputs") or "").strip()
        if not contract.output_shape:
            contract.output_shape = str(parsed.fields.get("output_shape") or "").strip()

        # Determine if this was client-provided or synthesized
        # If contract came from client with meaningful fields, mark as client
        if contract.objective and contract.objective != message.strip():
            contract.contract_source = "client"
        elif contract.decision_to_support or contract.audience:
            contract.contract_source = "client"
        elif parsed.used:
            contract.contract_source = "message_parser"

        contract.contract_completeness = contract.calculate_completeness()

    # Case 2: Client only provides message, synthesize contract
    else:
        contract = _synthesize_contract_from_message(
            message=message,
            goal_hint=goal_hint,
            context=context,
        )
        was_synthesized = True

    return contract, was_synthesized


# Import uuid for contract_id generation
import uuid
