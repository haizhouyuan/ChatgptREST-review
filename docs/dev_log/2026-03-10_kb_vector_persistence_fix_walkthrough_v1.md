# KB Vector Persistence Fix Walkthrough — 2026-03-10 v1

## Context

`docs/dev_log/2026-03-10_kb_architecture_deep_audit_v2.md` corrected the original audit and identified the concrete vector failure mode:

- `KBHub.index_document()` added vectors into `NumpyVectorStore` memory
- the runtime path never called `KBHub.save()`
- `NumpyVectorStore.save()` only ran on explicit save or clean close
- production therefore kept `kb_vectors.db` at `0` rows despite working embeddings

The same audit also confirmed that `ArtifactRegistry` governance code existed but `register_file()` never computed `quality_score`, which left runtime-created artifacts at `0.0`.

## Changes

### 1. Persist vectors during indexing

File: `chatgptrest/kb/hub.py`

- `index_document()` now removes existing vectors for the same `artifact_id` before re-indexing
- after adding fresh vectors, it immediately calls `self._vec.save()`

Why:

- this aligns vector lifecycle with FTS replacement semantics
- it prevents vector rows from depending on process shutdown for persistence
- it prevents duplicate vector chunks when the same document is re-indexed

### 2. Compute registry quality on `register_file()`

File: `chatgptrest/kb/registry.py`

- `register_file()` now computes `art.quality_score` before upsert/notify

Why:

- runtime writeback already goes through `register_file()`
- the registration callback passes `art.quality_score` into `KBHub.index_document()`
- this makes runtime-ingested KB documents carry a non-zero quality score without changing broader `register_artifact()` semantics

## Tests Added

Files:

- `tests/test_kb_hub.py`
- `tests/test_kb.py`

Coverage added:

- vectors are flushed to SQLite before `close()`
- re-indexing the same doc replaces old vectors instead of duplicating them
- `register_file()` stores a computed non-zero quality score

## Verification

Executed:

```bash
./.venv/bin/pytest -q tests/test_kb_hub.py tests/test_kb.py
./.venv/bin/pytest -q tests/test_funnel_kb_writeback.py tests/test_advisor_runtime.py
```

Result:

- all targeted tests passed

## Deliberately Not Done

- no semantic-memory promotion runner was added
- no EvoMap graph orchestration was added
- no backfill job was added for existing 903 FTS docs / 0 vectors

Those remain orchestration-layer work, not a hot-path persistence defect.
