# Service Optimization TODOList (2026-02-27)

## Scope

- Repository: `/vol1/1000/projects/ChatgptREST`
- Goal: execute a closed-loop optimization package focused on reliability, client semantics, and operational hygiene.
- Execution mode: `define -> implement -> test -> operate -> verify` in one pass.

## Baseline Snapshot (before changes)

- `ops/status` showed high historical debt in non-terminal states (`needs_followup`, `blocked`, `cooldown`) and open incidents.
- Open client issues included a mix of recent active failures and stale historical backfill entries.
- MCP stateless wait had known mismatch risk (`long timeout requested` vs `foreground cap + background unsupported`).
- `/v1/jobs/{job_id}/answer|conversation` not-ready/missing-artifact errors lacked strong next-action contract.

---

## TODO (Execution + Acceptance)

### T1. Publish executable optimization checklist
- Status: `DONE`
- Steps:
1. Create this document with explicit task breakdown.
2. Ensure each task includes: implementation steps, test steps, and acceptance criteria.
3. Keep this file as the single source of truth; update status in-place when done.
- Acceptance:
1. Checklist exists in `docs/reviews/` and is versioned.
2. Every later task has objective pass/fail evidence.
- Evidence:
1. This checklist is tracked in git at `docs/reviews/service_optimization_todolist_20260227.md`.

### T2. Add stale backlog janitor tool (jobs/issues)
- Status: `DONE`
- Steps:
1. Add `ops/backlog_janitor.py` with two modes: `--dry-run` and `--apply`.
2. Implement stale selectors:
   - jobs: stale non-terminal candidates (`needs_followup|blocked|cooldown`) older than threshold.
   - issues: stale open issues by source/status/age.
3. For `--apply`, mutate safely:
   - issues: update to `mitigated` via REST API with actor/note.
   - jobs: default no hard mutation unless explicit flag (safety-first).
4. Emit JSON summary report for auditing.
- Acceptance:
1. Dry-run prints deterministic counts and candidate IDs.
2. Apply mode updates issues with clear actor/note and reports updated IDs.
3. Tool exits non-zero on API/database hard failures.
- Evidence:
1. Implemented: `ops/backlog_janitor.py`.
2. Tests: `tests/test_backlog_janitor.py`.
3. Dry-run/apply reports written under `artifacts/monitor/reports/backlog_janitor/`.

### T3. Enhance `/v1/ops/status` observability
- Status: `DONE`
- Steps:
1. Extend response schema with freshness-aware metrics:
   - non-terminal total and stale buckets.
   - open issue freshness buckets (recent vs stale).
2. Keep backward compatibility for existing fields.
3. Wire SQL queries in route implementation.
- Acceptance:
1. Existing consumers still read old fields unchanged.
2. New fields are present and numerically correct in API response.
3. Tests cover field presence and representative values.
- Evidence:
1. Schema: `chatgptrest/api/schemas.py` (`OpsStatusView.nonterminal_backlog`, `open_issue_freshness`).
2. Route: `chatgptrest/api/routes_ops.py`.
3. Tests: `tests/test_ops_endpoints.py`.
4. Live check (after service restart): `/v1/ops/status` now returns populated `nonterminal_backlog` and `open_issue_freshness`.

### T4. Improve MCP stateless wait semantics
- Status: `DONE`
- Steps:
1. In `chatgptrest_job_wait`, when long wait cannot background-handoff in stateless mode, return explicit wait strategy metadata.
2. Add clear `next_action` guidance for callers (poll path and recommended poll interval).
3. Preserve existing behavior for stateful background mode.
- Acceptance:
1. Stateless fallback response contains unambiguous machine-readable hint fields.
2. Existing stateful/background tests continue to pass.
3. New tests verify stateless guidance payload.
- Evidence:
1. Updated helper in `chatgptrest/mcp/server.py` (`wait_strategy`, `background_wait_supported`, `next_action`).
2. Tests: `tests/test_mcp_job_wait_autocooldown.py` and `tests/test_mcp_stateless_mode.py`.
3. MCP service reloaded (`chatgptrest-mcp.service`) to activate new wait semantics.

### T5. Return structured next-action hints for chunk endpoints
- Status: `DONE`
- Steps:
1. For `/v1/jobs/{job_id}/answer` and `/conversation`:
   - when not ready: include structured `next_action` guidance.
   - when artifact missing: include structured repair guidance.
2. Keep HTTP status codes unchanged.
- Acceptance:
1. 409/503 responses include actionable `detail.next_action` contract.
2. Existing clients relying on status codes are unaffected.
3. Tests validate both not-ready and missing-artifact paths.
- Evidence:
1. Added structured detail builders in `chatgptrest/api/routes_jobs.py`.
2. Tests: `tests/test_contract_v1.py`.

### T6. Add regression tests for T2-T5
- Status: `DONE`
- Steps:
1. Add/extend tests in `tests/` for new route fields and detail payloads.
2. Add tests for MCP stateless guidance behavior.
3. Add tests for janitor tool dry-run and apply path (mocked API).
- Acceptance:
1. New tests fail before implementation and pass after implementation.
2. Targeted pytest suite is green.
- Evidence:
1. Executed: `./.venv/bin/pytest -q tests/test_backlog_janitor.py tests/test_ops_endpoints.py tests/test_contract_v1.py tests/test_mcp_job_wait_autocooldown.py tests/test_mcp_stateless_mode.py`.
2. Result: passed.

### T7. Execute operational cleanup and record evidence
- Status: `DONE`
- Steps:
1. Run janitor in dry-run and save report.
2. Run janitor apply for stale issue subset (safe scope).
3. Re-check `ops/status` + issue list and record delta.
- Acceptance:
1. Evidence files saved under `artifacts/monitor/reports/`.
2. Stale open issue count reduced.
3. No regression on recent active issues.
- Evidence:
1. Dry-run report: `artifacts/monitor/reports/backlog_janitor/backlog_janitor_20260227T025202Z_dryrun.json`.
2. Apply report: `artifacts/monitor/reports/backlog_janitor/backlog_janitor_20260227T025210Z_apply.json`.
3. Post-check dry-run: `artifacts/monitor/reports/backlog_janitor/backlog_janitor_20260227_postcheck_dryrun.json` (`issue_candidates.stale=0`).
4. Verified via issue APIs: stale `source=ops_backfill_2026-02-17` open issues reduced to zero.

### T8. Update external contract docs
- Status: `DONE`
- Steps:
1. Update `docs/contract_v1.md` for new `/v1/ops/status` fields and chunk endpoint `next_action` detail.
2. Update registry changelog in `docs/client_projects_registry.md` for client-impacting changes.
- Acceptance:
1. Contract doc reflects actual API behavior.
2. Registry records date-scoped capability changes.
- Evidence:
1. `docs/contract_v1.md` updated for `ops/status` and chunk `detail.next_action` semantics.
2. `docs/client_projects_registry.md` updated with 2026-02-27 capability changelog.

### T9. Long-window failure forensics (6h/24h/7d/30d)
- Status: `DONE`
- Steps:
1. Pull time-window stats from `state/jobdb.sqlite3` (`jobs`, `client_issues`).
2. Pull MCP-side transport/policy failures from `artifacts/monitor/mcp_http_failures.jsonl`.
3. Pull API write status profile from `journalctl --user -u chatgptrest-api.service`.
4. Build failure taxonomy and separate “短时偶发” vs “结构性复发”。
- Acceptance:
1. Audit includes concrete counts across 6h/24h/7d/30d windows.
2. Top failure clusters are grouped by `error_type` with examples.
3. Findings distinguish API direct misuse vs driver/UI fragility vs code regression.
- Evidence:
1. Updated audit note: `docs/reviews/api_direct_call_audit_20260227.md` (`Extended window update` section).
2. Runtime snapshot confirms non-terminal debt remains visible in `/v1/ops/status`.

### T10. Create-path policy reject auto-issue loop (online rollout)
- Status: `DONE`
- Steps:
1. Wire `POST /v1/jobs` policy rejects to issue auto-report path (same model as cancel path).
2. Cover policy errors: `client_not_allowed`, `missing_trace_headers`, `pro_smoke_test_blocked`, `trivial_pro_prompt_blocked`, `smoke_test_blocked`, `idempotency_collision`.
3. Add regression tests for allowlist reject and idempotency collision reject auto-report.
4. Expose env knob in registry/docs/env-example and restart API service.
5. Run live verification by triggering a real create rejection and checking Issue Ledger.
- Acceptance:
1. Policy reject creates/reuses `source=api_policy, kind=create_policy` issue record.
2. Regression tests pass.
3. API service restart completed and health check passes.
4. Live verification issue is visible and can be closed for clean ledger.
- Evidence:
1. Code: `chatgptrest/api/routes_jobs.py` (create-route exception auto-report hook).
2. Tests: `tests/test_jobs_write_guards.py`, `tests/test_env_registry.py`.
3. Config/docs: `chatgptrest/core/env.py`, `ops/systemd/chatgptrest.env.example`, `docs/contract_v1.md`, `docs/runbook.md`, `docs/client_projects_registry.md`.
4. Rollout: `systemctl --user restart chatgptrest-api.service` (2026-02-27 15:06 CST), `GET /healthz` returns `ok=true`.
5. Live check: created issue `iss_fe5acff7b0e14a5a98d7493e8211b9c4` (`create policy violation: client_not_allowed`), then closed.

---

## Execution Log

- [x] T1 checklist published
- [x] T2 janitor tool implemented
- [x] T3 ops/status enhanced
- [x] T4 MCP stateless wait semantics improved
- [x] T5 chunk endpoint next-action hints added
- [x] T6 tests added and passing
- [x] T7 cleanup executed with evidence
- [x] T8 docs synchronized
- [x] T9 long-window forensics completed
- [x] T10 create-path auto-issue loop online

### Runtime Rollout Notes

- 2026-02-27 10:57 CST: restarted `chatgptrest-api.service` and `chatgptrest-mcp.service` to load this optimization batch.
- 2026-02-27 15:06 CST: restarted `chatgptrest-api.service` to load create-path auto-issue reporting.
