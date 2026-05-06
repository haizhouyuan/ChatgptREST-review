# 2026-03-11 ChatgptREST + OpenClaw Production Readiness Fix Walkthrough v1

## Scope

This walkthrough records the production-readiness fix batch for:

- ChatgptREST branch: `codex/prod-readiness-fixes-20260311`
- OpenClaw branch: `codex/prod-readiness-fixes-20260311`

The batch addresses the highest-signal launch blockers found in the production review:

- v1/v2 auth boundary mismatch
- mutating GET reconcile behavior
- weak advisor ask auto-idempotency
- unrestricted `openclaw_mcp_url`
- missing readiness endpoint
- OpenClaw plugin identity gaps
- OpenClaw trusted-proxy single-host CIDR drift
- OpenClaw restart failure against the current production `openclaw.json`
- missing bundled `acpx` and `diffs` plugins on the active OpenClaw branch

## ChatgptREST Changes

Committed fixes on the ChatgptREST branch:

- `e5c286f` `docs: add production readiness fix todo`
- `df06298` `fix: separate advisor reconcile writes from reads`
- `280c3e7` `fix: harden advisor ask idempotency and openclaw mcp urls`
- `ecbe91c` `fix: restrict cc control routes and add readyz`

What changed:

- Global Bearer auth now exempts `/v2/*`, so OpenMind/OpenClaw `X-Api-Key` auth still works.
- `GET /v1/advisor/runs/{run_id}` is now read-only.
- Explicit `POST /v1/advisor/runs/{run_id}/reconcile` was added for mutating reconciliation.
- Guardian HTTP calls now inject the correct v1 auth headers.
- `/v2/advisor/ask` auto-idempotency now includes identity/context inputs and returns structured `409` on collisions.
- `openclaw_mcp_url` is loopback-only by default unless explicitly overridden by env.
- `/v2/advisor/cc-*` routes are now loopback-only by default, or require a control API key.
- `/readyz` now checks DB plus driver reachability instead of returning a false-green health state.

## OpenClaw Changes

Committed fixes on the OpenClaw branch:

- `241f7c8f9` `fix: preserve plugin session identity context`
- `f76854649` `fix: accept single-host trusted proxy cidrs`
- `1f652c9da` `fix: restore bundled acpx and diffs plugins`
- `4e7d6188c` `fix: restore production config compatibility`

What changed:

- Plugin tool context, `before_tool_call`, `tool_result_persist`, embedded run, and compaction paths now propagate `sessionId` and `agentAccountId` alongside the existing session identifiers.
- Trusted proxy handling now accepts only exact hosts and single-host CIDRs such as `127.0.0.1/32` and `::1/128`.
- Bundled `extensions/acpx` and `extensions/diffs` were restored from `upstream/main` so the active config can resolve them again.
- Config compatibility was restored for fields still present in the production `openclaw.json`:
  - `agents.defaults.subagents.runTimeoutSeconds`
  - `agents.list[].heartbeat.lightContext`
  - `tools.sessions.visibility`
  - `bindings[].type`
  - `plugins.installs.*.integrity`
  - top-level `acp`
- Session tools now honor the legacy `tools.sessions.visibility` fallback.
- `sessions_spawn` now honors configured default subagent timeout values when no explicit timeout is passed.

## Validation

ChatgptREST targeted pytest batches passed during implementation:

- `tests/test_advisor_orchestrate_api.py`
- `tests/test_ops_endpoints.py`
- `tests/test_openclaw_guardian_issue_sweep.py`
- `tests/test_advisor_v3_end_to_end.py`
- `tests/test_openclaw_adapter.py`
- `tests/test_openclaw_cognitive_plugins.py`
- `tests/test_routes_advisor_v3_security.py`

OpenClaw targeted vitest batch passed after the final fixes:

- `src/agents/pi-tools.before-tool-call.test.ts`
- `src/agents/session-tool-result-guard.tool-result-persist-hook.test.ts`
- `src/agents/openclaw-tools.context.test.ts`
- `src/gateway/net.test.ts`
- `src/gateway/auth.test.ts`
- `src/agents/openclaw-tools.subagents.sessions-spawn-prefers-per-agent-subagent-model.test.ts`
- `src/agents/tools/sessions-list-tool.gating.test.ts`
- `src/agents/tools/sessions-send-tool.gating.test.ts`
- `src/agents/tools/sessions-history-tool.gating.test.ts`
- `src/config/config.current-openclaw-compat.test.ts`

Current production OpenClaw config validation now succeeds:

- `valid: true`
- `issues: []`
- `legacyIssues: []`

## Remaining Risks

These were not solved by code changes in this batch and still need operational handling before a full production go-live:

- The active OpenClaw config still contains live secrets in `openclaw.json`; these should move to env/secret storage.
- Only targeted regressions were run for OpenClaw; no full suite or live end-to-end launch rehearsal was completed in this batch.
- The earlier live verifier failures on memory/recall quality need a fresh rerun against the patched branches before declaring launch-ready.

## Notes

- `gitnexus_detect_changes()` was executed before commits, but on this machine it still picked up unrelated repository noise outside the dedicated worktrees, so final scope verification relied on clean worktree status plus targeted test coverage.
- OpenClaw worktree testing required temporarily symlinking the main repo `node_modules` into the worktree because the worktree had no local dependency directory.
