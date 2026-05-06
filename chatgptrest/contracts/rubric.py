"""
Convergence Rubric v1 – Quantified stage gating for the Funnel.

Dimensions (from Funnel DR):
    1. Information completeness  (weight 18)
    2. Controversy convergence   (weight 16)
    3. Risk controllability      (weight 18)
    4. Scope boundary clarity    (weight 16)
    5. Executability             (weight 18)
    6. Evidence sufficiency      (weight 14)
                                 ─────────
                          Total: 100

Gate A (Diverge → Converge): Total ≥ 55, Scope ≥ 0.5, Info ≥ 0.5
Gate B (Converge → Freeze):  Total ≥ 80, Exec ≥ 0.8, Evidence ≥ 0.7, Risk ≥ 0.75
Gate C (Reopen):             Execution contradicts claims OR context changed
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any


class Gate(str, Enum):
    NONE = "none"       # Below Gate A
    A = "A"             # Diverge → Converge
    B = "B"             # Converge → Freeze/Handoff
    C = "C"             # Reopen (execution contradicts claims)


# Weights (sum = 100)
WEIGHTS = {
    "information_completeness": 18,
    "controversy_convergence": 16,
    "risk_controllability": 18,
    "scope_boundary_clarity": 16,
    "executability": 18,
    "evidence_sufficiency": 14,
}


@dataclass
class RubricInput:
    """
    Raw inputs for rubric computation.
    All scores are floats in [0, 1].
    """
    # Information completeness
    required_fields_total: int = 0
    required_fields_filled: int = 0

    # Controversy convergence
    agent_decision_agreement: float = 0.0     # fraction of agents picking same option
    rationale_overlap: float = 0.0            # Jaccard similarity of rationale tokens
    iteration_stability: float = 0.0          # does agreement improve over rounds?

    # Risk controllability
    top_k_risks: int = 0
    risks_with_mitigation: int = 0            # risks that have mitigation+signal+owner

    # Scope boundary clarity
    has_in_scope: bool = False
    has_out_scope: bool = False
    has_assumptions: bool = False
    has_constraints: bool = False
    has_interfaces: bool = False
    ambiguous_word_count: int = 0             # "fast", "user-friendly" without definition
    total_requirement_words: int = 1

    # Executability
    has_test_plan: bool = False
    task_decomposition_quality: float = 0.0   # 0-1

    # Evidence sufficiency
    critical_claims: int = 0
    critical_claims_with_evidence: int = 0
    avg_evidence_quality: float = 0.0         # 0-1


@dataclass
class RubricResult:
    """Full rubric result with dimension scores and gate determination."""
    total: float = 0.0
    information_completeness: float = 0.0
    controversy_convergence: float = 0.0
    risk_controllability: float = 0.0
    scope_boundary_clarity: float = 0.0
    executability: float = 0.0
    evidence_sufficiency: float = 0.0
    gate: str = "none"
    gate_reasons: list[str] = None

    def __post_init__(self):
        if self.gate_reasons is None:
            self.gate_reasons = []

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_rubric(inp: RubricInput) -> RubricResult:
    """
    Compute the convergence rubric score from raw inputs.

    Returns a RubricResult with dimension scores [0,1] and a total [0,100].
    """
    # 1. Information completeness
    if inp.required_fields_total > 0:
        s_info = inp.required_fields_filled / inp.required_fields_total
    else:
        s_info = 0.0

    # 2. Controversy convergence
    s_controversy = (
        0.5 * inp.agent_decision_agreement
        + 0.3 * inp.rationale_overlap
        + 0.2 * inp.iteration_stability
    )

    # 3. Risk controllability
    if inp.top_k_risks > 0:
        s_risk = inp.risks_with_mitigation / inp.top_k_risks
    else:
        s_risk = 1.0  # no risks = fully controlled

    # 4. Scope boundary clarity
    scope_checklist = [
        inp.has_in_scope,
        inp.has_out_scope,
        inp.has_assumptions,
        inp.has_constraints,
        inp.has_interfaces,
    ]
    scope_coverage = sum(scope_checklist) / len(scope_checklist)
    ambiguity_penalty = min(
        1.0,
        inp.ambiguous_word_count / max(inp.total_requirement_words, 1) * 10
    )
    s_scope = scope_coverage * (1.0 - ambiguity_penalty * 0.5)
    s_scope = max(0.0, min(1.0, s_scope))

    # 5. Executability
    test_present = 1.0 if inp.has_test_plan else 0.0
    s_exec = 0.6 * test_present + 0.4 * inp.task_decomposition_quality

    # 6. Evidence sufficiency
    if inp.critical_claims > 0:
        coverage = inp.critical_claims_with_evidence / inp.critical_claims
        s_evidence = coverage * inp.avg_evidence_quality
    else:
        s_evidence = 0.0

    # Compute weighted total (0-100)
    total = (
        WEIGHTS["information_completeness"] * s_info
        + WEIGHTS["controversy_convergence"] * s_controversy
        + WEIGHTS["risk_controllability"] * s_risk
        + WEIGHTS["scope_boundary_clarity"] * s_scope
        + WEIGHTS["executability"] * s_exec
        + WEIGHTS["evidence_sufficiency"] * s_evidence
    )

    # Determine gate
    gate_reasons = []

    # Gate B check first (more restrictive)
    gate_b_ok = True
    if total < 80:
        gate_b_ok = False
        gate_reasons.append(f"Total {total:.1f} < 80")
    if s_exec < 0.8:
        gate_b_ok = False
        gate_reasons.append(f"Executability {s_exec:.2f} < 0.80")
    if s_evidence < 0.7:
        gate_b_ok = False
        gate_reasons.append(f"Evidence {s_evidence:.2f} < 0.70")
    if s_risk < 0.75:
        gate_b_ok = False
        gate_reasons.append(f"Risk {s_risk:.2f} < 0.75")

    if gate_b_ok:
        gate = Gate.B
        gate_reasons = ["All Gate B thresholds met"]
    else:
        # Gate A check
        gate_a_ok = True
        a_reasons = []
        if total < 55:
            gate_a_ok = False
            a_reasons.append(f"Total {total:.1f} < 55")
        if s_scope < 0.5:
            gate_a_ok = False
            a_reasons.append(f"Scope {s_scope:.2f} < 0.50")
        if s_info < 0.5:
            gate_a_ok = False
            a_reasons.append(f"Info {s_info:.2f} < 0.50")

        if gate_a_ok:
            gate = Gate.A
            gate_reasons = ["Gate A met but not Gate B"] + gate_reasons
        else:
            gate = Gate.NONE
            gate_reasons = a_reasons

    return RubricResult(
        total=round(total, 2),
        information_completeness=round(s_info, 4),
        controversy_convergence=round(s_controversy, 4),
        risk_controllability=round(s_risk, 4),
        scope_boundary_clarity=round(s_scope, 4),
        executability=round(s_exec, 4),
        evidence_sufficiency=round(s_evidence, 4),
        gate=gate.value,
        gate_reasons=gate_reasons,
    )
