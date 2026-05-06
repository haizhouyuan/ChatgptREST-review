---
title: Execution Layer Governance Contract
status: active
updated: 2026-04-17
owner: Codex
related:
  - docs/contracts/2026-04-17_provider_capability_matrix_contract_v1.md
  - docs/ops/2026-04-17_ChatgptREST执行层治理与provider能力矩阵实施计划_v1.md
---

# 2026-04-17 Execution Layer Governance Contract v1

## 1. Purpose

Freeze the canonical `automation-kernel-v1` execution contract so that callers, runtime, and evidence all agree on:

1. who requested the execution lane;
2. whether premium execution was allowed;
3. which provider/preset actually ran after capability normalization;
4. whether runtime fallback happened.

This contract upgrades governance from “preset folklore” to execution-layer truth.

## 2. Scope

Applies to the canonical public MCP automation lane:

- `automation_ask`
- `automation_result`
- `/v1/jobs/{job_id}`
- `/v1/jobs/{job_id}/result`
- `_job_local_snapshot(...)` consumers on the MCP background-wait / push path

It does **not** make legacy surfaces canonical. `advisor/consult/agent_v3` remain compat surfaces.

## 3. Canonical request fields

`automation_ask` now accepts these execution-governance fields in addition to `provider/preset`:

- `requested_execution_lane`
- `premium_allowed`
- `task_object_contract`

### 3.1 Allowed canonical automation lanes

For `automation-kernel-v1` web asks, the only supported execution lanes are:

- `web_standard`
- `web_premium`
- `deep_research`

Other system-wide lanes (`local`, `coding_agent`, `compat_legacy`) are not valid for canonical web automation submit.

### 3.2 Lane derivation rules

Effective execution lane is derived from provider-effective truth:

- `deep_research=true` => `deep_research`
- premium effective preset => `web_premium`
- otherwise => `web_standard`

### 3.3 Fail-closed rules

Canonical public MCP must fail closed when:

1. `requested_execution_lane` is unsupported for automation;
2. caller explicitly requested one lane but provider-effective truth implies another lane;
3. `premium_allowed=false` while effective lane is premium (`web_premium` / `deep_research`).

## 4. Canonical truth fields

The following fields are first-class governance outputs on receipt / job view / result view:

- `requested_execution_lane`
- `effective_execution_lane`
- `requested_provider`
- `effective_provider`
- `requested_preset`
- `effective_preset`
- `selection_source`
- `rewrite_source`
- `rewrite_reason`
- `fallback_from`
- `fallback_to`
- `fallback_reason`
- `provider_capability_profile`
- `premium_allowed`
- `premium_justified`
- `task_object_contract`

## 5. Semantics

### 5.1 `requested_*`

What the caller explicitly asked for.

### 5.2 `effective_*`

What the system accepted after capability normalization, before runtime fallback.

Examples:

- `chatgpt + auto` => `effective_preset=auto`
- `gemini + auto` => `effective_preset=pro`

### 5.3 `rewrite_*`

Static normalization before execution. Current canonical source:

- `provider_capability_matrix`

Example:

- `gemini + auto` => `rewrite_source=provider_capability_matrix`, `rewrite_reason=gemini_alias_to_pro`

### 5.4 `fallback_*`

Runtime change after execution started.

Examples:

- ChatGPT Pro fallback to a lower premium preset;
- Gemini `deep_think -> pro` fallback.

Fallback must remain lane-local and be visible in formal outputs.

## 6. Object contract

`task_object_contract` is caller-owned context describing the business object, reader, purpose, or evidence boundary for this automation ask.

It is advisory for execution governance and evidence readability; it does not replace prompt text.

## 7. Rollout meaning

This contract means:

1. caller/Hermes owns lane authorization;
2. ChatgptREST owns capability normalization inside the chosen lane;
3. runtime fallback cannot silently rewrite governance truth.

