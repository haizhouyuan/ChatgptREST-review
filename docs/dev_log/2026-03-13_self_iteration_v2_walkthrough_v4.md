# 2026-03-13 Self-Iteration V2 Walkthrough v4

## Scope
- Completed Lane F locally: observer-only promotion/suppression decision seed and experiment registry.
- No runtime mutation, no DB migration.

## What changed
- Added `chatgptrest/eval/decision_plane.py`:
  - `RetrievalEvidence`
  - `ImprovementDecision`
  - `DecisionPlane.propose()`
  - promotion proposal generation for high-quality evaluated outcomes
  - suppression proposal generation for weak-grounding / kb-underused outcomes with noisy retrieval evidence
- Added `chatgptrest/eval/experiment_registry.py`:
  - file-backed `ExperimentCandidate`
  - `ExperimentRun`
  - `ExperimentRegistry`
  - canary start requires explicit rollback trigger
- Added focused tests for decision generation and experiment lifecycle enforcement.

## Why
- v2 requires a decision plane before any bounded proposer or rollout controller can exist.
- This lane keeps everything observer-only: no proposal can change runtime behavior by itself.
- File-backed registry is enough for scaffolding the experiment lifecycle without colliding with the outcome-ledger lane.

## Verification
- `python3 -m py_compile chatgptrest/eval/decision_plane.py chatgptrest/eval/experiment_registry.py tests/test_decision_plane.py`
- `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_decision_plane.py tests/test_evaluator_service.py`

## Notes
- `DecisionPlane` only emits proposals. It does not mutate retrieval policy, KB scores, or promotion state.
- `ExperimentRegistry` enforces rollback evidence on canary starts, which is the minimum rollout governance hook needed before any adaptive rollout is allowed.
