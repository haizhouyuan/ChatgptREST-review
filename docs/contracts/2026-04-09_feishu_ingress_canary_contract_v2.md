# Feishu Ingress Canary Contract v2

Date: 2026-04-09  
Status: canonical hard-gate contract for Feishu/OpenClaw ingress canary after seeded replay isolation correction

Supersedes:

- `docs/contracts/2026-04-09_feishu_ingress_canary_contract_v1.md`

## Purpose

Keep Feishu ingress canary as a controlled experiment with explicit stop conditions, rather than a best-effort replay that can contaminate later cases.

## Scope

Current canary scope:

- channel posture: `Feishu/OpenClaw ingress`
- runtime substrate: `ChatgptREST + OpenClaw bridge`
- project scope: `planning`
- replay hygiene: `fresh identity`

Seeded replay prompts:

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

### Safety gate

- authority violations: `0`
- severe cross-project mismatch: `0`
- severe entity mismatch: `0`
- seeded replay conversation-collision incidents: `0`

### Runtime gate

The canary must remain inside the current substrate envelope:

- `packet = pass`
- `recall = pass`
- `crystal = pass`
- `promotion` may remain `warn` only when:
  - `critical_rollout.buckets_without_servable_atoms = []`
  - `critical_rollout.buckets_without_active_atoms = []`
  - `bounded_to_noncritical_only = true`

## Replay hygiene

Controlled replay must not reuse prior interaction-learning state and must not allow one nonterminal seeded case to pollute the next case.

Required defaults:

- use a fresh `account_id`
- use a fresh `thread_id`
- use a fresh `user_id`
- do not reuse prior canary `session_id`
- send allowlisted client headers for `/v3/agent/*`

## Seeded replay isolation rule

For seeded replay, the runner must stop immediately when a case remains nonterminal at the timeout boundary.

Required behavior:

1. a nonterminal case must mark the replay bundle as non-green
2. later seeded cases must not be submitted after a nonterminal result
3. operator review must happen before further seeded cases are sent

Rationale:

- this prevents provider-conversation collision between independent seeded cases
- this preserves attribution when diagnosing route or answer mismatches

## Success criteria

Feishu ingress canary may be judged successful only when:

1. runtime gate holds throughout the watch window
2. sample gate is met
3. quality gate is met
4. safety gate is met
5. seeded replay isolation rule is satisfied

## Failure criteria

Immediate canary stop or rollback review is required if any of the following occur:

1. any authority violation
2. any severe entity mismatch
3. any seeded replay collision or cross-case answer contamination
4. recall or packet regresses from `pass`
5. promotion re-enters critical-rollout failure
6. graduation gate emits `rollback`
