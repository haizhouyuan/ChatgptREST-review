# 2026-03-25 Public Agent MCP Client Experience Issue Pack Walkthrough v1

## What changed

Captured a real coding-agent usage trace of the public advisor-agent MCP surface and converted it into a service-side issue pack.

Files added:

1. `docs/dev_log/2026-03-25_public_agent_mcp_client_experience_issue_pack_v1.md`

## Why

Recent public MCP hardening work successfully made the public MCP surface the right front door for coding agents.

However, a real client workflow using:

1. one attached markdown review packet
2. `advisor_agent_turn`
3. long-running Pro report generation

still exposed practical ergonomics gaps that are easy to miss in happy-path validations.

This walkthrough exists so the service team can distinguish:

1. what is already working correctly
2. what is still rough for real coding-agent operators
3. what should be prioritized next

## Main findings

1. Public MCP accepted and routed the task correctly.
2. Intake/control-plane metadata is already strong.
3. `attachments` validation is too strict ergonomically for common one-file cases.
4. `sync` auto-degrading to background execution is correct but not communicated clearly enough.
5. The public surface still needs a true wait primitive and richer progress telemetry for long-running report-grade turns.

## Outcome

The resulting issue pack recommends prioritizing:

1. attachment ergonomics
2. sync-to-background handoff clarity
3. advisor-session wait/progress improvements
4. stronger northbound schema alignment
