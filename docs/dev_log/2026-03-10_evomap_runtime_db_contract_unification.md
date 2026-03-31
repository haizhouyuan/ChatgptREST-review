# 2026-03-10 EvoMap Runtime DB Contract Unification

## Why

EvoMap runtime and ops scripts had diverged onto two different knowledge DBs:

- runtime/read path: `data/evomap_knowledge.db`
- legacy scratch/ops defaults: `~/.openmind/evomap_knowledge.db`

That made retrieval, refinement, and promotion work land in different stores.

## Decision

`data/evomap_knowledge.db` is the only runtime/default EvoMap knowledge DB.

`~/.openmind/evomap_knowledge.db` exits the runtime plane and is now treated as an
archive/sample DB. It is no longer used by helper fallback or script defaults.

## Changes

1. `resolve_evomap_knowledge_read_db_path()` no longer falls back to
   `~/.openmind/evomap_knowledge.db`.
2. `resolve_evomap_knowledge_runtime_db_path()` ignores the legacy home-path if it
   is injected through `EVOMAP_KNOWLEDGE_DB`; runtime falls back to the canonical
   repo DB instead.
3. `ops/run_atom_refinement.py` now defaults to the canonical runtime DB.
4. `chatgptrest.evomap.knowledge.p4_batch_fix` now defaults to the canonical
   runtime DB.

Manual archive work is still possible by passing `--db /path/to/archive.db`
explicitly to ops scripts. The removal is from runtime/default resolution, not from
manual one-off inspection.

## Validation

- `./.venv/bin/pytest -q tests/test_openmind_store_paths.py tests/test_routes_advisor_v3_security.py tests/test_routes_evomap.py`
- `./.venv/bin/python -m py_compile chatgptrest/core/openmind_paths.py ops/run_atom_refinement.py chatgptrest/evomap/knowledge/p4_batch_fix.py tests/test_openmind_store_paths.py`
- direct helper check:
  - `resolve_evomap_knowledge_runtime_db_path()` -> `/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db`
  - `resolve_evomap_knowledge_read_db_path()` -> `/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db`

## Result

The runtime path contract is now single-line:

- canonical runtime/read DB: `data/evomap_knowledge.db`
- legacy home DB: archive only, never defaulted
