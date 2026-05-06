# Scope Project Live Backfill Readiness Decision V1

Date: 2026-04-08

Primary evidence bundle:

- [preflight summary json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/next_stage_preflight/20260407T224249Z/preflight_summary.json)
- [preflight summary md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/next_stage_preflight/20260407T224249Z/preflight_summary.md)
- [scope-project backfill script](/vol1/1000/projects/ChatgptREST/scripts/backfill_evomap_scope_project.py)
- [next-stage preflight evidence pack](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_next_stage_preflight_evidence_pack_v1.md)

## 1. Decision

`scope_project` live backfill is **not approved**.

Current disposition:

- readiness = `conditional`
- execution posture = `deferred`
- allowed action now = dry-run analysis only
- blocked action now = any broad write-back against the live EvoMap DB

## 2. Why this remains deferred

### 2.1 The DB is mostly populated, but not yet semantically clean

Live counts from the latest preflight run:

- total atoms: `104123`
- nonblank `atoms.scope_project`: `103896`
- orphan atoms: `229`
- documents without episodes: `11`
- grouped mismatch families: `2`

The grouped mismatch families are not cosmetic:

1. `atom.scope_project=planning` vs `document.project=research` with `8218` atoms
2. `atom.scope_project=multi` vs `document.project=ChatgptREST` with `2475` atoms

These are large enough that any blind "document project wins" write-back would rewrite real semantics, not just fill blanks.

### 2.2 The noisy project namespace is still unresolved

The preflight evidence also shows multiple low-signal or suspect project labels, including:

- path-like values such as `/vol1/1000/projects/ChatgptREST`
- generic values such as `unknown`
- many dated low-volume project names

That means the remaining normalization problem is not "fill blank fields", but "decide what the canonical project namespace should be".

### 2.3 The current script is safe only if it is gated by audit output

[backfill_evomap_scope_project.py](/vol1/1000/projects/ChatgptREST/scripts/backfill_evomap_scope_project.py) is now a valid tool, but the latest evidence does not justify a production write.

The script can be used later, but only after the mismatch families and noisy namespace are explicitly adjudicated.

## 3. What is allowed now

Allowed now:

- rerun the preflight evidence pack
- run additional SQL-only audits
- compare mismatch families over time
- review a dry-run plan for blanks / orphan-safe rows only

Not allowed now:

- broad live backfill across all blank or nonblank rows
- normalization that rewrites existing nonblank `scope_project`
- project-name cleanup that does not first define a canonical namespace contract

## 4. Approval conditions for a future live write

Live write approval requires all of the following:

1. A reviewed mismatch-resolution note that explains the `planning↔research` and `multi↔ChatgptREST` families.
2. An explicit canonical project-namespace policy for noisy values.
3. A narrowed backfill target set that is limited to rows proven safe by the audit.
4. A dry-run artifact bundle showing exact candidate row counts before write.
5. A rollback plan for any write touching the production EvoMap DB.

Until those five conditions are met, the system should treat the live backfill as deferred.

## 5. Operational conclusion

This stage succeeded in turning `scope_project` from an architectural intention into an auditable runtime field.

It did **not** yet prove that a production rewrite is safe.

The correct next action is:

- keep `scope_project` write-back deferred
- continue using project-scoped retrieval with the current audited state
- only revisit live backfill after the mismatch families are explicitly resolved
