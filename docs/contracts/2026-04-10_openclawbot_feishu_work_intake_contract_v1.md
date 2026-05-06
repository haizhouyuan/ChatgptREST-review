# OpenClawBot Feishu Work Intake Contract v1

## Purpose

Freeze the live contract for the Feishu `OpenClawBot` work-only ingress after the `feishu-intake` cutover.

This contract defines the only supported posture for the current Feishu bot:

- work-related asks only
- screenshots/files treated as work materials
- intake lane must hand off into `openmind_advisor_ask`
- execution must land on the existing ChatgptREST `/v3/agent/turn` substrate

## Live Binding

- live OpenClaw state dir: `/home/yuanhaizhou/.home-codex-official/.openclaw`
- live config: `/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json`
- canonical route:
  - `channel=feishu`
  - `accountId=default`
  - `agentId=feishu-intake`

## Intake Agent Contract

- agent id: `feishu-intake`
- workspace: `/vol1/1000/openclaw-workspaces/feishu-intake`
- model: `minimax/MiniMax-M2.7-highspeed`
- tool policy:
  - profile: `minimal`
  - alsoAllow: `openmind_advisor_ask`

## Required Behavior

For work asks, the intake lane must:

1. treat inbound text, screenshots, quoted bodies, and files as work context
2. call `openmind_advisor_ask` before attempting a direct answer
3. default to `goalHint=planning`
4. switch to `research` or `report` only when the user intent is explicit
5. fail closed on clearly non-work asks instead of improvising

## Session Hygiene

- real Feishu traffic must no longer share the `main` agent session namespace
- real Feishu route session keys now resolve under:
  - `agent:feishu-intake:feishu:...`
- validation sessions may exist under:
  - `agent:feishu-intake:main`
  - these do not contaminate real Feishu chat sessions

## Evidence Required

The cutover is not considered ready without all of:

1. live config shows `feishu/default -> feishu-intake`
2. `feishu-intake` workspace files contain work-only + handoff-first guidance
3. meeting-intake smoke shows:
   - `route_session_key = agent:feishu-intake:feishu:chat:...`
   - `openmind_advisor_ask` present in the bridge contract
4. live intake-agent transcript shows first tool call = `openmind_advisor_ask`

## Explicit Non-Goals

This contract does not claim:

- non-work Feishu support
- education / finbot / personal lanes
- legacy `chatgptrest.advisor.feishu_handler` parity
- entity-grade recall completeness
- final answer quality for every work ask

## Cutover Outcome

After this contract, the supported operator message is:

- `OpenClawBot` Feishu ingress is ready for formal work-only usage.

