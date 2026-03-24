# Phase 16 / Phase 17 Scoped Release Review v1

## Verdict

This package can be accepted.

`Phase 16` closes the exact live-gap that remained after the earlier `Phase 12`
 review.

`Phase 17` is now the correct formal gate to use for the current public release
 decision, replacing any attempt to treat `Phase 12` as the final public-ready
 signal.

## What Is Correct

### 1. Phase 16 is a real live write-path gate, not just a report reader

This phase directly exercises the live public `/v3/agent/turn` surface and
proves the current write-guard stack in order:

- unauthenticated request → `401`
- authenticated but unallowlisted client → `403 client_not_allowed`
- authenticated + allowlisted but missing trace headers → `400 missing_trace_headers`
- authenticated + allowlisted + traced request → `200`, still reaching
  planning `clarify`

Code evidence:

- [public_auth_trace_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/public_auth_trace_gate.py#L47)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1174)
- [write_guards.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/write_guards.py#L100)
- [write_guards.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/write_guards.py#L186)

Artifact evidence:

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase16_public_auth_trace_gate_20260322/report_v1.json)

This is the key correction to the earlier Phase 12 review. The missing live
 write-gate proof is now present.

### 2. Phase 17 is the right gate to reference now

`Phase 17` aggregates the public-facing release decision over:

- `Phase 15` public surface launch gate
- `Phase 16` public auth/allowlist/trace gate

Code evidence:

- [scoped_public_release_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/scoped_public_release_gate.py#L11)
- [scoped_public_release_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/scoped_public_release_gate.py#L45)

Doc evidence:

- [2026-03-22_phase17_scoped_public_release_gate_completion_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-22_phase17_scoped_public_release_gate_completion_v1.md#L5)

So the revised interpretation is correct:

- `Phase 12` = historical aggregated core-ask gate
- `Phase 17` = current scoped public release gate

## Residual Note

### 1. Phase 17 is still an aggregated gate by design

Severity: `low`

Like `Phase 15`, the implementation reads prior artifact bundles rather than
 rerunning every lower-level validator itself.

Evidence:

- [scoped_public_release_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/scoped_public_release_gate.py#L45)

This is not a defect in the current framing, because the gate is explicitly
 named and documented as `scoped`, not `full-stack` or `fresh-replay`.

It only becomes a problem if someone later overstates it as:

- full-stack deployment proof
- OpenClaw dynamic replay proof
- heavy execution approval

The current docs do not make that mistake.

## Independent Judgment

The independent judgment you wrote is correct and aligned with the current repo
 state.

The shortest accurate summary is:

- the earlier downgrade of `Phase 12` remains valid
- the missing public-surface gaps were materially closed by `Phase 13-16`
- the current formal launch reference should be `Phase 17`
- `Phase 17` is strong enough for a scoped public release call, but should stay
  scoped in wording
