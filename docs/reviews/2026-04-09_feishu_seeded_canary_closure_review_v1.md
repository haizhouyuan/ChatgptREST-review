# 2026-04-09 Feishu Seeded Canary Closure Review v1

## Verdict

The seeded Feishu canary is now closed with honest posture:

- the original three-case batch replay exposed a real isolation bug
- the runner was corrected to fail-fast on nonterminal cases
- all three prompts were then re-run in isolated fresh-identity single-case mode
- all three isolated replays reached terminal `completed`

This is a valid closure of the seeded replay wave. It is not a claim that the wider Feishu canary is fully green.

## What failed in the first live replay

The first batch replay used three fresh identities but still allowed the second later case to be submitted after the first case was still nonterminal.

Observed failure:

- `绿源来访准备` and `两轮车车轮市场竞争分析` ended up on the same provider conversation id
- `绿源来访准备` received the wrong answer family

Evidence:

- job `079d3e813aeb4b368592b98eb38b90d4`
- job `85e6c8ebae124623b87fb4728a88651b`
- both pointed at provider conversation id `69d7b442-13cc-832b-b21e-a77eeeeb0421`

Interpretation:

- this was not a semantic-recall miss
- this was a seeded replay isolation failure

## Correction applied

`ops/run_feishu_ingress_canary.py` now:

- loads local auth correctly for `/v3/agent/*`
- sends allowlisted client headers
- marks nonterminal cases fail-closed
- stops the replay immediately after the first nonterminal case

This prevents later seeded prompts from contaminating the replay run.

## Isolated replay results

### 1. `绿源来访准备`

- bundle: `artifacts/monitor/feishu_ingress_canary_single/20260409T152107Z/summary.json`
- posture: `completed`
- observed answer family: visit/prep oriented and directionally correct

### 2. `钛虎机器人关节模组合作`

- bundle: `artifacts/monitor/feishu_ingress_canary_single/20260409T152417Z/summary.json`
- posture: `completed`
- observed answer family: cooperation/module implementation plan and directionally correct

### 3. `两轮车车轮市场竞争分析`

- bundle: `artifacts/monitor/feishu_ingress_canary_single/20260409T152712Z/summary.json`
- posture: `completed`
- observed answer family: market competition analysis plan and directionally correct

## Strategic reading

The seeded replay wave now supports three conclusions:

1. Feishu/OpenClaw ingress can be replayed cleanly with fresh identity on the live substrate.
2. The product risk is no longer basic runner/auth failure; it is answer quality and entity-grade recall under real asks.
3. Batch seeded replay must remain isolation-aware. If a case is still nonterminal, the correct posture is stop-and-review, not keep sending more prompts.

## Remaining gap

This closure does not remove the next major product gap:

- entity-grade recall is still weaker than bridge-grade recall

So the next engineering priority remains:

- Feishu canary with hard gates
- automated daily watch
- entity-grade recall hardening
