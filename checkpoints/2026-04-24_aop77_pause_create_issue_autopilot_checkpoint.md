# AOP-77 Pause Create-Issue Governance Autopilot Checkpoint

Date: 2026-04-24
Scope: Multica Assistant Ops safety intervention after ASF-26.

## Decision

The active `Chief Scheduled Governance Reporter` autopilot was paused because its only available execution mode is `create_issue`. This conflicts with the control-plane rule adopted from the Pro review: a successful scheduled sweep may be a correct `no_op`, and issue creation must not be treated as progress.

This is a reversible safety reduction, not an autonomy expansion.

## Target

- Workspace: Assistant Ops `bbc33e1b-a6d8-4724-b29f-b35ac8372572`
- Issue: AOP-77 `65228206-583d-439f-8954-02c938dd80ad`
- Autopilot: `9813cf26-809a-46b4-a4b2-319c8fa81b28`
- Autopilot title: `Chief Scheduled Governance Reporter`
- Trigger: `c42d1760-f2b9-4fdf-8f57-75b208dc3c1e`
- Schedule: `30 9 * * *`, timezone `Asia/Shanghai`

## Evidence

Before the intervention:

- Autopilot status was `active`.
- Execution mode was `create_issue`.
- Next run was `2026-04-25T09:30:00+08:00`.
- Historical runs created AOP-62, AOP-63, and AOP-64.
- Latest sidecar live dry-run after ASF-26 returned `allowed_action: no_op`.
- Latest sidecar live dry-run still showed high drift:
  - `mcp.lanes.chatgptrest.multica_visible`: absent
  - `skills.multica_visible_agent_skills`: empty

## Command

```bash
multica --workspace-id bbc33e1b-a6d8-4724-b29f-b35ac8372572 \
  autopilot update 9813cf26-809a-46b4-a4b2-319c8fa81b28 \
  --status paused \
  --output json
```

## Result

Post-update readback:

- Autopilot status: `paused`
- Execution mode remains: `create_issue`
- Trigger remains visible and enabled for audit.
- No replacement schedule was created.
- No autopilot was deleted.
- No issue transition or live chief wiring was enabled.

## Rationale

The current `create_issue` autopilot cannot express a correct no-op. Leaving it active would keep generating governance issues even while the checked control-plane state says no transition is allowed.

The intended next safe path is a read-only scheduled dry-run reporter that:

- collects a live snapshot,
- runs `chief_advance_one_dry_run.py`,
- writes a local report,
- creates no issue when the result is no-op,
- and never mutates issue status, MCP, skills, auth, runtime, workspace, project, or agent state.

That replacement is not implemented in this checkpoint.

## Remaining Limits

- This pause does not fix Multica-visible MCP or skills drift.
- This pause does not enable self-advance.
- This pause does not replace independent GAC review for high-risk changes.
- The schedule trigger is still present; reactivation must require an explicit sidecar/user decision and a dry-run/no-op capable mechanism.
