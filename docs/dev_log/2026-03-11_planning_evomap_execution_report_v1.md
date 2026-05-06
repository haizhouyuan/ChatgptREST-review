# 2026-03-11 Planning EvoMap Execution Report v1

## Scope

This run completed the `planning -> EvoMap` workstream up to the intended boundary:

- `planning` remains an `archive/review-plane` source, not a live runtime retrieval cutover.
- lineage/review-plane data is now materialized inside canonical EvoMap.
- a reviewed bootstrap service set is now active inside canonical EvoMap.

This run did **not** change default runtime retrieval behavior for all `planning` content.

## What Ran

### 1. Review-plane snapshot

Snapshot root:

- `/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane/20260311T022504Z`

Snapshot summary:

- planning docs scanned: `3350`
- document roles:
  - `archive_only`: `1694`
  - `review_plane`: `1483`
  - `service_candidate`: `156`
  - `controlled`: `17`
- curated families: `28`
- review packs: `8`
- model runs: `350`
- latest outputs: `264`
- initial service candidate pool: `156`
- reviewer pack selection: `120`

### 2. Multi-runner service review

Reviewer outputs merged into final decision set:

- heuristic baseline
- `Gemini CLI` split packs: `business_104 p1/p2/p3` + `rest_all`
- `Claude` split packs: `business_104 p1/p2/p3`
- `Codex ambient` `rest_all`

Final merged review decision summary:

- reviewed docs: `120`
- allowlist docs: `97`
- final buckets:
  - `service_candidate`: `86`
  - `review_only`: `17`
  - `procedure`: `10`
  - `archive_only`: `5`
  - `reject_noise`: `1`
  - `correction`: `1`

Files:

- [planning_review_decisions_v2.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane/20260311T022504Z/planning_review_decisions_v2.tsv)
- [planning_review_decisions_v2.summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane/20260311T022504Z/planning_review_decisions_v2.summary.json)

### 3. Canonical EvoMap import

Imported into canonical DB:

- canonical DB: [evomap_knowledge.db](/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db)
- review-plane documents imported: `506`
  - family docs: `28`
  - review pack docs: `8`
  - model run docs: `350`
  - review decision docs: `120`
- original planning docs updated with `planning_review` metadata: `3350`

Import summary:

- [import_summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane/20260311T022504Z/import_summary.json)

### 4. Bootstrap active set

Final bootstrap run used the merged `v2` review decisions.

Bootstrap summary:

- allowlist docs: `97`
- reconciled out atoms: `3`
- candidate atoms: `189`
- promoted atoms: `168`
- deferred atoms: `21`

Files:

- [bootstrap_active_summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane/20260311T022504Z/bootstrap_active_v3/bootstrap_active_summary.json)
- [bootstrap_active_promoted.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane/20260311T022504Z/bootstrap_active_v3/bootstrap_active_promoted.tsv)
- [bootstrap_active_deferred.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane/20260311T022504Z/bootstrap_active_v3/bootstrap_active_deferred.tsv)
- [bootstrap_active_reconciled_out.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane/20260311T022504Z/bootstrap_active_v3/bootstrap_active_reconciled_out.tsv)

Canonical DB state after bootstrap:

- planning active atoms: `168`
- planning candidate atoms: `21`
- planning staged atoms: `40712`
- planning active docs: `86`
- planning candidate docs: `11`

Active/candidate interpretation:

- active docs align to final `service_candidate` docs: `86`
- candidate docs are retained for `procedure/correction` outputs: `11`
- `3` previously promoted atoms were reconciled out after the fuller reviewer set changed the decision boundary

## Quality Assessment

The quality level is now materially better than the pre-run state:

- before this run, `planning` was effectively `all staged / 0 active`
- after this run, `86` reviewed `planning` docs now have active service atoms
- all `3350` planning documents now carry explicit review-plane metadata in `meta_json`
- review-plane objects are preserved as archived knowledge, not mixed into generic service retrieval as normal planning prose

This is still **bootstrap quality**, not final steady-state quality:

- the active set is review-driven and scoped
- the remaining `40712` staged atoms are still not service-ready by default
- retrieval cutover for `planning` has not been performed in this run

## Important Implementation Decision

`planning` bootstrap activation now uses a split gate:

- if an atom answer contains runtime grounding anchors like paths, relative code paths, or systemd units, it still runs the normal groundedness gate
- if an atom answer is a business/planning deliverable with no runtime anchors, it takes a `review_verified_fast_path`

Why this was necessary:

- the original bootstrap path called groundedness checks on every candidate atom
- for planning content this was too expensive and unnecessary
- the result was a long-running bootstrap process that completed import but stalled on promotion

The new contract is intentionally scoped to `planning review-plane bootstrap`, not a global change to generic EvoMap promotion logic.

## Remaining Gaps

Not done in this run:

- no runtime retrieval cutover for all planning content
- no active-only retrieval policy for planning
- no incremental watcher that auto-updates review-plane on new planning commits
- no full supersede/conflict reconciliation across all historical planning versions

Next correct steps:

1. Add incremental `planning` lineage/review-plane refresh.
2. Decide whether `planning` retrieval should become `active_then_review_fallback`.
3. Extend bootstrap review beyond the current `120`-doc selection if the active set needs broader coverage.

