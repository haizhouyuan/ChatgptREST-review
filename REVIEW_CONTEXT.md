# Multica / Hermes Chief Control Plane Review Packet

Date: 2026-04-24
Audience: ChatGPT Pro and Gemini Deep Think external reviewers.
Decision to support: whether the current Multica/Hermes chief control-plane design is safe to continue, and what exact next changes should be allowed or blocked.
Objective: prevent drift while enabling a stable personal assistant / development-team harness.

## User Goal
The user wants Multica to manage development execution while Hermes chief acts as the long-running control entrance. The immediate objective is not broad autonomous execution. The objective is a reliable, observable harness that can read issues, route work, run quality gates, and eventually reduce sidecar intervention.

## Current Architecture
- Multica is the execution/control board with two workspaces: assistant-ops and assistant-factory.
- Hermes chief-of-staff is the front controller / proposer, not supposed to be an unchecked executor.
- Codex sidecar currently implements rescue, evidence packing, dry-run checking, and external review submission.
- Scheduled create-issue autopilot was paused. It was replaced by a local read-only dry-run reporter.
- Deterministic control-plane pieces now exist: chief manifest, live snapshot exporter, advance_one dry-run checker, proof ledger, sidecar knowledge register.

## Important Current Facts
- Chief agent is `hermes-chief-of-staff`, model `gpt-5.5`, reasoning effort `xhigh` in Hermes config and Multica-visible model metadata.
- Chief Multica metadata still has `mcp_config = null` and `skills = []`.
- Hermes local config has a `chatgptrest` MCP lane and external skill dir `/vol1/1000/projects/planning/hermes-skills`.
- Latest dry-run after red-team swap remains `allowed_action = no_op`, with high drift for MCP visibility and skill visibility.
- User decided GAC Claude red-team is too quota-limited and replaced it with `redteam-gpt55-xhigh-primary`, a Codex runtime agent using `gpt-5.5` + `xhigh`.
- Because the primary red-team is now same-family with Codex sidecar, model independence is degraded. The design must rely more on deterministic gates.

## Why This Review Exists
A prior short ChatGPT Pro ask advised No-Go for live MCP/skills reconciliation, but the user judged the context insufficient. This packet is the corrected fuller evidence package. Treat the prior short answer as historical context, not binding authority.

## Specific Questions
1. Is the current separation between Hermes chief, Multica board, deterministic checker, red-team, and sidecar conceptually sound?
2. Given `agent.mcp_config = null` while Hermes local config has MCP lanes, should we write anything into Multica `agent.mcp_config`, or should we create a separate non-executable metadata/manifest path?
3. Given Multica `skills = []` while Hermes has local/external skills, should we assign workspace skills to chief now, or keep this blocked until skill allowlist/review/rollback exists?
4. After replacing GAC with Codex `gpt-5.5 xhigh`, what gate policy is still credible? What must be deterministic rather than model-reviewed?
5. Is the current dry-run/no-op harness good enough as a near-term harness foundation, or is it missing a critical state transition/audit/lock concept?
6. What is the minimal safe next step? Be concrete: Go/No-Go for live MCP metadata, live skills assignment, checker relaxation, or only static artifacts.
7. Are we over-governing with too much prose/issue machinery, or under-constraining the runtime? Identify the highest-leverage correction.

## Required Review Style
- Findings first.
- Evidence-based: cite attached file paths and observations from the packet.
- Do not use web search unless you need public Multica repo clarification; if used, separate public-source claims from packet evidence.
- Do not assume access to the local machine.
- Do not recommend uploading secrets or raw auth configs.
- Prefer concrete next actions and acceptance gates over abstract advice.
