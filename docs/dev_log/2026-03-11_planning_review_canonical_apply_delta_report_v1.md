# 2026-03-11 Planning Review Canonical Apply Delta Report v1

## Scope

Apply the reviewed `planning_review_decisions_v3.tsv` baseline into the live canonical EvoMap DB without changing runtime retrieval policy.

Applied inputs:

- [planning_review_decisions_v3.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/planning_review_decisions_v3.tsv)
- [planning_review_decisions_v3_allowlist.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/planning_review_decisions_v3_allowlist.tsv)

Command used:

```bash
./.venv/bin/python ops/import_planning_review_plane_to_evomap.py \
  --db data/evomap_knowledge.db \
  --snapshot-dir artifacts/monitor/planning_review_plane_refresh/20260311T032642Z \
  --review-decisions artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/planning_review_decisions_v3.tsv \
  --apply-bootstrap \
  --allowlist artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/planning_review_decisions_v3_allowlist.tsv \
  --bootstrap-output-dir artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/live_apply_v1/bootstrap_active
```

## Before

- `planning reviewed docs = 120`
- `planning_review_plane docs = 506`
- planning atom status:
  - `168 active`
  - `21 candidate`
  - `40712 staged`

## Apply Result

Import summary:

- `updated_docs = 3350`
- `imported_family_docs = 28`
- `imported_review_pack_docs = 8`
- `imported_model_run_docs = 350`
- `imported_decision_docs = 156`

Bootstrap summary:

- `allowlist_docs = 116`
- `promoted_atoms = 201`
- `candidate_atoms = 226`
- `deferred_atoms = 25`
- `reconciled_out_atoms = 0`

## After

- `planning reviewed docs = 156`
- `planning_review_plane docs = 542`
- planning atom status:
  - `201 active`
  - `25 candidate`
  - `40675 staged`

## Delta

- reviewed planning docs: `+36`
- planning review-plane docs: `+36`
- active planning atoms: `+33`
- candidate planning atoms: `+4`
- staged planning atoms: `-37`

## Boundary Check

This round did **not**:

- change default runtime retrieval rules
- broaden `review_verified_fast_path` beyond planning bootstrap
- touch execution telemetry contracts from `#114` mainline

It only advanced the planning reviewed slice from temp-copy validated state into the live canonical planning family.
