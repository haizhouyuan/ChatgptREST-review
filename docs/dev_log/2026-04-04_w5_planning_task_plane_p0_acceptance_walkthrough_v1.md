# W5 Walkthrough v1

## What I Did

Added a new bundled acceptance exporter for the planning task plane P0 scope:

- implemented `chatgptrest/eval/planning_task_plane_p0_acceptance.py`
- added `ops/export_planning_task_plane_p0_acceptance_pack.py`
- added `tests/test_planning_task_plane_p0_acceptance.py`

Then ran the exporter to freeze a real artifact under:

- `docs/dev_log/artifacts/planning_task_plane_p0_acceptance_pack_20260404_v1`

## Why

Before this batch, the planning task plane had a strong canonical acceptance story, but not one bundled artifact that covered the full five-scenario P0 surface expected by the program plan.

This batch turns that requirement into a stable export:

- same entry surface
- same checklist
- same manifest/report shape
- same evidence layout for every scenario

## Validation

- `./.venv/bin/python -m py_compile chatgptrest/eval/planning_task_plane_p0_acceptance.py ops/export_planning_task_plane_p0_acceptance_pack.py tests/test_planning_task_plane_p0_acceptance.py`
- `./.venv/bin/pytest -q tests/test_planning_task_plane_p0_acceptance.py`
- `PYTHONPATH=. ./.venv/bin/python ops/export_planning_task_plane_p0_acceptance_pack.py`

## Outcome

The generated acceptance pack passed all five scenarios:

- `meeting_sedimentation`
- `workforce_planning`
- `project_diagnosis`
- `research_decision`
- `leadership_report`

Every scenario passed the shared checklist:

- `understands_request`
- `covers_required_items`
- `voice_consistent`
- `directly_usable`
- `verifiable`
