# OpenMind Production Health Metric Contract v1

Date: 2026-04-09  
Status: canonical PR-7 observability contract for the OpenMind production-readiness rollout

## Purpose

Define the operator-facing health domains, metrics, thresholds, and first-response posture for the OpenMind production stack on top of ChatgptREST.

This contract is intentionally query-oriented. The goal is not to introduce a new dashboard product surface, but to guarantee that one command can answer the core product-health questions without reading code.

## Canonical command

```bash
cd /vol1/1000/projects/ChatgptREST

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
python3 ops/report_openmind_production_health.py \
  --output-root artifacts/monitor/openmind_production_health
```

## Health domains

| Domain | Core question | Primary source | Default acceptance posture |
| --- | --- | --- | --- |
| `packet` | Are wake-up packets compiling cleanly, and which canary cases are degraded? | `ops/run_wakeup_packet_batch_harness.py` | `success_rate >= 0.95`, adjusted degraded ratio `<= 0.20`, median usefulness `>= 4.0` |
| `recall` | Is recall drifting away from the frozen benchmark or mis-associating projects? | `ops/run_evomap_recall_production_benchmark.py` | top-3 relative gain `>= 0.20`, mis-association rate `<= 0.05` |
| `promotion` | Is promotion blocked by blank reasons or by sources/projects without active atoms? | `ops/report_evomap_promotion_inventory.py` | recent blank promotion-reason ratio `< 0.10` |
| `crystal` | Are shadow crystals churning or conflicting in a way that threatens advisory safety? | `ops/report_crystallized_learning_governance.py` | false-positive crystal rate `<= 0.05`, denied preference occurrences `= 0`, projection mode remains `shadow` |

## Metric projection

The rollup report must project these fields:

- `domains.packet.success_rate`
- `domains.packet.adjusted_degraded_ratio`
- `domains.packet.median_auto_usefulness_score`
- `domains.packet.layer_coverage`
- `domains.packet.degraded_cases`
- `domains.recall.aggregate`
- `domains.recall.delta`
- `domains.recall.attention_cases`
- `domains.promotion.likely_blockers`
- `domains.crystal.active_crystal_count`
- `domains.crystal.superseded_candidate_count`
- `domains.crystal.denied_preference_occurrences`
- `domains.crystal.false_positive_rate`
- `operator_questions`

## Status semantics

| Status | Meaning |
| --- | --- |
| `pass` | threshold checks passed and no extra operator warning was required |
| `warn` | thresholds passed but the operator should still inspect attention items |
| `fail` | threshold breach or governance breach |

## First-response posture

The rollup report must give a first-response path per domain:

- `packet`: inspect packet sub-artifacts and the degraded cases before touching runtime flags
- `recall`: inspect benchmark attention cases before altering ranking or baseline assumptions
- `promotion`: inspect blocker reports before bulk promotion or archive changes
- `crystal`: inspect governance samples before widening reuse or changing support semantics

## Evidence

PR-7 evidence should archive:

- the rollup summary JSON
- the rollup Markdown report
- the component artifacts referenced by the rollup
- a runbook drill note showing the first-response path was actually executable on the current stack
