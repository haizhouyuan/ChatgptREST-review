# 2026-04-09 Feishu Canary And Watch Execution Summary v1

## Outcome

This wave completed the missing operational step between strategy and live use:

- the OpenMind daily watch bundle is now automated and installed on the host
- the seeded Feishu canary runner was executed on the live API using fresh identity per case
- the runner and tests were corrected against live failures instead of being left as paper automation

## Daily watch

- live bundle:
  - `artifacts/monitor/openmind_daily_watch/20260409T141022Z/summary.json`
- current rollup:
  - `scorecard = launch_canary_watch`
  - `graduation_gate = hold`
- host timer:
  - `chatgptrest-openmind-daily-watch.timer`
  - enabled under `systemd --user`

## Seeded Feishu canary

Live bundle:

- `artifacts/monitor/feishu_ingress_canary/20260409T141405Z/summary.json`

Seeded prompts:

- `绿源来访准备`
- `钛虎机器人关节模组合作`
- `两轮车车轮市场竞争分析`

Fresh-identity hygiene:

- each case used a fresh `account_id`
- each case used a fresh `thread_id`
- each case used a fresh `user_id`
- no destructive memory deletion was used

Observed result at run close:

- `green_visit_prep`: `running`
- `tiger_module_coop`: `completed`
- `wheel_competition`: `running`

This is intentionally not described as green. The seeded replay succeeded as a live submission exercise, but two of the three cases remained nonterminal at the runner timeout boundary.

## Corrections applied

### 1. Daily watch payload compatibility

The first live run failed because the scorecard and graduation runners return `decision` as a plain string, while the daily watch aggregator assumed a nested object. The runner was corrected to accept the live payload shape.

### 2. Feishu canary auth posture

The first live submission failed with `401`, then `403` after token loading was added. Root cause was not the token itself but the `/v3/agent/*` client-name allowlist. The runner now sends:

- `X-Client-Name: openclaw-advisor`
- `X-Client-Instance: feishu-canary`

### 3. Canary summary fail-closed

The first version of the canary runner could return `ok=true` even when seeded cases were still `running`. This was corrected. The runner now emits:

- `terminal_case_count`
- `nonterminal_cases`
- overall `ok=false` unless every case reaches a terminal posture

## Interpretation

The operator side is now in a stronger state than before this wave:

- daily watch no longer depends on manual Codex polling
- seeded Feishu ingress canary is reproducible
- replay hygiene is explicit
- runner output is fail-closed

The product side is not yet fully green:

- seeded canary completion latency is still uneven
- entity-grade recall remains the next product-quality bottleneck
- the current canary result should be treated as a live submission proof, not as a pass of all three seeded cases
