from __future__ import annotations

import pytest

from chatgptrest.eval.planning_live_prompt_cases import select_planning_live_prompt_case


def test_select_planning_live_prompt_case_rotates_by_family(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CHATGPTREST_EVAL_PROMPT_ROTATION_STATE", str(tmp_path / "rotation.json"))

    first = select_planning_live_prompt_case("compact_next_steps")
    second = select_planning_live_prompt_case("compact_next_steps")
    third = select_planning_live_prompt_case("brief_next_steps")

    assert first.case_id == "compact_next_steps_v1"
    assert second.case_id == "compact_next_steps_v2"
    assert third.case_id == "brief_next_steps_v1"


def test_select_planning_live_prompt_case_rejects_unknown_family(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CHATGPTREST_EVAL_PROMPT_ROTATION_STATE", str(tmp_path / "rotation.json"))

    with pytest.raises(ValueError):
        select_planning_live_prompt_case("unknown-family")
