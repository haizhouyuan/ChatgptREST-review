# 2026-04-09 Recall Promotion Production Benchmark Walkthrough v1

Date: 2026-04-09

## Why this package exists

The earlier semantic-recall phase already proved that recall was materially better than zero.

That still was not a production-readiness closeout.

PR-3 needed three stricter things:

- a frozen baseline comparison
- a low-confidence behavior definition
- recent-window visibility for blank promotion reasons

## Landed changes

### 1. Planning-explicit ranking fix

Updated:

- `chatgptrest/evomap/knowledge/retrieval.py`

Before this batch, planning-explicit retrieval always returned:

- diversified active hits first
- fallback hits only after that

That meant a weak generic active hit could stay above a much more relevant candidate fallback.

Now:

- planning-explicit still caps fallback volume
- but active and fallback are merged and ranked by `final_score`

This is what fixed the worst top-1 misranking for `钛虎` and `两轮车车轮市场竞争分析`.

### 2. Frozen recall benchmark

Added:

- `ops/data/evomap_recall_benchmark_v1.json`
- `ops/run_evomap_recall_production_benchmark.py`
- `docs/contracts/2026-04-09_evomap_recall_production_benchmark_contract_v1.md`

The benchmark compares current retrieval against the frozen baseline artifact:

- `artifacts/monitor/evomap_semantic_recall_harness/20260408T231936Z/summary.json`

### 3. Low-confidence posture

The benchmark now classifies each case as:

- `answer`
- `clarify`
- `abstain`

This is the current canonical PR-3 policy for recall evaluation.

### 4. Recent-window promotion visibility

Updated:

- `ops/report_evomap_promotion_inventory.py`

The inventory now reports:

- `recent_staged_atoms`
- `recent_blank_promotion_reason_staged_atoms`
- `recent_blank_promotion_reason_ratio`
- top recent sources

This lets PR-3 judge whether new staged atoms are still arriving without reasons, instead of getting trapped by historical backlog alone.

## Verification

Syntax:

```bash
python3 -m py_compile \
  chatgptrest/evomap/knowledge/retrieval.py \
  ops/report_evomap_promotion_inventory.py \
  ops/run_evomap_recall_production_benchmark.py \
  tests/test_evomap_runtime_contract.py \
  tests/test_report_evomap_promotion_inventory.py \
  tests/test_run_evomap_recall_production_benchmark.py
```

Focused suite:

```bash
./.venv/bin/pytest -q \
  tests/test_evomap_runtime_contract.py \
  tests/test_report_evomap_promotion_inventory.py \
  tests/test_run_evomap_semantic_recall_harness.py \
  tests/test_run_evomap_recall_production_benchmark.py
```

Observed result:

- focused suite passed

## Real evidence

Updated semantic recall harness:

- `artifacts/monitor/evomap_semantic_recall_harness/20260409T052757Z/summary.json`
- `artifacts/monitor/evomap_semantic_recall_harness/20260409T052757Z/report.md`

Observed query-level outcome:

- `绿源来访准备`: top-3 all relevant
- `钛虎机器人关节模组合作`: relevant candidate fallback now outranks the weak generic active hit
- `两轮车车轮市场竞争分析`: relevant candidate fallback now outranks the weak generic active hit

Production benchmark:

- `artifacts/monitor/evomap_recall_production_benchmark/20260409T052811Z/summary.json`
- `artifacts/monitor/evomap_recall_production_benchmark/20260409T052811Z/report.md`

Observed aggregate delta:

- baseline `top3_hit_rate`: `0.555556`
- current `top3_hit_rate`: `1.0`
- relative gain: `0.8`
- baseline `top1_keyword_match_rate`: `0.0`
- current `top1_keyword_match_rate`: `1.0`
- baseline `background_reexplanation_risk_rate`: `1.0`
- current `background_reexplanation_risk_rate`: `0.0`
- current `misassociation_rate`: `0.0`

Promotion inventory:

- `artifacts/monitor/evomap_promotion_inventory/20260409T052757Z/promotion_inventory_20260409T052757Z.json`
- `artifacts/monitor/evomap_promotion_inventory/20260409T052757Z/promotion_blockers_20260409T052757Z.md`

Observed current throughput signal:

- historical `blank_promotion_reason_staged_atoms`: `89314`
- `recent_staged_atoms`: `1448`
- `recent_blank_promotion_reason_staged_atoms`: `0`
- `recent_blank_promotion_reason_ratio`: `0.0`

This means:

- the historical backlog is still large
- but new staged atoms in the last 7 days are not currently being written without reasons

## Why PR-3 closes

The production roadmap required:

- repeatable recall-quality gain
- measured project mis-association
- promotion-throughput evidence

This package now has all three.

## Residual risk

- `两轮车车轮市场竞争分析` still relies on broader strategic docs, not only ultra-specific market-competition atoms
- the benchmark case set is still small and intentionally focused
- low-confidence posture is defined at benchmark level today; broader runtime auto-consumption would be a later choice, not part of this PR-3 closeout
