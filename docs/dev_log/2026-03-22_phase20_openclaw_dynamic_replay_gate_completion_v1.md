# Phase 20 Completion: OpenClaw Dynamic Replay Gate v1

## Result

`Phase 20 = GO`

OpenClaw dynamic replay is now validated at the scoped public-surface level.

## What changed

- Added [openclaw_dynamic_replay_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/openclaw_dynamic_replay_gate.py)
- Added [run_openclaw_dynamic_replay_gate.py](/vol1/1000/projects/ChatgptREST/ops/run_openclaw_dynamic_replay_gate.py)
- Added [test_openclaw_dynamic_replay_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_dynamic_replay_gate.py)
- Updated [runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md) allowlist guidance to include `openclaw-advisor`
- Updated [chatgptrest.env.example](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest.env.example) with the explicit public-client allowlist example

## Runtime fix applied

The first live replay exposed a real integration gap:

- `openclaw-advisor` was not present in `CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST`
- live replay failed with `403 client_not_allowed`

The runtime allowlist in `~/.config/chatgptrest/chatgptrest.env` was updated to include `openclaw-advisor`, and `chatgptrest-api.service` was restarted before re-running the gate.

## Gate result

Report:

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase20_openclaw_dynamic_replay_gate_20260322/report_v1.json)
- [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase20_openclaw_dynamic_replay_gate_20260322/report_v1.md)

Summary:

- checks: `3`
- passed: `3`
- failed: `0`

Covered checks:

1. dynamic tool registration
2. dynamic contract capture
3. live planning clarify replay

## Boundary

This is now sufficient to say:

- OpenClaw plugin dynamic replay against the current public surface is `GO`

This still does not prove:

- full-stack external-provider delivery
- OpenClaw full session replay
- heavy execution lane approval
