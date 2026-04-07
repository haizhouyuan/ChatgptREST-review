from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ROTATION_STATE_PATH = (
    Path(__file__).resolve().parents[2] / "state" / "eval" / "planning_live_prompt_rotation.json"
)


@dataclass(frozen=True)
class PlanningLivePromptCase:
    family: str
    case_id: str
    message: str


_PROMPT_CASES: dict[str, tuple[PlanningLivePromptCase, ...]] = {
    "compact_next_steps": (
        PlanningLivePromptCase(
            family="compact_next_steps",
            case_id="compact_next_steps_v1",
            message=(
                "请严格依据附件整理三条下一步计划。"
                "要求：1）直接输出三条无序列表；2）每条一句；3）至少有一条直接处理附件中的当前项目卡点；"
                "4）不要写附件里没有出现的项目名、系统名、代码文件名。"
            ),
        ),
        PlanningLivePromptCase(
            family="compact_next_steps",
            case_id="compact_next_steps_v2",
            message=(
                "请只根据附件给出三条下一步计划。"
                "要求：1）直接输出三条无序列表；2）每条一句；3）至少一条直接处理附件里的当前项目卡点；"
                "4）不要补充附件里没有出现的项目名、系统名、代码文件名。"
            ),
        ),
        PlanningLivePromptCase(
            family="compact_next_steps",
            case_id="compact_next_steps_v3",
            message=(
                "请基于附件整理三条下一步动作。"
                "要求：1）直接输出三条无序列表；2）每条一句；3）至少有一条直接处理附件中的当前项目卡点；"
                "4）不要写出附件里没有出现的项目名、系统名、代码文件名。"
            ),
        ),
        PlanningLivePromptCase(
            family="compact_next_steps",
            case_id="compact_next_steps_v4",
            message=(
                "请围绕附件内容整理三条下一步计划。"
                "要求：1）直接输出三条无序列表；2）每条一句；3）至少有一条直接处理附件中的当前项目卡点；"
                "4）不要加入附件里没有出现的项目名、系统名、代码文件名。"
            ),
        ),
    ),
    "brief_next_steps": (
        PlanningLivePromptCase(
            family="brief_next_steps",
            case_id="brief_next_steps_v1",
            message="请基于附件整理三条下一步计划，答案控制在150字内。",
        ),
        PlanningLivePromptCase(
            family="brief_next_steps",
            case_id="brief_next_steps_v2",
            message="请依据附件给出三条下一步动作，答案控制在150字内。",
        ),
        PlanningLivePromptCase(
            family="brief_next_steps",
            case_id="brief_next_steps_v3",
            message="请根据附件输出三条下一步安排，答案控制在150字内。",
        ),
    ),
    "cancel_probe": (
        PlanningLivePromptCase(
            family="cancel_probe",
            case_id="cancel_probe_v1",
            message="请整理三条下一步动作。",
        ),
        PlanningLivePromptCase(
            family="cancel_probe",
            case_id="cancel_probe_v2",
            message="请给出三条下一步动作。",
        ),
        PlanningLivePromptCase(
            family="cancel_probe",
            case_id="cancel_probe_v3",
            message="请输出三条下一步安排。",
        ),
    ),
}


def _rotation_state_path(override: str | Path | None = None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    raw = str(os.environ.get("CHATGPTREST_EVAL_PROMPT_ROTATION_STATE") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_ROTATION_STATE_PATH


def _load_rotation_state(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    state: dict[str, int] = {}
    for key, value in payload.items():
        try:
            state[str(key)] = max(0, int(value))
        except Exception:
            continue
    return state


def _write_rotation_state(path: Path, state: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def select_planning_live_prompt_case(
    family: str,
    *,
    state_path: str | Path | None = None,
) -> PlanningLivePromptCase:
    normalized_family = str(family or "").strip()
    cases = _PROMPT_CASES.get(normalized_family)
    if not cases:
        raise ValueError(f"unknown planning live prompt family: {normalized_family}")
    path = _rotation_state_path(state_path)
    state = _load_rotation_state(path)
    current_index = int(state.get(normalized_family) or 0)
    selected = cases[current_index % len(cases)]
    state[normalized_family] = current_index + 1
    _write_rotation_state(path, state)
    return selected

