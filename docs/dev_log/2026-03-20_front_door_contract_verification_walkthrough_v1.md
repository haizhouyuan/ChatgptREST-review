# 2026-03-20 Front Door Contract Verification Walkthrough v1

## What I checked

This verification re-audited:

- [2026-03-20_front_door_contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_v1.md)

I focused on five questions:

1. Is `/v3/agent/turn` really the current public live ask front door?
2. Is `/v3/agent/turn` really doing live ingress work instead of thin forwarding?
3. Is `/v2/advisor/ask` really the retained internal smart-execution lane?
4. Is `/v2/advisor/advise` really the retained internal graph/controller lane?
5. Did the document accidentally omit other still-live ingress or mix distinct Feishu channels together?

## What held up

These parts of the document survived verification:

- `/v3/agent/turn` is the public live ask front door for OpenClaw, public MCP, CLI `agent turn`, and coding-agent style callers
- `/v3/agent/turn` is not a thin facade; it already holds contract synthesis, clarify gate, and several direct dispatch branches
- `/v2/advisor/ask` is still the active internal smart-execution/compatibility lane
- `/v2/advisor/advise` is still the active internal graph/controller lane
- Feishu WS still points to `/v2/advisor/advise`

That means the primary three-way split is materially sound.

## What did not hold up cleanly

The remaining problems are in the residual ingress picture.

### 1. `/v1/advisor/advise` was left out

The target document talks as if the live split is now just three routes.

That is too clean relative to the codebase. A legacy wrapper ingress still exists:

- REST route exists
- MCP tool exists
- CLI `advisor advise` exists
- ops/e2e script still uses it

So the doc works as a primary split decision, but not as a complete ingress inventory unless it explicitly scopes v1 legacy out.

### 2. Webhook was folded into the wrong route

The document lets `/v2/advisor/advise` stand in for webhook-style integrations.

But the code separates these channels:

- Feishu WS gateway calls `/v2/advisor/advise`
- Feishu webhook handler is `/v2/advisor/webhook`

So the contract currently mixes two distinct ingress channels that should stay separate.

## Why this matters

This matters because the next proposed decision is `session_truth_decision_v1`.

If `session_truth` is built on top of a front-door contract that:

- ignores a still-live legacy ingress
- mixes WS and webhook into one route

then the next document will likely undercount ledgers, telemetry sources, and recovery surfaces again.

## Deliverables

This verification added:

- [2026-03-20_front_door_contract_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_verification_v1.md)
- [2026-03-20_front_door_contract_verification_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_verification_walkthrough_v1.md)

## Test Note

This was a documentation and code-evidence verification task. No code was changed, and no test suite was run.
