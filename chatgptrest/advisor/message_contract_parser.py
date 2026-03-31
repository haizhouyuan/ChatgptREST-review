"""Lightweight label-based message contract parser."""

from __future__ import annotations

from dataclasses import dataclass


_LABEL_MAP: dict[str, tuple[str, ...]] = {
    "objective": ("objective", "goal", "task", "目标", "任务"),
    "decision_to_support": ("decision to support", "decision", "决策目的", "支持的决策", "需要支持的决策"),
    "audience": ("audience", "recipient", "受众", "对象", "使用对象"),
    "constraints": ("constraints", "constraint", "约束", "限制"),
    "available_inputs": ("available inputs", "available input", "inputs", "已有输入", "现有材料", "已有材料"),
    "missing_inputs": ("missing inputs", "missing input", "缺失信息", "待补信息"),
    "output_shape": ("output shape", "output format", "deliverable", "输出形式", "输出格式", "交付形式"),
    "scope_boundary": ("scope boundary", "scope", "范围"),
    "time_horizon": ("time horizon", "time window", "时间范围", "时间窗口"),
}


@dataclass(frozen=True)
class ParsedMessageContract:
    used: bool
    objective: str
    fields: dict[str, str]
    extracted_fields: list[str]
    cleaned_message: str

    def to_meta(self) -> dict[str, object]:
        return {
            "used": self.used,
            "extracted_fields": list(self.extracted_fields),
            "cleaned_message": self.cleaned_message,
        }


def parse_message_contract(message: str) -> ParsedMessageContract:
    text = str(message or "").strip()
    if not text:
        return ParsedMessageContract(False, "", {}, [], "")

    objective_lines: list[str] = []
    fields: dict[str, str] = {}
    extracted_fields: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        key, value = _parse_labeled_line(line)
        if not key:
            objective_lines.append(line)
            continue
        if key in {"scope_boundary", "time_horizon"}:
            if value:
                label = "scope" if key == "scope_boundary" else "time_horizon"
                existing = str(fields.get("constraints") or "").strip()
                fields["constraints"] = f"{existing}\n{label}: {value}".strip() if existing else f"{label}: {value}"
                if "constraints" not in extracted_fields:
                    extracted_fields.append("constraints")
            continue
        if value:
            if key == "constraints" and fields.get("constraints"):
                fields["constraints"] = f"{fields['constraints']}\n{value}".strip()
            else:
                fields[key] = value
            if key not in extracted_fields:
                extracted_fields.append(key)

    objective = str(fields.get("objective") or "").strip()
    if not objective:
        objective = "\n".join(objective_lines).strip()
    cleaned_message = "\n".join(objective_lines).strip() or objective

    return ParsedMessageContract(
        used=bool(extracted_fields),
        objective=objective,
        fields=fields,
        extracted_fields=extracted_fields,
        cleaned_message=cleaned_message,
    )


def _parse_labeled_line(line: str) -> tuple[str | None, str]:
    normalized = line.strip().lstrip("-*").strip().replace("：", ":")
    if ":" not in normalized:
        return None, ""
    raw_label, raw_value = normalized.split(":", 1)
    label = raw_label.strip().lower()
    value = raw_value.strip()
    for key, aliases in _LABEL_MAP.items():
        if label in aliases:
            return key, value
    return None, ""
