# Code Context Map

The two proposals must be judged against the current implementation, not against a blank slate.

## A. Task Harness / Long-Running Agent Core

- `chatgptrest/advisor/task_intake.py`
- `chatgptrest/advisor/task_spec.py`
- `chatgptrest/kernel/artifact_store.py`
- `chatgptrest/eval/evaluator_service.py`
- `chatgptrest/eval/decision_plane.py`
- `chatgptrest/quality/outcome_ledger.py`
- `chatgptrest/core/completion_contract.py`
- `chatgptrest/core/job_store.py`
- `chatgptrest/api/routes_jobs.py`
- `chatgptrest/kernel/work_memory_manager.py`
- `chatgptrest/kernel/work_memory_importer.py`

Judge the proposal against these questions:

- what already exists but is fragmented?
- what is missing at the task-control level?
- what should become durable state instead of transcript/event inference?
- what should be promoted into first-class runtime contracts?

## B. Planning / Memory / Runtime Context

- `chatgptrest/cognitive/context_service.py`
- `chatgptrest/cognitive/memory_capture_service.py`
- `chatgptrest/kernel/work_memory_objects.py`
- `chatgptrest/kernel/work_memory_policy.py`
- `config/work_memory_governance.yaml`
- `docs/dev_log/2026-03-30_work_memory_backfill_importer_walkthrough_v1.md`
- `docs/ops/work_memory_backfill_importer_runbook_v1.md`

Judge the proposal against these questions:

- where should task harness stop and work-memory begin?
- what should flow into memory only after outcome/promotion?
- what should stay in task control instead of memory?

## C. opencli / CLI-Anything Integration Reality Check

- `chatgptrest/api/routes_agent_v3.py`
- `chatgptrest/kernel/skill_manager.py`
- `chatgptrest/advisor/standard_entry.py`
- `chatgptrest/advisor/dispatch.py`
- `chatgptrest/kernel/market_gate.py`
- `chatgptrest/evomap/knowledge/skill_suite_review_plane.py`
- `ops/ingest_skill_suite_validation_to_evomap.py`
- `ops/policies/skill_platform_registry_v1.json`

Mirrored external code under review:

- `docs/reviews/agent_harness_20260331/external_code/opencli/`
- `docs/reviews/agent_harness_20260331/external_code/cli_anything/`

Judge the proposal against these questions:

- is the proposed execution seam realistic for the current route graph?
- should `opencli` be treated as a trusted executor or a controlled external substrate?
- should `CLI-Anything` outputs be treated as internal skills or untrusted generated artifacts?
- where does review evidence end and canonical registry authority begin?

## D. Review Style Requirement

The answer should not stop at “directionally correct”.

It must clearly separate:

- confirmed strengths
- architectural mistakes
- hidden assumptions
- missing phases
- high-risk implementation traps
- recommended execution order
- acceptance criteria
