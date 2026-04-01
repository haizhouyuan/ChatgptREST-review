# 2026-03-11 EvoMap DB Lock Hardening

## Why

The first live `run_evomap_activation_pack.py --apply` against
[`data/evomap_knowledge.db`](/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db)
failed with `sqlite3.OperationalError: database is locked` while
`chatgptrest-api.service` was also writing activity atoms. The activation-pack
tool already had local retries, but the underlying `KnowledgeDB` write path did
not.

This round hardens the canonical EvoMap write path itself instead of keeping the
mitigation only in one caller.

## Scope

Touched:

- [`db.py`](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/db.py)
- [`test_evomap_db_locking.py`](/vol1/1000/projects/ChatgptREST/tests/test_evomap_db_locking.py)

Did not touch:

- schema
- retrieval / promotion rules
- runtime visibility gates

## Change

1. `KnowledgeDB.connect()` now opens sqlite with `timeout=30.0`
2. `KnowledgeDB.connect()` now sets `PRAGMA busy_timeout=30000`
3. `KnowledgeDB._insert()` now retries `database is locked` a bounded number of
   times with rollback + short backoff
4. non-lock sqlite errors still fail immediately

## Validation

Added focused tests for:

- connection busy-timeout value
- retry on transient lock
- no retry on unrelated sqlite errors

Targeted regression passed:

- `./.venv/bin/pytest -q tests/test_evomap_db_locking.py tests/test_evomap_activation_pack.py tests/test_groundedness.py tests/test_advisor_consult.py`
- `./.venv/bin/python -m py_compile chatgptrest/evomap/knowledge/db.py tests/test_evomap_db_locking.py`

Live smoke with `chatgptrest-api.service` still running also passed:

- `PYTHONPATH=. ./.venv/bin/python ops/run_evomap_activation_pack.py --atom-id at_act_46e169011ca85fb0 --apply ...`
- result: `selected=1, passed=1, applied=true`
- the same operation had previously required a maintenance window

This is an infra hardening step for the canonical EvoMap DB. It reduces the
chance that concurrent runtime writes and maintenance tasks immediately fail on
the first lock contention, but it is still not a substitute for wider
multi-writer load testing.
