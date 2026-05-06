# EvoMap Scratch Refine and P1 Run

Date: 2026-03-07
Owner: Codex takeover after Antigravity became unavailable

## Scope

This run targeted the scratch EvoMap DB at:

- `~/.openmind/evomap_knowledge.db`

This is **not** the same DB as the live ChatgptREST runtime DB:

- `data/evomap_knowledge.db`

The scratch DB currently holds Antigravity conversation artifacts only.
The live DB holds the broader ChatgptREST knowledge corpus and was not migrated here.

## Actual State Before Takeover

The Antigravity brain walkthrough was stale at `1045/2248 (47%)`.
The real DB state at takeover time was:

- atoms: `2700`
- `status='scored'`: `2435`
- non-empty `canonical_question`: `2419`
- `valid_from > 0`: `0`
- remaining refineable (`canonical_question=''` and `answer >= 100 chars`): `31`
- short unrefined (`canonical_question=''` and `answer < 100 chars`): `250`

## Completion of Remaining Refineable Atoms

Command:

```bash
python3 ops/run_atom_refinement.py \
  --db /home/yuanhaizhou/.openmind/evomap_knowledge.db \
  --limit 100 \
  --batch-size 10 \
  --min-answer-chars 100 \
  --model gpt-5.4 \
  --reasoning-effort high
```

Observed result:

- found: `31` atoms to refine
- refined: `31`
- errors: `0`
- elapsed: `215.0s`
- bridge calls: `4`

Scratch DB state after refine catch-up:

- atoms: `2700`
- `status='scored'`: `2450`
- non-empty `canonical_question`: `2450`
- short unrefined below threshold: `250`

## P1 Migration Run

P1 was executed on the scratch DB only.

Automatic backup created by CLI:

- `~/.openmind/evomap_knowledge.db.bak.20260307_184854`

Command:

```bash
python3 ops/run_atom_refinement.py \
  --db /home/yuanhaizhou/.openmind/evomap_knowledge.db \
  --p1-migrate \
  --p1-only \
  --report-json docs/dev_log/artifacts/evomap_p1_scratch_20260307/p1_report.json
```

Result:

- elapsed: `947.4ms`
- `valid_from` backfilled from `episode.time_end`: `2700/2700`
- missing `valid_from`: `0`
- atoms with canonical question: `2450`
- atoms without canonical question: `250`
- total chains: `2376`
- singleton chains: `2334`
- multi-atom chains: `42`
- `promotion_status='candidate'`: `2376`
- `promotion_status='superseded'`: `74`
- `promotion_status='staged'`: `250`

Artifacts:

- `docs/dev_log/artifacts/evomap_p1_scratch_20260307/p1_report.json`

## Code Changes Landed During Takeover

To make P1 operable instead of doc-only, the following were added/fixed:

- `ops/run_atom_refinement.py`
  - add `--p1-migrate`
  - add `--p1-only`
  - automatic DB backup before P1
  - JSON report output
  - fix misleading negative "Remaining" stats
- `chatgptrest/evomap/knowledge/db.py`
  - always ensure `idx_atoms_promotion` / `idx_atoms_chain`
- `tests/test_evomap_chain.py`
  - verify indices exist after idempotent init/migration

## Important Boundary

This run does **not** make scratch knowledge active retrieval truth.
Current meaning of the scratch DB after P1 is:

- structurally refined
- time-backed
- chain-grouped
- supersession-marked
- still awaiting P2 groundedness and any later promotion policy

## What Was Intentionally Not Done

- no P1 migration on `data/evomap_knowledge.db`
- no automatic promotion to `active`
- no attempt to merge scratch and live DBs
- no groundedness verification against GitNexus yet

## Next Steps

1. Implement P2 groundedness verification for scratch Antigravity atoms.
2. Decide promotion rules after P2, not before.
3. Keep live ChatgptREST DB separate until there is an explicit merge/governance plan.
