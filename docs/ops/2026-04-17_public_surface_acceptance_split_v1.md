---
title: Public Surface Acceptance Split
status: active
updated: 2026-04-17
owner: Codex
related:
  - docs/ops/2026-04-17_ChatgptREST执行层治理与provider能力矩阵实施计划_v1.md
  - docs/contracts/2026-04-17_execution_layer_governance_contract_v1.md
---

# 2026-04-17 Public Surface Acceptance Split v1

## Purpose

Separate evidence classes so that probe/smoke transport checks no longer masquerade as production happy-path proof.

## 1. Canonical acceptance

Canonical acceptance is only for the current shared public backend:

- surface: `automation-kernel-v1`
- tools: `automation_*`
- evidence requirement:
  - current-head
  - real business object task
  - fresh happy-path or fresh fail-close
  - requested/effective/rewrite/fallback explainable from formal fields

## 2. Compat acceptance

Compat acceptance only proves that non-canonical legacy surfaces still function during migration.

Examples:

- `advisor_*`
- `/v3/agent/*`
- legacy direct route/provider-selection flows

Compat evidence must not redefine canonical preset or execution-lane truth.

## 3. Probe / smoke

Probe evidence only validates transport or narrow mechanism behavior.

Examples:

- `chatgptrest.eval.public_agent_mcp_validation`
- service initialize / tool-advertisement checks
- duplicate handoff / push receipt continuity probes

Probe evidence rules:

1. use object-framed prompts where possible;
2. default non-premium;
3. never count as production premium success evidence.

## 4. Current repo mapping

### Canonical

- `automation-kernel-v1`
- `automation_ask`
- `automation_result`
- `automation_job_*`

### Compat

- advisor / consult / `agent_v3`
- legacy route-based provider/preset defaults

### Probe

- `public_agent_mcp_validation.py`

## 5. Operational consequence

When a question is “did the new shared backend prove real user value?”, only canonical acceptance counts.

