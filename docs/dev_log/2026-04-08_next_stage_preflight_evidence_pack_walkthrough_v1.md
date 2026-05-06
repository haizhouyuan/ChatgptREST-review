# 2026-04-08 Next-Stage Preflight Evidence Pack Walkthrough V1

## What I added

I added a rerunnable preflight runner and a versioned retrieval corpus:

- [run_next_stage_preflight_evidence_pack.py](/vol1/1000/projects/ChatgptREST/ops/run_next_stage_preflight_evidence_pack.py)
- [next_stage_project_retrieval_corpus_v1.json](/vol1/1000/projects/ChatgptREST/ops/next_stage_project_retrieval_corpus_v1.json)

I then executed the runner against the live EvoMap DB and planning authority anchors, which produced:

- [preflight summary json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/next_stage_preflight/20260407T172824Z/preflight_summary.json)
- [preflight summary md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/next_stage_preflight/20260407T172824Z/preflight_summary.md)

## Why this batch matters

The next-stage v2 plan explicitly requires a preflight evidence package before boundary-consolidation work. This batch turns that requirement into a concrete, rerunnable artifact set.

Without it, the next work packages would still be relying on vague assumptions about:

- how clean `scope_project` really is
- whether promotion is failing due to content gates or missing scheduling
- whether authority anchors are structurally complete
- whether project-scoped retrieval already has observable value
- whether the planning runtime pack is healthy enough to treat as a supported asset

## What the runner checks

The runner currently produces six sections:

1. `scope_project` data audit
2. promotion diagnosis
3. authority-anchor / authority-doc integrity scan
4. project-scoped retrieval baseline
5. auxiliary read-only documents audit
6. auxiliary read-only planning runtime pack audit

## Important live findings

### 1. `scope_project` is populated but not clean enough for blind write-back

Live findings:

- `104089` atoms total
- `103896` nonblank `scope_project`
- `229` orphan atoms
- only `2` mismatch families, but both are large:
  - `planning -> research`
  - `multi -> ChatgptREST`

This is why the summary marks migration safety as `conditional`.

### 2. Promotion is mostly blocked by missing runtime scheduling

The runner confirmed:

- `promotion_audit` has not advanced recently
- active coverage is still around `0.19%`
- the planning review maintenance timer is not installed in the current live user systemd state

This is a stronger and more actionable diagnosis than “promotion is weak”.

### 3. Authority anchors are structurally healthy

Both known project anchors resolve and their pinned authority docs are present and non-empty.

That means authority governance can move forward on top of a valid baseline instead of first fixing missing files.

### 4. Project-scoped retrieval already shows real separation value

The v1 corpus intentionally focuses on stable live query families where unscoped retrieval still contaminates results.

That means later gate packs can validate project-scoped retrieval with a reusable baseline instead of ad hoc prompt examples.

### 5. Planning runtime pack is structurally fine but stale

The pack still resolves and remains explicitly consumable, but its freshness is stale. This reinforces the next-stage decision to treat freshness and maintenance as real gate concerns.

## One real issue the runner exposed

The first execution failed because `promotion_audit.groundedness_result` contains malformed historical JSON rows, and SQLite `json_extract()` crashed on them.

I fixed the runner to treat malformed JSON as a first-class audit outcome instead of crashing. That is the right behavior for release-facing diagnostics.

## Resulting decision

Work Package 0 is now materially complete:

- the evidence pack exists
- it is rerunnable
- it produced live findings that directly shape the next implementation packages

The next step is to move into the coding-agent-v1 contract work on top of this evidence baseline.

