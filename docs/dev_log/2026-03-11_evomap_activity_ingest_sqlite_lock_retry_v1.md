# EvoMap Activity Ingest SQLite Lock Retry v1

During the formal EvoMap launch smoke, `POST /v2/telemetry/ingest` returned
`200`, but the EventBus subscriber failed to materialize the activity episode
because `KnowledgeDB._insert_if_absent()` did not retry on SQLite write locks.

The failure surfaced as:

- `sqlite3.OperationalError: database is locked`
- path: `chatgptrest/evomap/activity_ingest.py -> put_episode_if_absent()`

## Change

Added a shared write-retry path in
`chatgptrest/evomap/knowledge/db.py` and routed both:

- `_insert()`
- `_insert_if_absent()`

through the same SQLite lock retry logic.

This keeps the data semantics unchanged:

- `INSERT OR REPLACE` still replaces
- `INSERT OR IGNORE` still preserves existing rows

but both now survive transient write-lock contention.

The fix also closes the longer-lived lock source:

- single-row writes now commit by default
- `bulk_put_atoms()` still batches and commits once at the end
- shared `KnowledgeDB` writes now run under a process-local write lock so the
  runtime cannot race one sqlite connection against itself

## Validation

```bash
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_evomap_db_locking.py

python3 -m py_compile \
  chatgptrest/evomap/knowledge/db.py \
  tests/test_evomap_db_locking.py
```

The test coverage now explicitly includes:

- retrying locked `INSERT OR IGNORE`
- preserving the `False` return when the row already exists
