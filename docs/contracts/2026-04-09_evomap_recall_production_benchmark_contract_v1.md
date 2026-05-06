# 2026-04-09 EvoMap Recall Production Benchmark Contract v1

## Purpose

This contract defines the production-readiness benchmark for project recall, entity recall, and promotion-throughput visibility.

It exists to stop PR-3 from collapsing into vague statements like "recall seems better now".

## Canonical benchmark assets

Case set:

- `ops/data/evomap_recall_benchmark_v1.json`

Baseline summary:

- `artifacts/monitor/evomap_semantic_recall_harness/20260408T231936Z/summary.json`

Current runner:

```bash
cd /vol1/1000/projects/ChatgptREST

./.venv/bin/python ops/run_evomap_recall_production_benchmark.py \
  --output-root artifacts/monitor/evomap_recall_production_benchmark
```

Promotion-throughput visibility runner:

```bash
cd /vol1/1000/projects/ChatgptREST

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
./.venv/bin/python ops/report_evomap_promotion_inventory.py \
  --output-dir artifacts/monitor/evomap_promotion_inventory/$STAMP \
  --stamp $STAMP \
  --recent-window-days 7
```

## Benchmark dimensions

Per recall case:

- `top3_hit_rate`
- `top1_keyword_overlap`
- `misassociation_count`
- `confidence_posture`
- `background_reexplanation_risk`

Aggregate:

- `top3_hit_rate`
- `top1_keyword_match_rate`
- `misassociation_rate`
- `clarify_rate`
- `abstain_rate`
- `background_reexplanation_risk_rate`

## Low-confidence behavior

The canonical PR-3 low-confidence posture is:

- `answer` when top-1 has direct keyword overlap and top-3 hit rate is healthy
- `clarify` when recall is partially relevant but still weak
- `abstain` when top-1 is irrelevant and top-3 evidence remains too thin

This is a benchmark policy today.

It is not yet a blanket runtime auto-response policy for all consumers.

## Promotion-throughput visibility

PR-3 does not require clearing all historical blank promotion reasons.

It requires visibility into whether **new** staged atoms are still being written without promotion reasons.

The canonical metric is:

- `recent_blank_promotion_reason_ratio`

Current window:

- `7 days`

## Default acceptance thresholds

Until explicitly overridden:

- top-3 hit rate improves by at least `20%` over the frozen baseline
- misassociation rate stays at or below `5%`
- recent blank promotion reason ratio stays below `10%`

If the recent blank ratio is already below `10%`, PR-3 does not require historical backlog cleanup to reach zero.

## Archived evidence for PR-3

- `artifacts/monitor/evomap_semantic_recall_harness/20260409T052757Z/summary.json`
- `artifacts/monitor/evomap_semantic_recall_harness/20260409T052757Z/report.md`
- `artifacts/monitor/evomap_recall_production_benchmark/20260409T052811Z/summary.json`
- `artifacts/monitor/evomap_recall_production_benchmark/20260409T052811Z/report.md`
- `artifacts/monitor/evomap_promotion_inventory/20260409T052757Z/promotion_inventory_20260409T052757Z.json`
- `artifacts/monitor/evomap_promotion_inventory/20260409T052757Z/promotion_blockers_20260409T052757Z.md`
