# 2026-03-10 Role Pack Runtime Live Validation

## Scope

This checkpoint validates the post-`1A/1B/1C` runtime state rather than the
plumbing alone:

- live OpenClaw/OpenMind verifier on `lean`
- live `/v2/memory/capture` + `/v2/context/resolve` role isolation
- live `/v2/advisor/ask` role propagation
- continuity observability wrapper smoke

## Important runtime finding

An earlier live probe showed `role_id` missing from `/v2/context/resolve`
responses and `research` incorrectly seeing a `devops` memory. The root cause
was not a design bug; `chatgptrest-api.service` was still running an older
process. After restarting the API service, live behavior matched the current
code and tests.

## Live verifier

Command:

```bash
./.venv/bin/python ops/verify_openclaw_openmind_stack.py \
  --state-dir /vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw \
  --expected-topology lean
```

Result artifacts:

- [verify_openclaw_openmind_stack.json](/vol1/1000/projects/ChatgptREST/artifacts/verify_openclaw_openmind/20260310T090001Z/verify_openclaw_openmind_stack.json)
- [verify_openclaw_openmind_stack.md](/vol1/1000/projects/ChatgptREST/artifacts/verify_openclaw_openmind/20260310T090001Z/verify_openclaw_openmind_stack.md)

Key outcomes:

- `role_devops_recall_reply`: passed
- `role_research_recall_reply`: passed
- `main_no_sessions_spawn`: passed
- `main_no_subagents_tool`: passed
- `advisor_unauth_ingress_rejected`: passed

## Live role isolation smoke

Actions:

1. Captured a memory with `role_id=devops`
2. Queried `/v2/context/resolve` three ways:
   - `role_id=devops`
   - `role_id=research`
   - no `role_id`
3. Queried `/v2/advisor/ask` with `role_id=devops`

Observed results:

```json
{"role":"devops","meta_role":"devops","kb_scope_mode":"hint","captured_blocks":1,"has_marker":true}
{"role":"research","meta_role":"research","kb_scope_mode":"hint","captured_blocks":0,"has_marker":false}
{"role":"","meta_role":"","kb_scope_mode":"off","captured_blocks":1,"has_marker":true}
{"advisor_role_id":"devops","route":"hybrid","intent_top":null}
```

Interpretation:

- `devops` role memory is live and queryable
- `research` is isolated from `devops` captures
- no-role requests remain fail-open
- Advisor runtime propagates `role_id`

## Continuity wrapper smoke

Command:

```bash
PYTHONPATH=. ./.venv/bin/python ops/controller_lane_wrapper.py \
  --lane-id verifier \
  --summary "wrapper smoke" \
  --artifact-path /tmp/controller-lane-wrapper-smoke.txt \
  -- bash -lc 'echo ok > /tmp/controller-lane-wrapper-smoke.txt'
```

Observed digest afterward:

```text
- main: working — no summary
- scout: idle — no summary
- verifier: completed — wrapper smoke completed
- worker-1: idle — no summary
```

This confirms continuity is now genuinely usable as observability-first fleet
tracking, without pretending automatic restart is ready.

## Current conclusion

Blueprint status at this checkpoint:

- `1A`: landed and live
- `1B`: key identity write-path bug fixed
- `1C`: KB tag governance landed; runtime behavior is `hint`, not hard enforce
- role runtime integration: live and verified
- continuity: observability-first, with actual wrapper-based heartbeat/report

Remaining work is no longer about role-pack core correctness. It is about
productization choices on top of a now-working base.
