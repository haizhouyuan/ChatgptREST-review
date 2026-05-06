## Context

While running the first live EvoMap smoke checks against the 18711 runtime, two high-signal facts emerged:

1. `POST /v2/telemetry/ingest` returned `200 OK` with `recorded=1`, but no new
   `activity: team.run.completed` atom appeared in `data/evomap_knowledge.db`.
2. `GET /v1/issues/canonical/export` returned `500 Internal Server Error` in the
   live API process.

The second issue was a true code bug, not an environment artifact.

## Root Cause

`chatgptrest/core/issue_family_registry.py:match_issue_family()` built its
haystack with:

- scalar fields
- `tags`
- `metadata`

The metadata portion used `" ".join([...])` over list pairs `[str(k), str(v)]`.
That raises:

- `TypeError: sequence item 0: expected str instance, list found`

as soon as an issue has non-empty metadata.

This affected both:

- canonical issue export
- any canonical projection path that calls `_issue_record()`

## Fix

- Added `_text_fragments()` to flatten nested dict/list/set metadata and tags into
  a safe text stream before normalization.
- Updated `match_issue_family()` to build its haystack from `_text_fragments(...)`
  instead of joining nested lists directly.
- Added a route-level regression test covering list-valued metadata through the
  real `/v1/issues/canonical/export` API.

## Validation

Targeted validation passed:

```bash
./.venv/bin/pytest -q tests/test_issue_canonical_api.py -k 'roundtrip or list_metadata'
./.venv/bin/python -m py_compile \
  chatgptrest/core/issue_family_registry.py \
  tests/test_issue_canonical_api.py
```

Direct in-process canonical export also succeeds after the fix:

```python
issue_canonical.export_issue_canonical_snapshot(...)
```

and returns:

- `read_plane = canonical`
- `canonical_issue_count = 245`
- `coverage_gap_count = 0`

## Remaining Follow-up

The telemetry smoke remains partially blocked:

- runtime `/v2/telemetry/ingest` accepts the event
- but the canonical EvoMap DB still does not show the corresponding
  `activity: team.run.completed` atom on the 18711 process

That should be investigated separately as a live wiring/runtime-state problem,
not folded into the issue-domain export fix.
