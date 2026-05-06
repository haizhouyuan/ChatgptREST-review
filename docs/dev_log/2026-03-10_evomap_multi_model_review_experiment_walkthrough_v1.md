# 2026-03-10 EvoMap Multi-Model Review Experiment Walkthrough v1

## What This Round Did

This round turned the `archive / review / service` execution plan into a real
experiment on the canonical EvoMap DB.

Delivered:

- canonical inventory snapshot
- review-pack generation
- manual gold benchmark
- three-lane model runs:
  - `codex_spark`
  - `gemini_cli`
  - `claude_minimax`
- normalized comparison artifacts
- final decision report

## Implemented Tooling

New experiment helpers landed earlier in the same task line:

- `chatgptrest/evomap/knowledge/review_experiment.py`
- `ops/evomap_inventory_report.py`
- `ops/evomap_build_review_packs.py`
- `ops/evomap_compare_review_runs.py`
- `tests/test_evomap_review_experiment.py`

This round then used those helpers to generate:

- `artifacts/monitor/evomap/inventory/*20260310_round1*`
- `artifacts/monitor/evomap/review_packs/20260310_round1/*`
- `artifacts/monitor/evomap/review_runs/20260310_round1/*`

## Execution Notes

### Gold benchmark

Used a smaller round-1 benchmark than the original `180 + 40 + 40` plan:

- `41` atom items
- `8` family items

Reason:

- enough to invalidate the “single model can auto-promote” assumption
- faster to hand-audit without fabricating weak labels

### Expanded packs

Executed:

- `72` service-readiness atoms
- `21` noise atoms
- `18` version families

### Lane-specific behavior

#### `codex_spark`

- cleanest JSON
- fastest runtime
- conservative on `planning`
- but over-promoted family wrappers and missed obvious noise
- also dropped one item in two packs

#### `gemini_cli`

- best gold decision accuracy
- strongest noise-pack reject rate
- but output schema drifted (`items` / `reviews` / `review_results`)
- every run carried MCP wrapper/error noise
- very promotion-biased on `planning` and `chatgptrest`

#### `claude_minimax`

- best lesson alignment
- family output broke when quoted titles invalidated outer JSON
- full service pack did not return usable output in one shot
- service pack had to be split into `part1 + part2`
- still over-promoted many items and remained the slowest lane

## Extra Normalization Work

Because the three lanes did not honor the shared contract uniformly, this round
also produced normalized comparison outputs under:

- `artifacts/monitor/evomap/review_runs/20260310_round1/summary/`

Important normalization decisions:

- preserved raw outputs as evidence
- treated wrapper text / `<think>` leakage / key drift as quality signals
- did not silently “upgrade” broken family JSON into a trusted result
- treated Claude full-pack service failure as an operational finding, not as a
  missing file to ignore

## Why The Final Decision Is Conservative

The report does not pick a fully automatic winner because the experiment did
not justify one.

The strongest facts were:

- all three lanes had poor `service_candidate` precision
- all three lanes were unreliable on wrapper/process noise
- model agreement was low across the expanded packs
- operational format stability differed too much between lanes

That is why the decision is:

- archive ingestion can widen
- review-plane implementation is mandatory
- service exposure must stay narrow and family-scoped
- model lanes remain reviewer evidence, not promotion authority

## Outputs

Primary report:

- `docs/dev_log/2026-03-10_evomap_multi_model_review_experiment_report_v1.md`

Key machine-readable summaries:

- `artifacts/monitor/evomap/review_runs/20260310_round1/summary/gold_summary.json`
- `artifacts/monitor/evomap/review_runs/20260310_round1/summary/lane_pack_summary.json`
- `artifacts/monitor/evomap/review_runs/20260310_round1/summary/agreement_matrix.csv`
- `artifacts/monitor/evomap/review_runs/20260310_round1/summary/source_decisions.json`

## Closeout Note

This walkthrough records the experiment as a completed evaluation round, not a
production rollout.

The next task should be implementation work:

1. review-plane schema
2. bootstrap `active` seed
3. retrieval mode cutover
4. family-scoped import policy enforcement
