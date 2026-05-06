# 2026-03-11 EvoMap Multi-Writer Smoke

## Why

After hardening `KnowledgeDB` lock handling, the next step is to verify that the
fix still holds under a small concurrent write workload instead of only a single
activation-pack apply.

## Scope

Added:

- [`run_evomap_multiwriter_smoke.py`](/vol1/1000/projects/ChatgptREST/ops/run_evomap_multiwriter_smoke.py)
- [`test_evomap_multiwriter_smoke.py`](/vol1/1000/projects/ChatgptREST/tests/test_evomap_multiwriter_smoke.py)

## What it does

- creates or uses a dedicated sqlite DB for the smoke run
- launches multiple writer processes
- each worker writes `Document + Episode + Atom` rows through `KnowledgeDB`
- reports:
  - attempted writes
  - successful writes
  - total errors
  - `database is locked` count

The smoke DB is separate from the canonical runtime DB by default, so this
validation does not pollute `data/evomap_knowledge.db`.

## Goal

This is not a throughput benchmark. It is a repeatable contention smoke test to
answer one narrow question:

> does the current `KnowledgeDB` write path still fail fast on concurrent
> writers, or does the new busy-timeout/retry behavior absorb the contention?

## Validation

Targeted regression passed:

- `./.venv/bin/pytest -q tests/test_evomap_multiwriter_smoke.py tests/test_evomap_db_locking.py tests/test_evomap_activation_pack.py`
- `./.venv/bin/python -m py_compile chatgptrest/evomap/knowledge/db.py ops/run_evomap_multiwriter_smoke.py tests/test_evomap_multiwriter_smoke.py`

Live smoke passed on a dedicated temp DB:

- `PYTHONPATH=. ./.venv/bin/python ops/run_evomap_multiwriter_smoke.py --workers 4 --writes-per-worker 25 --report-json artifacts/evomap_smoke/20260311T085800Z_multiwriter.json`
- result:
  - `total_attempted=100`
  - `total_succeeded=100`
  - `locked_errors=0`
  - `error_count=0`
