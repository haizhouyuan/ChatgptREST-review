# OpenClaw OpenMind Agent Business Integration Test Agent Teams Prompt Walkthrough v2

Date: 2026-03-17

## Why v2 Was Needed

The first Agent Teams prompt was structurally correct, but Claude Code still had a realistic failure mode:

- it could drift back to the earlier public facade development task
- it could stop to ask the user whether to continue
- it could treat Agent Teams availability itself as a blocker instead of degrading gracefully

This v2 prompt hardens against that drift.

## What Changed

The v2 prompt adds:

- an explicit task identity lock
- a rule that this is BI-01 through BI-14 business validation, not old facade development
- a startup self-check so the agent verifies it loaded the correct mission
- a requirement to auto-degrade to single-session execution if Agent Teams is unavailable
- a prohibition on asking the user whether to continue

## New Prompt File

- [2026-03-17_openclaw_openmind_agent_business_integration_test_agentteams_prompt_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-17_openclaw_openmind_agent_business_integration_test_agentteams_prompt_v2.md)
