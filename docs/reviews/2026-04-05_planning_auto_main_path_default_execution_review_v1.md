# 2026-04-05 Planning Auto Main-Path Default Execution Review v1

## Scope

This batch closes one of the biggest remaining user-facing gaps:

- users should not have to choose a provider for already-frozen planning
  profiles

Implementation commit:

- `TBD`

The batch does not widen the execution-layer boundary.
It only changes the default main path for planning profiles that are already in
scope.

## Implemented

### 1. Stable planning profiles now auto-select a visible main path

Files:

- `chatgptrest/api/routes_agent_v3.py`

What changed:

1. `lane_policy.default_provider` no longer only applies to compact
   implementation next-steps
2. the following frozen planning profiles now default to `chatgpt` when the
   caller did not explicitly request another provider or lane:
   - `business_planning`
   - `meeting_summary`
   - `interview_notes`
   - `workforce_planning`
   - `implementation_plan`
   - `project_diagnosis`
   - `research_decision`
   - `leadership_report`
   - `planning_general`
3. repo-backed `implementation_plan` still keeps the stronger default:
   - `coding_agent -> codex`

User effect:

- common planning requests no longer look “accepted but unresolved”
- the main path is visible in the public surface instead of being left as an
  unfrozen runtime default

### 2. User-readiness proof now freezes automatic main-path visibility

Files:

- `chatgptrest/eval/planning_user_readiness_acceptance.py`
- `tests/test_planning_user_readiness_acceptance.py`
- `tests/test_routes_agent_v3.py`

What changed:

1. the user-readiness acceptance pack now checks
   `automatic_main_path_visible` for the stable planning profiles
2. continuity proof now also checks that the first turn entered a stable main
   path without manual provider selection
3. route tests now assert the public surface exposes
   `provider_resolution=policy_default` where expected

## Acceptance Result

Fresh readiness evidence is frozen in:

- `docs/dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v3/manifest.json`
- `docs/dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v3/report_v1.md`

Frozen result:

1. `9/9` user-readiness cases pass
2. `stable_planning_profiles_auto_select_main_path = true`
3. repo-backed implementation planning still auto-selects `coding_agent`
4. thin and incomplete full-planning output still fail-close
5. same-task continuity still remains green

Result:

- accepted

## Validation

Python syntax:

- `python3 -m py_compile chatgptrest/api/routes_agent_v3.py chatgptrest/eval/planning_user_readiness_acceptance.py tests/test_routes_agent_v3.py tests/test_planning_user_readiness_acceptance.py`

Targeted pytest:

- `./.venv/bin/pytest -q tests/test_routes_agent_v3.py tests/test_planning_user_readiness_acceptance.py`
- `./.venv/bin/pytest -q tests/test_routes_agent_v3.py tests/test_routes_agent_v3_planning_task_plane.py tests/test_agent_v3_routes.py tests/test_planning_user_readiness_acceptance.py`

Evidence export:

- `PYTHONPATH=. ./.venv/bin/python ops/export_planning_user_readiness_acceptance_pack.py --output-dir docs/dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v3`

## Frozen User-Facing Statement

After this batch, the honest statement is:

> for the stable planning profiles already in scope, the system now auto-selects
> a visible main path instead of leaving provider choice unresolved. Users do
> not need to decide the provider for normal planning asks, while repo-backed
> implementation planning still escalates into the coding-agent lane by default.
