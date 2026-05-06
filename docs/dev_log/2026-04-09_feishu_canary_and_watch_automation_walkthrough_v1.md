# 2026-04-09 Feishu Canary And Watch Automation Walkthrough v1

## Intent

Move the next rollout step from informal manual testing to a controlled Feishu canary with:

- explicit hard gates
- daily automated watch
- fresh-identity replay for seeded cases

## What was added

### 1. Daily watch runner

- `ops/run_openmind_daily_watch.py`

This script runs:

1. production regression
2. production health
3. canary scorecard
4. watch-window ledger
5. graduation gate

and writes one bundle summary.

### 2. Daily watch systemd units

- `ops/systemd/chatgptrest-openmind-daily-watch.service`
- `ops/systemd/chatgptrest-openmind-daily-watch.timer`

### 3. Feishu ingress canary replay

- `ops/run_feishu_ingress_canary.py`
- `ops/data/feishu_ingress_canary_cases_v1.json`

The runner uses fresh:

- `account_id`
- `thread_id`
- `user_id`

to avoid prior interaction-learning contamination without destructive history deletion.

### 4. Canonical next-step contracts

- `docs/contracts/2026-04-09_feishu_ingress_canary_contract_v1.md`
- `docs/reviews/2026-04-09_entity_grade_recall_hardening_plan_v1.md`
- `docs/reviews/2026-04-09_canary_driven_kb_governance_plan_v1.md`

## Live execution

### Daily watch

- live run completed:
  - `artifacts/monitor/openmind_daily_watch/20260409T141022Z/summary.json`
- generated decisions:
  - `scorecard = launch_canary_watch`
  - `gate = hold`
- host automation enabled:
  - `chatgptrest-openmind-daily-watch.timer`
  - next trigger observed at install time: `2026-04-10 09:36:29 CST`

### Feishu seeded canary

- live run bundle:
  - `artifacts/monitor/feishu_ingress_canary/20260409T141405Z/summary.json`
- seeded prompts were run with fresh identity:
  - `绿源来访准备`
  - `钛虎机器人关节模组合作`
  - `两轮车车轮市场竞争分析`
- actual posture at the end of the run:
  - `green_visit_prep`: `running`
  - `tiger_module_coop`: `completed`
  - `wheel_competition`: `running`

## Corrections made during execution

### Daily watch aggregation

- fixed `ops/run_openmind_daily_watch.py` to accept real scorecard/gate runner payloads where `decision` is returned as a plain string rather than a nested object
- extended the focused test to prevent the same regression from slipping through again

### Feishu canary live auth

- added local auth token loading from `~/.config/chatgptrest/chatgptrest.env`
- added allowlisted client headers:
  - `X-Client-Name: openclaw-advisor`
  - `X-Client-Instance: feishu-canary`
- this corrected the live failure path from `401 unauthorized` to an allowed client posture

### Feishu canary fail-closed summary

- updated `ops/run_feishu_ingress_canary.py` so nonterminal cases no longer report overall `ok=true`
- the runner now records:
  - `terminal_case_count`
  - `nonterminal_cases`
- this avoids reporting a green canary when seeded cases are still waiting on provider completion
