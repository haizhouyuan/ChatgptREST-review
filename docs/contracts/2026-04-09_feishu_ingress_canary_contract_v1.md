# Feishu Ingress Canary Contract v1

Date: 2026-04-09  
Status: canonical hard-gate contract for the current Feishu/OpenClaw ingress canary

## Purpose

Turn Feishu ingress testing into a controlled experiment instead of an informal "try it and see".

## Scope

Current canary scope:

- channel posture: `Feishu/OpenClaw ingress`
- runtime substrate: `ChatgptREST + OpenClaw bridge`
- project scope: `planning`
- memory reset mode for test replays: `fresh identity`

Current seeded replay cases:

- `绿源来访准备`
- `钛虎机器人关节模组合作`
- `两轮车车轮市场竞争分析`

Case registry:

- `ops/data/feishu_ingress_canary_cases_v1.json`

Replay runner:

- `ops/run_feishu_ingress_canary.py`

## Hard gates

### Sample gate

- watch window: `7 days`
- minimum real asks: `20`
- minimum covered families:
  - `visit/cooperation prep`
  - `research/analysis`
  - `project diagnosis`
  - `leadership/report brief`

### Quality gate

- subjective operator satisfaction: `>= 70%`
- direct-usability rate: `>= 70%`
- first-turn closure rate: `>= 70%`

First-turn closure means the answer gives a usable combination of:

- judgment
- key preparation / analysis points
- explicit pending confirmations
- suggested reply or next-step framing

### Safety gate

- authority violations: `0`
- severe cross-project mismatch: `0`
- severe entity mismatch: `0`

### Runtime gate

The canary must stay within the current substrate contract:

- `packet = pass`
- `recall = pass`
- `crystal = pass`
- `promotion` may remain `warn` only when:
  - `critical_rollout.buckets_without_servable_atoms = []`
  - `critical_rollout.buckets_without_active_atoms = []`
  - `bounded_to_noncritical_only = true`

## Test hygiene

For controlled replay, old interaction-learning state must not be allowed to contaminate the result.

Default rule:

- use a fresh `account_id`
- use a fresh `thread_id`
- use a fresh `user_id`
- do not reuse prior canary `session_id`

This is safer than destructive deletion and preserves historical auditability.

## Success criteria

The Feishu ingress canary may be judged successful when all of the following hold:

1. runtime gate holds throughout the watch window
2. sample gate is met
3. quality gate is met
4. safety gate is met

## Failure criteria

Immediate canary stop / rollback review is required if any of the following occur:

1. any authority violation
2. any severe entity mismatch
3. recall or packet regresses from `pass`
4. promotion re-enters critical-rollout failure
5. graduation gate emits `rollback`
