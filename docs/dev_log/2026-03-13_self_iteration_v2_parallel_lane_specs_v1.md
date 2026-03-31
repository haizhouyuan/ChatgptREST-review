# 2026-03-13 Self-Iteration V2 Parallel Lane Specs v1

## Shared frozen contracts
- Retrieval surfaces are frozen.
- Execution identity fields are frozen:
  - `trace_id`
  - `run_id`
  - `job_id`
  - `task_ref`
  - `logical_task_id`
  - `identity_confidence`

## Lane C — Actuator Governance
- Goal: govern existing actuators without changing default runtime behavior.
- Allowed write set:
  - `chatgptrest/evomap/actuators/`
  - new `chatgptrest/evomap/actuators/registry.py`
  - actuator tests only
- Forbidden files:
  - `chatgptrest/telemetry_contract.py`
  - `chatgptrest/core/db.py`
  - `chatgptrest/api/routes_consult.py`
  - `chatgptrest/core/advisor_runs.py`
- Acceptance:
  - each actuator exposes mode/owner/candidate_version/rollback_trigger metadata
  - audit trail exists for state changes
  - no default behavior broadening

## Lane D — Observer-Only Outcome Ledger
- Goal: durable outcome ledger with no runtime mutation.
- Allowed write set:
  - new `chatgptrest/quality/`
  - `chatgptrest/core/db.py`
  - closeout hooks in `chatgptrest/core/advisor_runs.py` only if strictly needed
  - outcome-ledger tests only
- Forbidden files:
  - `chatgptrest/telemetry_contract.py`
  - `chatgptrest/api/routes_consult.py`
  - `chatgptrest/cognitive/telemetry_service.py`
- Acceptance:
  - one durable outcome row per completed execution outcome
  - observer-only semantics
  - replay/idempotency coverage

## Lane E — Evaluator Plane Seed
- Goal: wrap existing QA inspector as evaluator adapter with human-label sink.
- Allowed write set:
  - `chatgptrest/advisor/qa_inspector.py`
  - new files under `chatgptrest/eval/`
  - evaluator tests only
- Forbidden files:
  - `chatgptrest/core/db.py`
  - `chatgptrest/telemetry_contract.py`
  - `chatgptrest/api/routes_consult.py`
- Acceptance:
  - evaluator output schema exists
  - human label sink exists
  - meta-eval scaffolding exists

## Lane F — Promotion/Suppression Decision Seed
- Goal: produce observer-only promotion/suppression proposals.
- Allowed write set:
  - new `chatgptrest/eval/decision_plane.py`
  - new `chatgptrest/eval/experiment_registry.py`
  - decision-plane tests only
- Forbidden files:
  - `chatgptrest/core/db.py`
  - `chatgptrest/telemetry_contract.py`
  - `chatgptrest/api/routes_consult.py`
  - `chatgptrest/advisor/qa_inspector.py`
- Acceptance:
  - only proposal objects, no runtime mutation
  - offline/shadow/canary lifecycle recorded in schema or domain objects
  - rollback evidence required for canary-ready candidates
