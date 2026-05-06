# 2026-04-05 Planning Auto-Understanding From Language And Attachments Execution Review v1

## Scope

This batch closes the remaining user-facing gap between:

- "the system works if you tell it the exact planning type"
- and
- "the system understands common planning requests the way users naturally
  phrase them"

This batch stays narrow on purpose.

`resolve_scenario_pack` remains a `CRITICAL` blast-radius area in GitNexus, so
the implementation only adds two bounded detection upgrades:

1. generic planning-language detection for `planning_general`
2. attachment-driven `meeting_summary` detection from transcript signals

## Implemented

### 1. Generic planning language now lands in `planning_general`

Files:

- `chatgptrest/advisor/scenario_packs.py`
- `tests/test_scenario_packs.py`
- `tests/test_routes_agent_v3.py`

What changed:

1. `scenario_pack` now treats common expressions like:
   - `业务推进方案`
   - `工作推进方案`
   - `推进计划`
   - `下一阶段计划`
   - `下一步推进`
2. requests like `请整理一版业务推进方案和下一步计划` no longer need
   explicit `planning_task_type=planning_general`
3. the route layer now proves this through the real `/v3/agent/turn` surface,
   not just through pack-unit tests

User effect:

- users can describe a normal planning ask in natural language
- the system can still freeze the correct structure and main path without
  asking for internal task labels

### 2. Meeting transcript attachments now auto-land in `meeting_summary`

Files:

- `chatgptrest/advisor/scenario_packs.py`
- `chatgptrest/eval/planning_user_readiness_acceptance.py`
- `tests/test_scenario_packs.py`
- `tests/test_routes_agent_v3.py`
- `tests/test_planning_user_readiness_acceptance.py`

What changed:

1. `scenario_pack` haystack building now reads more attachment-inventory signal:
   - `files`
   - `notes`
   - `preflight.planning_roles`
   - `preflight.material_families`
   - per-item `planning_role / family / path / handling`
2. if those signals indicate `meeting_transcript`, a generic request like
   `请先帮我整理一下今天材料` now lands in `meeting_summary`
3. the readiness pack now includes this as a real user-effect case

User effect:

- users do not need to explain "this is meeting material" in the prompt if the
  attachment metadata already says so
- meeting-summary work is more likely to enter the right report lane directly

### 3. User-readiness proof is now stricter and more honest

Files:

- `chatgptrest/eval/planning_user_readiness_acceptance.py`
- `tests/test_planning_user_readiness_acceptance.py`

What changed:

1. the user-readiness pack no longer relies on explicit `task_type` for:
   - `project_diagnosis`
   - `research_decision`
   - `leadership_report`
   - `planning_general`
2. a new attachment-driven `meeting_summary` case was added
3. the pack scope now explicitly freezes:
   - `attachment_signals_auto_understood = true`

## Acceptance Result

Fresh readiness evidence is frozen in:

- `docs/dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v4/manifest.json`
- `docs/dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v4/report_v1.md`

Frozen result:

1. `10/10` user-readiness cases pass
2. natural-language `planning_general` still stays green
3. attachment-driven `meeting_summary` stays green
4. stable planning profiles still auto-select a visible main path
5. repo-backed implementation planning still auto-selects `coding_agent + codex`
6. continuity, branch integrity, and full-planning fail-close remain green

Result:

- accepted

## Validation

Python syntax:

- `python3 -m py_compile chatgptrest/advisor/scenario_packs.py chatgptrest/eval/planning_user_readiness_acceptance.py tests/test_scenario_packs.py tests/test_routes_agent_v3.py tests/test_planning_user_readiness_acceptance.py`

Targeted pytest:

- `./.venv/bin/pytest -q tests/test_scenario_packs.py tests/test_routes_agent_v3.py tests/test_planning_user_readiness_acceptance.py`
- `./.venv/bin/pytest -q tests/test_routes_agent_v3.py tests/test_routes_agent_v3_planning_task_plane.py tests/test_agent_v3_routes.py tests/test_scenario_packs.py tests/test_planning_user_readiness_acceptance.py`

Evidence export:

- `PYTHONPATH=. ./.venv/bin/python ops/export_planning_user_readiness_acceptance_pack.py --output-dir docs/dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v4`

## Frozen User-Facing Statement

After this batch, the honest statement is:

> users can now describe more planning work the way they naturally would. A
> plain-language planning request can land in `planning_general`, and a generic
> "整理今天材料" request can land in `meeting_summary` when the attachment
> metadata already shows it is a meeting transcript. This happens without
> forcing explicit internal task labels.
