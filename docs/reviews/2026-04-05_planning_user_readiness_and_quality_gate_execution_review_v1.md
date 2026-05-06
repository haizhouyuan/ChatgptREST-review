# 2026-04-05 Planning User Readiness and Quality Gate Execution Review v1

## Scope

This batch closes the remaining gap between “planning can produce answers” and
“planning gives the user something they can trust as directly usable work
output”.

The goal of this batch is user-facing:

1. the system should route common planning requests into the right profile
2. the output should be directly usable instead of generic or underspecified
3. obviously incomplete planning output should fail closed instead of pretending
   to be finished
4. once a response is fail-closed, the same truth should remain visible in task
   lookup and session lookup

## Implemented

### 1. Full planning no longer passes on length alone

Files:

- `chatgptrest/api/routes_agent_v3.py`

What changed:

1. full planning quality-gate now requires the answer to cover the required
   planning skeleton, not just be long enough
2. profiles with up to 4 required sections must cover all of them
3. profiles with 5 or more required sections may miss at most 1 section
4. the public `quality_gate` now explicitly exposes:
   - `required_section_minimum`
   - `section_coverage_ratio`

User effect:

- long but incomplete planning answers now fail closed
- users no longer get a “completed” response that still omits core sections such
  as dependencies or validation

### 2. Missing-section failures are now frozen as a first-class bad path

Files:

- `tests/test_routes_agent_v3.py`
- `chatgptrest/eval/planning_user_readiness_acceptance.py`
- `tests/test_planning_user_readiness_acceptance.py`
- `ops/export_planning_user_readiness_acceptance_pack.py`

What changed:

1. added a bad-path regression where the answer is long but still misses key
   implementation-plan sections
2. added a user-readiness acceptance case that proves this bad path fails
   closed end-to-end
3. the acceptance bundle now freezes 9 user-facing behaviors instead of 8

User effect:

- users are protected from “looks finished but still not actionable” planning
  output
- the missing sections are visible in the public response instead of hidden in
  internal logic

## Acceptance Result

Fresh user-readiness evidence is frozen in:

- `docs/dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v2/manifest.json`
- `docs/dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v2/report_v1.md`

Frozen result:

1. `9/9` user-readiness cases pass
2. same-task continuity still stays green
3. repo-backed implementation planning still auto-selects `coding_agent`
4. thin full-planning output fail-closes
5. long-but-missing-section full-planning output now also fail-closes
6. fail-closed truth stays aligned in both `task_get` and `session_get`
7. branch flow still preserves the original task truth

Result:

- accepted

## Validation

Python syntax:

- `python3 -m py_compile chatgptrest/api/routes_agent_v3.py chatgptrest/eval/planning_user_readiness_acceptance.py tests/test_routes_agent_v3.py tests/test_planning_user_readiness_acceptance.py`

Targeted pytest:

- `./.venv/bin/pytest -q tests/test_routes_agent_v3.py tests/test_planning_user_readiness_acceptance.py`
- `./.venv/bin/pytest -q tests/test_routes_agent_v3.py tests/test_routes_agent_v3_planning_task_plane.py tests/test_agent_v3_routes.py tests/test_planning_user_readiness_acceptance.py`

Evidence export:

- `PYTHONPATH=. ./.venv/bin/python ops/export_planning_user_readiness_acceptance_pack.py --output-dir docs/dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v2`

## Frozen User-Facing Statement

After this batch, the honest statement is:

> the planning task plane now has a user-readiness gate that rejects both thin
> full-planning output and long-but-incomplete full-planning output. High-
> frequency planning requests can be routed into the correct profile, continue on
> the same task, default repo-backed implementation planning into a coding-agent
> lane, and fail closed without losing truth alignment between the response,
> session, and task checkpoint.
