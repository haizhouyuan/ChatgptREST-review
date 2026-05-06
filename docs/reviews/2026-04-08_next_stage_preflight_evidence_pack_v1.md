# Next-Stage Preflight Evidence Pack V1

Date: 2026-04-08

Primary artifact bundle:

- [preflight summary json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/next_stage_preflight/20260407T172824Z/preflight_summary.json)
- [preflight summary md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/next_stage_preflight/20260407T172824Z/preflight_summary.md)
- [retrieval corpus v1](/vol1/1000/projects/ChatgptREST/ops/next_stage_project_retrieval_corpus_v1.json)
- [preflight runner](/vol1/1000/projects/ChatgptREST/ops/run_next_stage_preflight_evidence_pack.py)

## 1. Why this exists

This is the mandatory preflight evidence package required by:

- [Refined Next-Stage Full Execution Plan V2](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v2.md)

Its purpose is to replace architectural assumptions with live evidence before the next-stage boundary-consolidation work proceeds.

## 2. Executive findings

### 2.1 scope_project is mostly populated, but not yet clean enough for blind write-back

Live DB findings:

- total atoms: `104089`
- nonblank `scope_project`: `103896`
- mismatch families between `atoms.scope_project` and `documents.project`: `2`
- orphan atoms: `229`
- documents without episodes: `11`

Important mismatch families:

1. `planning` atom scope attached to `research` documents: `8218` atoms
2. `multi` atom scope attached to `ChatgptREST` documents: `2475` atoms

Decision:

- any broad `scope_project` backfill or normalization must remain **conditional**
- future write-back logic must preserve existing nonblank atom scope and investigate mismatch families before normalization

### 2.2 promotion is currently blocked more by scheduling absence than by proven content rejection

Live DB / runtime findings:

- active atoms: `202`
- staged atoms: `103320`
- active ratio: `0.001941`
- promotion audit rows: `505`
- last promotion audit age: `27.56` days
- `chatgptrest-planning-review-maintenance.timer`: not installed / not listed in live user timers

Decision:

- the dominant failure mode is **scheduling absence**
- this stage should restore a safe maintenance loop before attempting broad promotion-throughput tuning

### 2.3 authority anchors are present and currently structurally healthy

Authority-anchor scan findings:

- anchor count: `2`
- stale or missing authority docs: `0`

Covered anchors:

- [两轮车车身业务/_project_context.md](/vol1/1000/projects/planning/两轮车车身业务/_project_context.md)
- [行星滚柱丝杠/_project_context.md](/vol1/1000/projects/planning/行星滚柱丝杠/_project_context.md)

Decision:

- authority-anchor governance can proceed on top of a structurally complete baseline
- future governance work should keep this scan machine-rerunnable and release-blocking

### 2.4 project-scoped retrieval already proves its value on selected live queries

The v1 corpus intentionally uses stable live query families where scoped vs unscoped behavior is visibly different:

1. `ChatgptREST` / `completion contract authoritative answer`
2. `infrastructure` / `issue domain projection contract`
3. `antigravity` / `数据来源`

Observed baseline:

- scoped retrieval returned project-aligned hits for all three cases
- unscoped retrieval still mixes in unrelated `multi`, `unknown`, and cross-project hits

Decision:

- the project-scoped retrieval contract is worth protecting in later release gates
- planning-specific retrieval was intentionally left out of the v1 corpus because the current live FTS behavior does not yet provide a stable, project-distinguishing planning query family

### 2.5 planning runtime pack is structurally healthy but operationally stale

Live planning runtime pack findings:

- bundle available: `true`
- ready for explicit consumption: `true`
- freshness: `stale`
- bundle age: `654+` hours
- pack files: all required files present
- pack counts:
  - `docs.tsv`: `116`
  - `atoms.tsv`: `226`
  - `retrieval_pack.atom_ids`: `226`

Decision:

- the pack remains a valid structural asset
- freshness is now the dominant operational concern
- semantic staleness still requires manual review, not just structural validation

## 3. Accepted implications for the next stage

The next-stage implementation can now proceed with these constraints fixed:

1. do **not** run blind `scope_project` normalization writes
2. treat promotion maintenance scheduling as a required release-shape fix, not an optional improvement
3. keep authority-anchor validation in the governance loop
4. preserve the v1 retrieval corpus as a reusable baseline
5. treat planning runtime pack freshness as a real operational signal in the later release gate pack

## 4. What this preflight does not authorize

This evidence pack does **not** authorize:

- bulk document cleanup
- archive migration
- throughput optimization work on promotion
- semantic rewriting of project anchors
- re-expansion of advisor-heavy defaults for coding agents

## 5. Release-readiness posture after preflight

Posture after Work Package 0:

- coding-agent boundary work: ready to proceed
- OpenClaw entry-policy work: ready to proceed
- authority governance work: ready to proceed
- promotion work: only safe-maintenance restoration is justified in this stage

