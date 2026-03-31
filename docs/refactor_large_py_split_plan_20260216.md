# ChatgptREST Large .py Split Plan (One-shot: maintainable + extensible + auditable)

> Updated: 2026-02-16
>
> Pro review (primary): `artifacts/jobs/3f2527901bd14127a7444cedf7811e74/answer.md`
>
> Review bundle: `state/chatgpt-pro-packs/chatgptrest_large_py_split_plan_20260215_194543Z_5c93fae.zip`

## Why this doc
ChatgptREST has several mega Python files that act as bottlenecks for:
- safe iteration (high blast radius per change)
- adding providers/features (ChatGPT/Gemini/Qwen UI drift, new tools)
- testability and auditability (hard to pin invariants, hard to review)

This plan proposes a single coherent target architecture and a staged execution sequence that keeps the system running, reviewable, and production-safe.

## Goals (non-negotiable)
1. Feature parity: current REST contract + job state machine + provider kinds remain working.
2. Auditability / mutual trust (互信):
   - stable interfaces frozen as executable constraints (tests + assertions)
   - deterministic idempotency + rate limit semantics
   - unified error taxonomy + structured events
   - evidence packs for side-effectful actions
3. Extensibility:
   - new provider or new tool kind does not require editing a monolith
   - UI-drift fixes should land in isolated provider modules
4. Operational safety:
   - follow P0/P1/P2 rollout discipline
   - auto actions are fail-closed unless explicitly enabled

## Scope: top offenders (line counts)
- `chatgpt_web_mcp/_tools_impl.py` (~17.6k): Playwright automation + tool impls (ChatGPT/Gemini/Qwen) + shared helpers.
- `chatgptrest/worker/worker.py` (~4.6k): leasing, send/wait stages, state machine, provider routing.
- `ops/maint_daemon.py` (~4.0k): incident scan, evidence capture, auto repair, Codex SRE loop.
- `chatgptrest/executors/repair.py` (~2.0k): repair.check/autofix/open_pr orchestration.

## Stability surfaces to freeze (must become executable constraints)
The critical lesson from Pro review: the split is feasible, but it must be guarded by hard, executable constraints. Otherwise the refactor will silently erode “互信” assets.

### A) REST contract surface
- Freeze `docs/contract_v1.md` semantics with contract tests:
  - idempotency 200/409
  - conversation single-flight 409
  - `/answer` chunking semantics and UTF-8 boundaries
  - `/conversation` export semantics

### B) MCP tool registry surface (driver)
- Freeze tool names and parameter schema as a snapshot test:
  - tools must exist (no missing / no duplicates)
  - parameter names must not drift
  - structured output top-level keys must remain compatible

### C) Driver persistent state surface
Safe-enable requires the following state to persist and remain stable across restarts:
- `MCP_IDEMPOTENCY_DB`
- `CHATGPT_BLOCKED_STATE_FILE`
- `CHATGPT_GLOBAL_RATE_LIMIT_FILE`
- wait-refresh/regenerate/thought-guard state files

These defaults must be centralized (single module) and validated at startup (assertions + tests).

### D) Error taxonomy + event schema surface
- Unify `status/phase/reason_type/error_type` into an explicit taxonomy module.
- Make `events.jsonl` / DB event emission go through one wrapper that enforces required fields:
  - who triggered, what action, why decision, retry_after/not_before
  - evidence paths (if any)

### E) Side-effect boundary (no shadow send)
In web automation, “ask” is side-effectful. New/old parallelism must NOT send prompts.
Allowed parallelism patterns:
- offline verify (rehydrate/compare answers without UI)
- shadow export parsing (new vs old parser)
- read-only probes/canaries (self_check, tab_stats, blocked_status)


## Implementation status (worktree)
- Updated: 2026-02-15 23:28 UTC
- Driver modularization (this worktree):
  - Tool contract guardrail: `tests/test_mcp_tool_registry_snapshot.py` + `tests/fixtures/mcp_tools_snapshot.json`
  - Provider refactor guardrails:
    - `tests/test_provider_modules_no_missing_globals.py` (fail-closed missing globals)
    - `tests/test_no_provider_imports_tools_impl.py` (boundary: providers must not import `_tools_impl`)
  - Shared primitives extracted:
    - `chatgpt_web_mcp/runtime/util.py` (ctx/error + slugify)
    - `chatgpt_web_mcp/runtime/paths.py` (debug/ui snapshot paths)
    - `chatgpt_web_mcp/runtime/locks.py` (ask lock)
    - `chatgpt_web_mcp/runtime/ratelimit.py` (per-provider pacing)
    - `chatgpt_web_mcp/runtime/call_log.py` (structured call log)
    - `chatgpt_web_mcp/runtime/concurrency.py` + `chatgpt_web_mcp/runtime/humanize.py`
    - `chatgpt_web_mcp/playwright/cdp.py` + `chatgpt_web_mcp/playwright/navigation.py` + `chatgpt_web_mcp/playwright/evidence.py`
    - `chatgpt_web_mcp/runtime/answer_classification.py` (deep research classification + transient assistant errors)
    - `chatgpt_web_mcp/playwright/input.py` + `chatgpt_web_mcp/playwright/io.py` (typing + browser fetch primitives)
  - Provider splits:
    - `chatgpt_web_mcp/providers/gemini_web.py`
    - `chatgpt_web_mcp/providers/qwen_web.py`
    - `chatgpt_web_mcp/providers/gemini_api.py`
    - `chatgpt_web_mcp/providers/gemini_common.py`
    - `chatgpt_web_mcp/providers/gemini_helpers.py`
  - Compatibility:
    - `_tools_impl.py` removed legacy Gemini/Qwen helper duplicates; providers now own their helpers.
    - ChatGPT `create_image` no longer depends on Gemini-only helper names.
    - `chatgpt_web_mcp/_tools_impl.py` now delegates missing legacy helpers via `__getattr__`.
  - Verification:
    - `pytest -q` passes in this worktree.

## Target architecture (final shape)
The split is by domain boundaries first, then by provider/tool. Two strict rules:
- One module owns global state construction (no duplicated module-level singletons).
- Dependency direction is strictly one-way.

### A) Driver-side: `chatgpt_web_mcp/` (Playwright MCP)
Current pain: `_tools_impl.py` mixes lifecycle, selectors, flows, tool entrypoints, idempotency, locks, netlog/evidence.

#### Proposed structure
```text
chatgpt_web_mcp/
  server.py                 # MCP server startup; stable behavior
  registry.py               # explicit tool registration (avoid import-order drift)
  _tools_impl.py            # compatibility facade (thin re-export/bridge)

  runtime/
    config.py               # env parsing + defaults (single source)
    types.py                # ToolContext/RunMeta/ProviderKind/ToolResult
    errors.py               # taxonomy + normalize
    events.py               # structured driver-side events
    state_paths.py          # state/driver/ path rules + validation
    locks.py                # singleton locks/single-flight (constructed once)
    ratelimit.py            # global + per-provider pacing
    idempotency.py          # MCP idempotency DB access (single impl)
    audit.py                # side-effect actions audit

  playwright/
    cdp.py                  # connect_over_cdp + reconnect strategy (single entry)
    browser.py              # browser/context/page factory (timeouts/stealth)
    navigation.py           # goto_with_retry/waits/backoff
    io.py                   # upload/download primitives (provider-agnostic)
    selectors.py            # shared locator utilities
    evidence.py             # screenshot/html dump/netlog hooks

  providers/
    base.py                 # ProviderAdapter Protocol
    chatgpt/
      adapter.py
      selectors.py
      flows_send.py
      flows_wait.py
      export.py
      errors.py
      probes.py
    gemini/
      adapter.py
      selectors.py
      flows_send.py
      flows_wait.py
      attach_drive.py       # UI attach only (rclone stays server-side)
      errors.py
      probes.py
    qwen/
      adapter.py
      selectors.py
      flows_send.py
      flows_wait.py
      errors.py
      probes.py

  tools/
    chatgpt_web.py          # @mcp.tool entrypoints (stable names)
    gemini_web.py
    qwen_web.py

  compat/
    legacy_exports.py       # transitional: bridge old symbol names
```

#### Dependency direction
- `tools/*` -> `providers/*` -> `playwright/*` + `runtime/*`
- `providers/*` must not import `tools/*`
- `runtime/*` must not import `providers/*` (runtime is the foundation)

#### Stable driver interfaces
- MCP tool names + args/output schema
- driver state file locations and semantics
- idempotency record schema (especially “sent” and conversation_url recovery)
- evidence pack references (paths and manifest fields)

### B) Server-side: `chatgptrest/` (REST + worker + executors)
Goal: make job orchestration thin, policies explicit, and error taxonomy stable.

#### Proposed structure
```text
chatgptrest/
  api/
    app.py
    routes/
      jobs.py
      ops.py
      health.py
    schemas.py
    errors.py

  core/
    config.py
    artifacts.py
    events.py
    taxonomy.py
    guardrails.py
    rate_limit.py
    redaction.py

  db/
    conn.py
    repo/
      jobs.py
      incidents.py
      events.py
      rate_limits.py

  driver/
    protocol.py             # DriverClient Protocol
    client.py               # MCP backend wrapper(s)
    api.py                  # provider-agnostic driver API: ask/wait/export/probes
    errors.py               # normalize driver errors -> core.taxonomy

  executors/
    base.py
    chatgpt_web.py
    gemini_web.py
    qwen_web.py
    repair.py
    registry.py

  worker/
    worker.py               # orchestration only
    lease.py
    router.py
    stages/
      send.py
      wait.py
      repair.py
    policies/
      retries.py
      export_throttle.py
      completion_guard.py
      single_flight.py

  ops/
    maint/
      daemon.py
      cli.py
    incidents/
      model.py
      service.py
    evidence/
      capture.py
      bundle.py
    healers/
      infra.py
    codex_sre/
      analyze.py
      actions.py
```

### C) Ops-side: maint/repair (evidence-first)
- Keep `ops/maint_daemon.py` as thin entrypoint for systemd/runbook compatibility.
- Move real logic into `chatgptrest/ops/*` modules.
- Separate read-only analysis from action execution (allowlist + audit + rate limit + drain-guard).

## Execution plan (Strangler Fig, safe + reviewable)
The strategy is: keep legacy façade files, move internals behind them, lock invariants with tests, and avoid any side-effectful parallelism.

### Phase 0: Guardrails (must do before moving code)
Deliverables:
- REST contract tests (freeze `docs/contract_v1.md` semantics)
- Tool registry snapshot test (freeze MCP tool names + args)
- Runtime state-path validation (single source of truth)
- Taxonomy module (`status/phase/reason_type/error_type`) and event emission wrapper

Acceptance criteria:
- Contract tests and registry tests pass in CI.
- Driver startup prints/records effective state paths.

Rollback:
- No behavior change; safe to revert.

### Phase 1: Split `_tools_impl.py` without behavior change
- Extract `runtime/*` and `playwright/*` first (pure moves).
- Extract provider selectors/probes next.
- Keep `_tools_impl.py` as thin re-export/bridge.

Acceptance criteria:
- Tool registry snapshot unchanged.
- Read-only canaries succeed: `*_self_check`, `tab_stats`, `rate_limit_status`, `blocked_status`.

Rollback:
- `_tools_impl.py` still exists; revert module moves.

### Phase 2: Split tool entrypoints into `tools/*` + explicit `registry.py`
- Move all `@mcp.tool` functions into `tools/*.py`.
- Introduce `registry.register_all(mcp)` to avoid import-order drift.
- Keep compatibility re-exports in `_tools_impl.py`.

Acceptance criteria:
- Tool registry snapshot unchanged.
- Driver server boots with a deterministic import path.

### Phase 3: ProviderAdapter interface (narrow + auditable)
- Introduce `ProviderAdapter` Protocol:
  - open/apply_mode/send/wait/export
  - probes are explicitly read-only
- Eliminate cross-provider if/else in tools and driver API.

Acceptance criteria:
- No tool module imports selector modules directly.
- Side-effect actions emit audit events.

### Phase 4: Split worker + policies + maint/repair
- Split worker into `lease/router/stages/policies`.
- Make export throttle/backoff and completion guard explicit and unit-tested.
- Move maint/repair internals to `chatgptrest/ops/*`.

Acceptance criteria:
- Mock-driver integration tests cover send->wait slicing, export fallback, cancel, idempotency.
- Drain-guard prevents restarts when send-stage is active.

### Phase 5: Safe parallel verification and canary
Allowed parallelism:
- offline verify (e.g. `ops/verify_job_outputs.py`)
- shadow export parser
- read-only canaries

Not allowed:
- any shadow path that may send prompts

Acceptance criteria:
- 12h soak shows no regression in:
  - cooldown/error rates
  - export storm metrics
  - duplicate-send prevented count

## Testing + monitoring checklist (high value)
- Unit: completion guards (deep_research ACK + min_chars), export throttle/backoff, idempotency/dedup.
- Integration (mock driver): SSE timeout, stream error, delayed conversation_url, export missing reply retries.
- UI drift: DOM snapshot tests for critical selectors (composer/message list/model/mode toggles).
- Canary (read-only): self_check/tab_stats/blocked_status across providers.
- Metrics/alerts: CDP connect failures, TargetClosedError, SSE timeouts, export backoff queue size, auto-action attempts blocked by drain-guard.

## Risk control (P0/P1/P2 safe enable)
Fail-closed decisions:
- attachments not confirmed (ChatGPT)
- Drive attach not ready (Gemini)
- idempotency says sent or conversation_url exists: suppress fallback resend

Rate limit + single-flight + drain-guard required:
- restart_driver / restart_chrome
- refresh / regenerate
- any DB autofix actions

Evidence packs required when:
- an auto action runs OR is blocked by guardrails
- include: manifest.json (decision/reason), recent events slice, probe snapshots, optional UI artifacts

## Open questions to resolve before implementation
- How to freeze MCP tool schema snapshot (what to snapshot: tool names + args + top-level keys).
- Where to host “compat” layer and how long to keep it.
- Whether to keep both embedded and external MCP driver backends long-term (recommended: only as a temporary dev safety fuse).
