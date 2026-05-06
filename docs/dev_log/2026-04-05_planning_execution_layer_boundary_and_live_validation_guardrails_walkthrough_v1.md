# Planning Execution Layer Boundary And Live Validation Guardrails Walkthrough v1

## What I Did

Re-opened the planning phase-1 scope after a red-team discussion with `claudegac` and corrected two pieces of drift:

1. the execution-layer claim boundary
2. the default behavior of planning live validation

The red-team reference for this batch is:

- `claudegac` run id: `ccjob_20260405T021349Z_b9654113`

Then I implemented and tested one narrow batch:

- made `control_plane.execution_layer` explicit
- projected the same execution-layer summary onto planning-task read surfaces
- let direct Gemini planning validation request `preset=auto`
- replaced single-prompt live validation with prompt rotation plus `prompt_case_id`
- documented the corrected boundary in `AGENTS.md`

## Why

The drift was not in the code path alone. The larger problem was that the repo could be read as if:

- `planning task plane` already modeled the whole execution layer
- repeated live validation against `chatgpt_web` or `gemini_web` was an acceptable proxy for every executor shape

That was too broad.

The corrected interpretation is:

- `planning task plane` currently proves a `phase1_web_provider_subset`
- `chatgpt_web / gemini_web / qwen_web` are the currently modeled execution subset
- `codex / codex2 / claudeminmax / claudegac` belong to future execution lanes unless and until they are explicitly added to the same contract

## Files

- `chatgptrest/api/routes_agent_v3.py`
- `chatgptrest/eval/planning_live_prompt_cases.py`
- `chatgptrest/eval/openclawbot_planning_task_plane_live_completion_gate.py`
- `chatgptrest/eval/openclawbot_planning_task_plane_live_gate.py`
- `chatgptrest/eval/openclawbot_planning_task_plane_live_main_path_gate.py`
- `ops/run_openclawbot_planning_task_plane_live_completion_gate.py`
- `ops/export_openclawbot_planning_task_cancel_consistency_probe.py`
- `AGENTS.md`

## Risk Handling

I explicitly stayed out of the durable truth core this round.

- `MeetingTaskStore.update_checkpoint` was not edited because GitNexus marked it `CRITICAL`
- `_session_response` was not edited because GitNexus also marked it `CRITICAL`

Instead, the batch uses the already lower-risk projection path:

- `control_plane.execution_layer`
- planning-task refresh projection
- live-gate/report metadata

## Validation

- `./.venv/bin/python -m py_compile chatgptrest/api/routes_agent_v3.py chatgptrest/eval/planning_live_prompt_cases.py chatgptrest/eval/openclawbot_planning_task_plane_live_completion_gate.py chatgptrest/eval/openclawbot_planning_task_plane_live_gate.py chatgptrest/eval/openclawbot_planning_task_plane_live_main_path_gate.py ops/run_openclawbot_planning_task_plane_live_completion_gate.py ops/export_openclawbot_planning_task_cancel_consistency_probe.py`
- `./.venv/bin/pytest -q tests/test_planning_live_prompt_cases.py tests/test_routes_agent_v3.py tests/test_routes_agent_v3_planning_task_plane.py tests/test_openclawbot_planning_task_plane_live_completion_gate.py tests/test_run_openclawbot_planning_task_plane_live_completion_gate.py tests/test_openclawbot_planning_task_plane_live_gate.py tests/test_openclawbot_planning_task_plane_live_main_path_gate.py tests/test_export_openclawbot_planning_task_cancel_consistency_probe.py`
- fresh live contract verification:
  - `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260405_gemini_auto_v2/manifest.json`
  - `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260405_gemini_auto_v2/report_v1.md`
  - `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260405_gemini_auto_v2/session_snapshot_v1.json`

## Outcome

The planning phase-1 wording is now harder to misread:

- execution-layer truth is explicit
- `auto` can be requested for direct Gemini validation
- live validation no longer needs one repeated canonical question
- future coding-agent executors are no longer implicitly claimed by the current planning evidence
- a fresh live rerun confirmed the new contract propagation without claiming a new Gemini green completion
