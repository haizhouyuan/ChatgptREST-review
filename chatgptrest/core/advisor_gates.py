from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_MODE_DEFAULT_THRESHOLD: dict[str, int] = {
    "fast": 14,
    "balanced": 17,
    "strict": 20,
}


def _safe_int(raw: Any, default: int) -> int:
    try:
        return int(raw)
    except Exception:
        return int(default)


def _norm_mode(raw: Any) -> str:
    mode = str(raw or "").strip().lower()
    if mode in _MODE_DEFAULT_THRESHOLD:
        return mode
    return "balanced"


def _text(raw: Any) -> str:
    return str(raw or "")


def _bool(raw: Any, default: bool = False) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return bool(raw)
    if isinstance(raw, str):
        v = raw.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off"}:
            return False
    return bool(default)


def _quality_dimensions(*, answer_text: str, context: dict[str, Any], evidence_present: bool) -> list[dict[str, Any]]:
    txt = _text(answer_text)
    txt_lower = txt.lower()
    txt_len = len(txt.strip())

    score_conclusion = 0
    if txt_len >= 180:
        score_conclusion = 5
    elif txt_len >= 120:
        score_conclusion = 4
    elif txt_len >= 80:
        score_conclusion = 3
    elif txt_len >= 40:
        score_conclusion = 2
    elif txt_len > 0:
        score_conclusion = 1

    evidence_markers = [
        "http://",
        "https://",
        "[1]",
        "来源",
        "source",
        "reference",
    ]
    score_evidence = 2 if evidence_present else 0
    if any(m in txt_lower for m in evidence_markers):
        score_evidence = min(5, score_evidence + 3)
    elif txt_len >= 120:
        score_evidence = min(5, score_evidence + 1)

    uncertainty_markers = [
        "不确定",
        "假设",
        "可能",
        "uncertain",
        "assumption",
        "risk",
        "limitation",
    ]
    score_uncertainty = 5 if any(m in txt_lower for m in uncertainty_markers) else (2 if txt_len >= 100 else 0)

    actionable_markers = [
        "下一步",
        "行动",
        "todo",
        "next step",
        "1.",
        "2.",
        "- ",
    ]
    has_actionable = any(m in txt_lower for m in actionable_markers) or bool(re.search(r"^\s*\d+\.", txt, flags=re.M))
    score_actionable = 5 if has_actionable else (2 if txt_len >= 120 else 0)

    constraints = list(context.get("constraints") or [])
    if isinstance(constraints, str):
        constraints = [constraints]
    matched_constraints = 0
    for item in constraints:
        token = str(item or "").strip().lower()
        if token and token in txt_lower:
            matched_constraints += 1
    if constraints:
        score_constraints = min(5, int(round((matched_constraints / max(1, len(constraints))) * 5.0)))
    else:
        score_constraints = 5 if txt_len >= 60 else 2

    return [
        {
            "name": "结论明确性",
            "score": score_conclusion,
            "max_score": 5,
            "passed": score_conclusion >= 2,
        },
        {
            "name": "证据覆盖度",
            "score": score_evidence,
            "max_score": 5,
            "passed": score_evidence >= 2,
        },
        {
            "name": "不确定性披露",
            "score": score_uncertainty,
            "max_score": 5,
            "passed": score_uncertainty >= 2,
        },
        {
            "name": "可执行性",
            "score": score_actionable,
            "max_score": 5,
            "passed": score_actionable >= 2,
        },
        {
            "name": "约束符合度",
            "score": score_constraints,
            "max_score": 5,
            "passed": score_constraints >= 2,
        },
    ]


def _role_gate(*, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
    context = dict(run.get("context") or {})
    required_roles = list(context.get("required_roles") or [])
    if isinstance(required_roles, str):
        required_roles = [required_roles]
    required_norm = {str(r).strip().lower() for r in required_roles if str(r).strip()}
    output = dict(step.get("output") or {})
    covered = set()
    for raw in list(output.get("roles_covered") or []):
        token = str(raw or "").strip().lower()
        if token:
            covered.add(token)
    route = str(run.get("route") or "").strip().lower()
    if route:
        covered.add(route)
    missing = sorted(required_norm - covered)
    return {
        "passed": len(missing) == 0,
        "required_roles": sorted(required_norm),
        "covered_roles": sorted(covered),
        "missing_roles": missing,
    }


def _evidence_gate(*, run: dict[str, Any], answer_text: str, evidence_path: str | None) -> dict[str, Any]:
    context = dict(run.get("context") or {})
    require_evidence = _bool(context.get("require_evidence"), default=False)
    mode = _norm_mode(run.get("mode"))
    if mode == "strict":
        require_evidence = True

    path_text = str(evidence_path or "").strip()
    has_file = False
    if path_text:
        try:
            p = Path(path_text)
            has_file = p.exists() and p.is_file() and p.stat().st_size > 0
        except Exception:
            has_file = False
    answer_has_marker = any(
        marker in _text(answer_text).lower() for marker in ["http://", "https://", "[1]", "source", "来源", "evidence"]
    )
    passed = (has_file or answer_has_marker) if require_evidence else (has_file or answer_has_marker or bool(answer_text.strip()))
    return {
        "passed": bool(passed),
        "require_evidence": bool(require_evidence),
        "has_file_evidence": bool(has_file),
        "has_inline_evidence_markers": bool(answer_has_marker),
    }


def evaluate_gate_report(
    *,
    run: dict[str, Any],
    step: dict[str, Any],
    answer_text: str,
    evidence_path: str | None,
) -> dict[str, Any]:
    context = dict(run.get("context") or {})
    mode = _norm_mode(run.get("mode"))
    threshold = _safe_int(run.get("quality_threshold"), _MODE_DEFAULT_THRESHOLD.get(mode, 17))
    threshold = max(0, min(100, threshold))

    evidence = _evidence_gate(run=run, answer_text=answer_text, evidence_path=evidence_path)
    role = _role_gate(run=run, step=step)
    dims = _quality_dimensions(answer_text=answer_text, context=context, evidence_present=bool(evidence.get("has_file_evidence")))
    score = sum(int(item.get("score") or 0) for item in dims)
    quality = {
        "passed": score >= threshold,
        "score": score,
        "threshold": threshold,
        "dimensions": dims,
    }
    failures: list[str] = []
    if not quality["passed"]:
        failures.append("quality")
    if not role["passed"]:
        failures.append("role")
    if not evidence["passed"]:
        failures.append("evidence")
    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "quality": quality,
        "role": role,
        "evidence": evidence,
    }
