# 2026-04-09 Feishu Seeded Canary Closure Walkthrough v1

## What happened

The original seeded Feishu canary batch run reached the live API, but it did not close cleanly:

- one case completed
- two cases were still `running` at timeout
- later investigation showed cross-case contamination between `绿源来访准备` and `两轮车车轮市场竞争分析`

## Root cause

The runner allowed later seeded prompts to continue even when an earlier case had not yet reached a terminal state.

This created an operator-level replay isolation problem:

- later seeded prompts could land in the same provider conversation as an earlier unfinished prompt

## What was changed

### Code

- updated `ops/run_feishu_ingress_canary.py`
  - fail-closed when cases remain nonterminal
  - stop after first nonterminal seeded case

### Tests

- updated `tests/test_run_feishu_ingress_canary.py`
  - added regression coverage for stop-after-nonterminal behavior

### Contract

- added `docs/contracts/2026-04-09_feishu_ingress_canary_contract_v2.md`
  - freezes seeded replay isolation as a hard rule

### Review

- added `docs/reviews/2026-04-09_feishu_seeded_canary_closure_review_v1.md`

## What was executed

After the runner correction, the three seeded prompts were re-run in isolated single-case mode with fresh identity and longer timeout:

- `绿源来访准备`
- `钛虎机器人关节模组合作`
- `两轮车车轮市场竞争分析`

## Result

All three isolated seeded replays reached `completed`.

This closes the seeded replay task honestly:

- batch replay found a real isolation flaw
- the flaw was corrected
- the three prompts were re-run cleanly
- clean isolated results now exist as evidence artifacts
