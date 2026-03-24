# OpenClaw + OpenMind Role Pack Runtime Review Bundle

Date: 2026-03-10
Repo: `ChatgptREST`
Source commit under review: see `REVIEW_SOURCE.json` in the synced public review branch
Review repo: `https://github.com/haizhouyuan/ChatgptREST-review`
Review branch: supplied by the review prompt for the current synced mirror branch

## Goal

Review whether the current OpenClaw/OpenMind baseline is now ready to accept
the first two explicit role packs:

- `devops`
- `research`

The target is **not** a general multi-agent platform. The target is a
controller-centric shell where:

- OpenClaw remains the shell/runtime
- OpenMind remains the cognition substrate
- `main` remains the only persistent controller
- role packs are explicit business-context overlays
- continuity remains observability-first, not auto-restart automation

## Scope under review

### In scope

- `1A` role pack core
- `1B` identity write-path fix
- `1C` KB tag governance + soft hint mode
- runtime role propagation into live OpenMind entrypoints
- continuity observability with wrapper-based heartbeat/report

### Explicitly out of scope

- coordinator role
- automatic `role_hint` routing
- role-aware EvoMap scoring
- role-aware Policy profiles
- hard-enforced KB filtering
- automatic lane restart/resume promises

## Review questions

1. Is the current role-pack design coherent for a single-user system?
2. Is `source.role` now correctly separated from `source.agent`?
3. Is `KB` currently in the right place on the `off -> hint -> enforce` path?
4. Does the live runtime evidence actually prove that `devops` and `research`
   behave differently at the memory layer?
5. Is continuity correctly positioned as an observability sidecar rather than a
   second controller?
6. Are there any remaining blockers before this should be accepted as the
   production baseline for role-pack-enabled OpenClaw/OpenMind use?

## Primary sources

- role blueprint:
  - [`docs/reviews/2026-03-10_agent_role_architecture_blueprint_v4.md`](../reviews/2026-03-10_agent_role_architecture_blueprint_v4.md)
- `1A` role pack implementation:
  - [`chatgptrest/kernel/team_types.py`](../../chatgptrest/kernel/team_types.py)
  - [`chatgptrest/kernel/role_context.py`](../../chatgptrest/kernel/role_context.py)
  - [`chatgptrest/kernel/role_loader.py`](../../chatgptrest/kernel/role_loader.py)
  - [`config/agent_roles.yaml`](../../config/agent_roles.yaml)
  - [`chatgptrest/kernel/memory_manager.py`](../../chatgptrest/kernel/memory_manager.py)
  - [`chatgptrest/cognitive/context_service.py`](../../chatgptrest/cognitive/context_service.py)
  - [`tests/test_role_pack.py`](../../tests/test_role_pack.py)
  - [`docs/dev_log/2026-03-10_1A_role_pack_walkthrough.md`](../dev_log/2026-03-10_1A_role_pack_walkthrough.md)
- `1B/1C` governance:
  - [`docs/dev_log/2026-03-10_1B_1C_identity_kb_tags_walkthrough.md`](../dev_log/2026-03-10_1B_1C_identity_kb_tags_walkthrough.md)
  - [`chatgptrest/kb/retrieval.py`](../../chatgptrest/kb/retrieval.py)
  - [`chatgptrest/kb/hub.py`](../../chatgptrest/kb/hub.py)
  - [`scripts/backfill_kb_tags.py`](../../scripts/backfill_kb_tags.py)
- runtime integration:
  - [`chatgptrest/api/routes_advisor_v3.py`](../../chatgptrest/api/routes_advisor_v3.py)
  - [`chatgptrest/api/routes_cognitive.py`](../../chatgptrest/api/routes_cognitive.py)
  - [`openclaw_extensions/openmind-memory/index.ts`](../../openclaw_extensions/openmind-memory/index.ts)
  - [`openclaw_extensions/openmind-advisor/index.ts`](../../openclaw_extensions/openmind-advisor/index.ts)
  - [`scripts/rebuild_openclaw_openmind_stack.py`](../../scripts/rebuild_openclaw_openmind_stack.py)
- continuity:
  - [`ops/controller_lane_continuity.py`](../../ops/controller_lane_continuity.py)
  - [`ops/controller_lane_wrapper.py`](../../ops/controller_lane_wrapper.py)
  - [`config/controller_lanes.json`](../../config/controller_lanes.json)
  - [`docs/ops/controller_lane_continuity_v0_1.md`](../ops/controller_lane_continuity_v0_1.md)
  - [`docs/dev_log/2026-03-10_controller_lane_wrapper_v0_2.md`](../dev_log/2026-03-10_controller_lane_wrapper_v0_2.md)

## Live evidence

- verifier artifacts:
  - [`docs/reviews/openclaw_openmind_verifier_lean_20260310.md`](./openclaw_openmind_verifier_lean_20260310.md)
  - [`docs/reviews/openclaw_openmind_verifier_lean_20260310.json`](./openclaw_openmind_verifier_lean_20260310.json)
- runtime validation walkthrough:
  - [`docs/dev_log/2026-03-10_role_pack_runtime_live_validation.md`](../dev_log/2026-03-10_role_pack_runtime_live_validation.md)

## Current claimed state

- `main` is still the only persistent controller
- `maintagent` remains optional watchdog-only
- `devops` and `research` are explicit role packs, not persistent agents
- live `/v2/context/resolve` behavior is now:
  - `role_id=devops` -> role-scoped memory visible
  - `role_id=research` -> `devops` captures hidden
  - no role -> fail-open behavior remains
- live `/v2/advisor/ask` propagates `role_id`
- live verifier passes role capture / role recall / negative tool probes
- continuity now has:
  - manifest onboarding
  - digest/status
  - wrapper-based heartbeat/report
  - no claim of reliable auto-resume

## What changed since the older topology review

The older topology review focused on:

- collapsing `lean` / `ops`
- removing persistent role agents
- proving `main` had no `sessions_spawn`/`subagents`

This review adds the next layer:

- first explicit role packs
- role-aware memory query/write behavior
- KB tag governance reaching `hint`
- continuity becoming actually observable in lane execution

## Reviewer guidance

Please judge this as a **single-user production baseline**. Do not require a
general agent-team framework or automatic coordinator role. The intended shape
is deliberately smaller:

- one controller
- explicit role packs
- soft KB scoping
- sidecar continuity

If you conclude FAIL, separate:

- blocking implementation faults
- packaging / review-input issues
- “future improvements” that are not required for this baseline
