# 2026-03-10 Shared Resolver And Memory Identity Hardening

## Summary
- unify runtime and consult path resolution for OpenMind KB/EventBus/EvoMap stores
- ignore zero-byte HOME EvoMap fallback during consult recall
- disable startup EvoMap extractors by default unless explicitly enabled
- add graph mirror policy gate to block implicit graph growth outside governed modes
- expose memory capture / context resolve identity gaps and provenance quality for hot-path diagnostics

## Files
- `chatgptrest/core/openmind_paths.py`
- `chatgptrest/advisor/runtime.py`
- `chatgptrest/api/routes_advisor_v3.py`
- `chatgptrest/api/routes_consult.py`
- `chatgptrest/cognitive/ingest_service.py`
- `chatgptrest/cognitive/memory_capture_service.py`
- `chatgptrest/cognitive/context_service.py`
- `tests/test_openmind_store_paths.py`
- `tests/test_advisor_runtime.py`
- `tests/test_cognitive_api.py`

## Why
The v2 authority review found three live gaps:
1. runtime and consult read different stores
2. consult could read a zero-byte HOME fallback and miss the live repo-local EvoMap knowledge DB
3. memory recall/capture lacked explicit parity and degraded-identity gates for the reference slice

## Validation
- `python3 -m py_compile ...` for all touched modules
- `pytest` reference slice acceptance gates now all pass (`CP1/CP2/CP3/TP1/ID1/RESOLVER/GROWTH/ISSUE`)
- targeted tests include resolver parity, extractor default-off, graph mirror policy skip, and partial-identity exposure
- full targeted regression pack also passed across advisor runtime, cognitive API, consult resolver, issue graph, and plugin verifier slices
