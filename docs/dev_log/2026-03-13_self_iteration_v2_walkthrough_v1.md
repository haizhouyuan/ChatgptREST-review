# 2026-03-13 Self-Iteration V2 Walkthrough v1

## Scope
- Completed Slice A: runtime knowledge policy surfaces.
- Deferred Slice B and parallel lanes until Slice A was frozen and verified.

## What changed
- Added explicit runtime retrieval surfaces in `chatgptrest/evomap/knowledge/retrieval.py`:
  - `user_hot_path`
  - `diagnostic_path`
  - `shadow_experiment_path`
  - `promotion_review_path`
- Added `runtime_retrieval_config()` so runtime entrypoints stop relying on the broad library default.
- Added `summarize_promotion_statuses()` for runtime/debug metadata.
- Updated public runtime entrypoints to request an explicit surface:
  - `ContextResolver` / local cognitive context path -> `user_hot_path`
  - legacy `ContextAssembler` EvoMap path -> `user_hot_path`
  - consult EvoMap helper -> `user_hot_path`
  - graph personal query -> `diagnostic_path`
- Added runtime metadata so responses can show promotion-state evidence without changing the main payload contract.

## Why
- Current public hot paths already intended to hide `STAGED`, but that policy was implicit and inconsistent.
- The retrieval library default still allowed `ACTIVE + STAGED`, which made runtime safety depend on each caller remembering to narrow the config manually.
- The goal of Slice A is to make runtime path policy explicit while preserving wider diagnostic/shadow access.

## Verification
- `python3 -m py_compile chatgptrest/evomap/knowledge/retrieval.py chatgptrest/cognitive/context_service.py chatgptrest/kernel/context_assembler.py chatgptrest/api/routes_consult.py chatgptrest/cognitive/graph_service.py tests/test_evomap_runtime_contract.py tests/test_cognitive_api.py`
- `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_evomap_runtime_contract.py tests/test_cognitive_api.py`

## Findings during verification
- Initial implementation broke all explicit runtime surfaces because `RetrievalSurface` enum values were normalized via `str(enum_member)` instead of `.value`.
- Graph query metadata initially assumed `personal_graph` was always requested; that broke `repo_graph`-only requests.
- A new black-box regression proved the intended split:
  - `/v2/context/resolve` does not surface a `STAGED`-only EvoMap hit.
  - `/v2/graph/query` on `personal_graph` can surface the same `STAGED` atom for diagnostics.

## Remaining work
- Slice B: execution identity contract.
- Parallel lanes only after Slice B freezes shared contracts.
