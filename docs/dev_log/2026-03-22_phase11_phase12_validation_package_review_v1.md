# Phase 11 / Phase 12 Validation Package Review v1

## Verdict

Phase 11 can be accepted as written.

Phase 12 is directionally correct and the package is green at the current HEAD,
but the launch-gate label needs to stay narrow:

- acceptable label: `aggregated core-ask launch gate`
- too-strong label: `live core-ask deployment proof`

## Findings

### 1. Phase 12 GO is an aggregated evidence gate, not an independent current-state replay gate

Severity: `medium`

The core gate implementation reads previously generated validation artifacts and
checks only their aggregate counters, plus two live health endpoints.

Code evidence:

- [core_ask_launch_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/core_ask_launch_gate.py#L70)
- [core_ask_launch_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/core_ask_launch_gate.py#L126)
- [core_ask_launch_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/core_ask_launch_gate.py#L194)
- [run_core_ask_launch_gate.py](/vol1/1000/projects/ChatgptREST/ops/run_core_ask_launch_gate.py#L17)

Document evidence:

- [2026-03-22_phase12_core_ask_launch_gate_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-22_phase12_core_ask_launch_gate_v1.md#L15)
- [2026-03-22_phase12_core_ask_launch_gate_completion_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-22_phase12_core_ask_launch_gate_completion_v1.md#L33)
- [2026-03-22_phase12_core_ask_launch_gate_completion_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-22_phase12_core_ask_launch_gate_completion_walkthrough_v1.md#L5)

What this means:

- a stale green artifact bundle can keep Phase 12 green across later regressions
- the gate does not itself rerun Phase 7 to Phase 11 validators
- the gate therefore proves `aggregated evidence + current health`, not
  `fresh replay of all covered surfaces`

This does not invalidate the current package result, because I independently
re-ran the referenced tests and runners at the current HEAD and they remained
green. It does mean the wording should stay narrow.

### 2. Phase 12 still does not exercise the authenticated live `/v3/agent/turn` seam

Severity: `medium`

The live checks in Phase 12 are:

- `GET /healthz`
- `GET /v2/advisor/health`

They do not include an authenticated live `POST /v3/agent/turn` canary.

Code evidence:

- [core_ask_launch_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/core_ask_launch_gate.py#L100)
- [2026-03-22_phase12_core_ask_launch_gate_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-22_phase12_core_ask_launch_gate_v1.md#L17)

Runtime evidence from this review:

- `GET http://127.0.0.1:18711/healthz` returned `200 {"ok":true,"status":"ok"}`
- unauthenticated `POST http://127.0.0.1:18711/v3/agent/turn` returned `401`

The `401` is expected under strict auth, so this is not a route bug. The point
is narrower: current Phase 12 health does not prove the authenticated public ask
surface is usable on the live service.

## What Passed Cleanly

Phase 11’s scope and conclusion are accurate.

The branch pack does what it says it does:

- public clarify stays on `needs_followup/clarify`
- KB direct completes on `provider=kb`
- no-pack controller fallback is correctly frozen as `route=hybrid`
- team fallback is correctly frozen as `execution_kind=team`

Evidence:

- [2026-03-22_phase11_branch_coverage_validation_completion_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-22_phase11_branch_coverage_validation_completion_v1.md#L27)
- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase11_branch_coverage_validation_20260322/report_v1.json)

## Independent Judgment

This package is green enough to support the next work split, but the Phase 12
headline should be read as:

- `core ask aggregated launch gate: GO`

not as:

- `live authenticated public ask gate: GO`
- `fresh full-package replay gate: GO`

That makes the next package boundary still correct:

1. public agent MCP usability
2. strict ChatGPT Pro smoke blocking

A later package should also add one authenticated live `/v3/agent/turn`
clarify-safe canary if the goal is to promote this from a code-level gate to a
deployment-level gate.
