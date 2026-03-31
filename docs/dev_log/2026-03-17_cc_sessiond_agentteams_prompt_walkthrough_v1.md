# CC-Sessiond Agent Teams Prompt Walkthrough v1

Date: 2026-03-17

## What Changed

Added an Agent Teams-specific Claude Code prompt for the `cc-sessiond` full implementation task.

## Why

The plain single-agent prompt was sufficient for one lane, but this task has a better parallelization shape:

- app wiring and integration
- backend adapters
- state/lifecycle mechanics
- direct tests
- docs

At the same time, this task is risky if multiple agents edit the same core files in parallel.

So the Agent Teams prompt explicitly defines:

- one integration lead lane
- supporting lanes with bounded write scopes
- ordered integration phases
- a quality-first review bar

## Added Document

- [2026-03-17_cc_sessiond_full_implementation_agentteams_prompt_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-17_cc_sessiond_full_implementation_agentteams_prompt_v1.md)

## Intended Use

Open Claude Code in the repo and paste the Agent Teams prompt directly. It is meant to replace the plain prompt only when running with Agent Teams enabled.
