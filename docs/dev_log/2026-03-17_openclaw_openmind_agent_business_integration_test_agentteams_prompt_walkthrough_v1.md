# OpenClaw OpenMind Agent Business Integration Test Agent Teams Prompt Walkthrough v1

Date: 2026-03-17

## What I Added

Added an Agent Teams-specific Claude Code prompt for executing the full OpenClaw / OpenMind unified agent business integration test plan.

## Why

This test plan is a better fit for Agent Teams than a normal single-agent development task because:

- most business lanes are independent
- the work is evidence-heavy
- there is a natural split between HTTP, MCP, CLI/wrapper, OpenClaw plugin, and auth/fault scenarios
- failures can be triaged centrally by a lead lane before deciding whether code fixes are needed

## Prompt File

- [2026-03-17_openclaw_openmind_agent_business_integration_test_agentteams_prompt_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-17_openclaw_openmind_agent_business_integration_test_agentteams_prompt_v1.md)

## Prompt Design

The prompt explicitly defines:

- a `test-lead` lane
- an `http-facade-lane`
- an `mcp-wrapper-lane`
- an `openclaw-plugin-lane`
- an `auth-fault-report-lane`

It also requires:

- automated gate suites before business execution
- BI-01 through BI-14 evidence collection
- code fixes plus regression coverage when failures are repo-local
- explicit blocker evidence when failures are external
