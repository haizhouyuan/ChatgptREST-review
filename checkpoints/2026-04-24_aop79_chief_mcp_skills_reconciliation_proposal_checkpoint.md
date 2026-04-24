# AOP-79 Chief MCP/Skills Reconciliation Proposal Checkpoint

Date: 2026-04-24
Scope: static proposal for remaining Hermes chief metadata drift.

## Decision

AOP-79 produced a static reconciliation proposal only. No live Multica agent, MCP, skill, runtime, auth, project, workspace, or Hermes config mutation was performed.

The current safe decision remains `no_op` because the live dry-run still detects high drift in Multica-visible MCP and skills metadata.

## Target

- Workspace: Assistant Ops `bbc33e1b-a6d8-4724-b29f-b35ac8372572`
- Issue: AOP-79 `4c9f9904-e7fd-4d4b-ad5e-24134d9218f3`
- Chief agent: `hermes-chief-of-staff` `48251656-cdc5-48e3-804d-4fd338614b7b`
- Proposal: `docs/control_plane/metadata_reconciliation/chief_mcp_skills_reconciliation_proposal_2026-04-24.json`
- Pro follow-up job: `3460226e79c1493fae0c91596cdc916c`
- Failed prior Pro follow-up attempts:
  - `2e840263e09144b4bdcfe687d28aa8bc`: rejected because the prompt referenced local paths without declared attachments.
  - attachment retry: rejected because the automation service did not allow attaching files from the local repo path.

## Current Evidence

Latest local dry-run after AOP-78:

```json
{
  "allowed_action": "no_op",
  "dry_run_only": true,
  "eligible_count": 0,
  "drift_count": 2,
  "proposed_issue_id": null
}
```

The two remaining high drift items are:

- `mcp.lanes.chatgptrest.multica_visible`: absent
- `skills.multica_visible_agent_skills`: empty

Hermes local config allowlist confirms:

- model provider: `openai-codex`
- model default: `gpt-5.5`
- reasoning effort: `xhigh`
- MCP server names: `chatgptrest`
- external skill dirs: `/vol1/1000/projects/planning/hermes-skills`

Multica live chief agent confirms:

- model: `gpt-5.5`
- runtime: Hermes
- `mcp_config`: null
- `skills`: empty

## Proposal Summary

The proposal deliberately separates candidate actions from executable payloads:

- Writing a non-secret summary into `agent.mcp_config` is **not recommended** because `mcp_config` appears semantically intended for executable MCP config, not metadata summaries.
- Writing actual executable `agent.mcp_config` is **blocked** until a secret-safe MCP contract and independent gate exist.
- Changing the checker to accept Hermes local config as the MCP source of truth is **blocked** because it weakens the current Multica-visible control-plane rule.
- Creating and assigning workspace skills to chief is **blocked** because even restrictive skill assignment is live prompt/behavior mutation.
- The only recommended current action is static proposal plus waiting for independent Pro/GAC decision.

## Validation

Commands run:

```bash
python3 -m json.tool docs/control_plane/metadata_reconciliation/chief_mcp_skills_reconciliation_proposal_2026-04-24.json >/dev/null
rg -n "sk-[A-Za-z0-9_-]{16,}|api[_-]?key\\s*[:=]|access[_-]?token\\s*[:=]|refresh[_-]?token\\s*[:=]|Authorization\\s*:|Bearer\\s+[A-Za-z0-9._~+/-]{10,}|password\\s*[:=]" docs/control_plane/metadata_reconciliation/chief_mcp_skills_reconciliation_proposal_2026-04-24.json
python3 ops/scripts/chief_scheduled_dry_run_report.py --output-dir /vol1/maint/state/control_plane/sweeps --stamp sidecar-recheck-20260424T1322Z --run-id sidecar-recheck-after-aop78
```

Results:

- Proposal JSON parse: passed.
- Secret-pattern scan: no matches.
- Latest dry-run remains `no_op` with two high drift items.

## Safety Boundary

This checkpoint does not:

- create workspace skills,
- assign skills to chief,
- update `agent.mcp_config`,
- change `chief_manifest.v0.json`,
- relax the dry-run checker,
- mutate Hermes config,
- mutate Multica agent/runtime/auth/MCP/permissions,
- or unblock self-advance.

## Remaining Limits

- AOP-79 does not resolve the drift; it makes the next live change reviewable.
- The Pro follow-up is pending and should be read before any live reconciliation.
- GAC remains the preferred independent gate. Codex GPT-5.5 xhigh fallback remains Grade-C and cannot clear high-risk live control-plane changes alone.
- If the user explicitly accepts a degraded gate, the acceptance should be recorded before any live mutation.
