# 2026-03-11 Planning Runtime Pack Explicit Runtime Hook v1

## Goal

Expose the planning reviewed runtime pack as a real runtime feature without
changing default retrieval behavior.

## What Changed

Added:

- `chatgptrest/evomap/knowledge/planning_runtime_pack_search.py`

Updated:

- `chatgptrest/api/routes_consult.py`

## Runtime Contract

Default behavior is unchanged.

The planning slice is only used when the caller explicitly asks for it through:

- `source_scope=["planning_review"]`
- or `planning_mode=true`

This explicit hook is available on:

- `POST /v1/advisor/recall`
- `POST /v1/advisor/consult`

## Retrieval Strategy

The hook does not reuse generic EvoMap FTS as the only ranking path.

Instead it uses a three-step path:

1. load the latest approved planning runtime-pack release bundle
2. rank candidate atoms using the pack TSV metadata
3. fetch the real answer bodies from canonical EvoMap by `atom_id`

This keeps the launch path narrow and deterministic:

- only approved bundles are eligible
- only pack-declared `atom_ids` are eligible
- runtime visibility gate still applies in canonical DB

## Safety

The hook still enforces runtime safety gates:

- bundle must have `ready_for_explicit_consumption = true`
- `candidate` atoms do not leak into runtime results
- low-groundedness atoms do not leak into runtime results
- default recall/consult paths are unchanged when opt-in is absent

## Response Surface

Recall now adds:

- `sources.planning_review_pack`
- `source_scope`

Consult now adds:

- `planning_context_injected`
- `planning_hits_count`
- `source_scope`

## Validation

Focused checks:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_planning_runtime_pack_search.py \
  tests/test_advisor_consult.py

python3 -m py_compile \
  chatgptrest/evomap/knowledge/planning_runtime_pack_search.py \
  chatgptrest/api/routes_consult.py \
  tests/test_planning_runtime_pack_search.py \
  tests/test_advisor_consult.py
```
