# ChatgptREST v1 Contract (Frozen)

This document defines the stable REST contract for ChatgptREST. Implementation details may evolve, but any breaking change here requires a new version.

## Base

- Default local base URL: `http://127.0.0.1:18711`
- `Content-Type: application/json`

## Job Status

`status` is one of:

- `queued`
- `in_progress`
- `needs_followup`
- `cooldown`
- `blocked`
- `completed`
- `error`
- `canceled`

## Job Phase

`phase` indicates which stage of processing is active for a job:

- `send` (prompt send stage)
- `wait` (answer collection stage; no new prompt is sent)

## Browser-Visible Retry Pacing

For ChatGPT Web / Gemini Web jobs, any retry that would trigger another visible browser action is fail-safe bounded by a global human-like floor:

- `CHATGPTREST_WEB_HUMAN_RETRY_FLOOR_SECONDS` (default `90`)
- `CHATGPTREST_WEB_HUMAN_RETRY_JITTER_MAX_SECONDS` (default `15`)

This floor applies even when a narrower per-flow knob is configured lower. Examples include:

- worker cooldown retries for UI / infra failures
- wait-phase retries on stable thread URLs
- ChatGPT unsent transient cooldowns
- Gemini inline send retries

The goal is to avoid machine-like `5s/12s/20s/30s` resend cadence that can trigger web anti-abuse controls.

Browser-visible retries are also protected by a rolling retry budget:

- `CHATGPTREST_WEB_RETRY_BUDGET_WINDOW_SECONDS` (default `900`)
- `CHATGPTREST_WEB_RETRY_BUDGET_MAX_PER_JOB` (default `4`)
- `CHATGPTREST_WEB_RETRY_BUDGET_MAX_PER_PROVIDER` (default `12`)
- `CHATGPTREST_WEB_RETRY_BUDGET_WARN_RATIO` (default `0.8`)

This budget counts only retries that would schedule another visible browser action. When the budget is exceeded, the worker fail-closes instead of continuing a browser-visible retry storm:

- terminal `status=needs_followup`
- `last_error_type=WebRetryBudgetExceeded`
- event `browser_retry_budget_exceeded`

ChatGPT frontend rate-limit modals are not normal retryable browser failures. If the driver observes `modal-conversation-history-rate-limit`, the job may return:

- `status=blocked`
- `last_error_type=ChatGPTFrontendRateLimit`
- `blocked_state.reason=frontend_rate_limit`

Clients and repair automation must treat this as a stop-the-world provider/session limit. Do not clear the blocked state or retry ChatGPT Web sends until the blocked-state cooldown expires.
During this state, ChatGPT Web UI actions are forbidden across send, wait, export, refresh, regenerate, self-check, capture, and repair/autofix paths. Status-only probes may read the blocked state; UI-touching probes must skip or return the same blocked result.

Manual ChatGPT Pro use in the shared browser profile is represented as a separate proactive hold:

- `blocked_state.reason=manual_pro_session`

This is not a provider-side 429. It means a human has exclusive use of the shared ChatGPT Pro browser session, so ChatgptREST must not touch ChatGPT Web at all. During this state, the worker pause should be `mode=all` with a ChatGPT-specific `auto_blocked:*` reason so queued/in-progress ChatGPT Web jobs are not claimed while non-ChatGPT lanes can continue. The manual Pro guard must also remove the runtime systemd allow file and apply runtime masks for driver/send/wait units; stopping the guard process alone is not a release.

New `chatgpt_web.*` job submissions are blocked while either the frontend-rate-limit submit gate or the manual Pro hold is active, including direct export/extract jobs such as `chatgpt_web.conversation_export`. `POST /v1/jobs` returns HTTP 429 with:

- `detail.error=chatgpt_frontend_rate_limit_active` for `frontend_rate_limit`
- `detail.error=chatgpt_web_automation_hold_active` for proactive holds such as `manual_pro_session`
- `detail.reason`
- `detail.job_created=false`
- `detail.retry_after_seconds`
- `detail.blocked_until`
- `detail.safe_next_action=wait_for_cooldown_or_use_non_chatgpt_web_provider`
- `Retry-After` response header

This gate is ChatGPT-specific: it does not block `gemini_web.ask` or other non-ChatGPT kinds. It also preserves idempotent replay; if the same `Idempotency-Key` already maps to an existing job, the create endpoint returns that existing job view instead of converting the replay to HTTP 429.

Observability:

- `GET /v1/ops/status` exposes:
  - `retry_budget_window_seconds`
  - `retry_budget_recent_by_provider`
  - `retry_budget_hot_providers`
  - `retry_budget_exceeded_events`
- `GET /v1/ops/retry-budget` returns the provider-level budget dashboard with hot/exceeded state.

## Artifacts and Paths

- `path` in API responses is a **relative path under `ARTIFACTS_DIR`** (e.g. `jobs/<job_id>/answer.txt`).
- The server resolves `path` against `ARTIFACTS_DIR` internally; clients must not assume an absolute filesystem layout.

## Endpoints

### `POST /v1/jobs` (enqueue)

Headers:
- `Idempotency-Key` (required)
- `X-Client-Name` (recommended; caller name, e.g. `codex-worker`)
- `X-Client-Instance` (strongly recommended; caller instance identity, e.g. `hostA-worker2`)
- `X-Request-ID` (strongly recommended; unique per HTTP request, for cross-log tracing)

Optional server gate:
- If `CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST` is configured, write operations enforce `X-Client-Name` allowlist (`POST /v1/jobs`, `POST /v1/jobs/{job_id}/cancel`) and reject others with HTTP 403 `detail.error="client_not_allowed"`.
- For `kind=chatgpt_web.ask|gemini_web.ask|qwen_web.ask`, registered low-level ask identities are allowed through this coarse allowlist gate so the identity/auth/intent decision can happen inside the dedicated ask guard. This means an unsigned maintenance profile now fails as `low_level_ask_client_auth_failed` instead of being masked as `client_not_allowed`.
- Optional fallback: with `CHATGPTREST_ALLOW_FALLBACK_WHEN_MCP_DOWN=1` and `CHATGPTREST_FALLBACK_CLIENT_NAME_ALLOWLIST_WHEN_MCP_DOWN` configured, fallback clients are allowed only when MCP probe (`CHATGPTREST_MCP_PROBE_HOST/PORT`) is unreachable.
- Optional trace-header hard gate: if `CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE=1`, write operations require both `X-Client-Instance` and `X-Request-ID`, otherwise return HTTP 400 `detail.error="missing_trace_headers"`.

Body:
- `kind: string`
- `input: object`
- `params: object`
- `client: object | null` (observability only; not part of idempotency hash)

For `kind=chatgpt_web.ask` (common fields):

`input`:
- `question: string` (required)
- `conversation_url: string | null` (optional follow-up)
- `parent_job_id: string | null` (optional follow-up; server will reuse the parent job's `conversation_url`)
- `file_paths: string[] | null` (optional; server-local paths)
- `github_repo: string | null` (optional)

`params`:
- `preset: string` (required; supported: `auto`, `pro_extended`, `thinking_heavy`, `thinking_extended`, `deep_research`; aliases: `default`/`defaults` → `auto`, `research`/`deep-research`/`deepresearch` → `deep_research`)
- `purpose: string` (optional; recommended `prod|smoke`; used by policy/audit)
- `timeout_seconds: int` (legacy: used for both send+wait timeouts when the split fields are omitted)
- `send_timeout_seconds: int` (optional; tool timeout for the initial send/ask stage)
- `wait_timeout_seconds: int` (optional; per-call timeout for wait polling)
- `max_wait_seconds: int` (best-effort; controls server-side waiting behavior)
- `min_chars: int` (best-effort; used for wait heuristics)
- `allow_queue: bool` (default `false`; if `true`, allow enqueuing a follow-up even when the target conversation already has an active ask job)
- `answer_format: string` (`markdown` or `text`; default `markdown`)
- `deep_research: bool` / `web_search: bool` / `agent_mode: bool`
- `allow_live_chatgpt_smoke: bool` (default `false`; explicit one-off override for `chatgpt_web.ask` live smoke/test/probe guard)
- `format_prompt: string | null` (optional; if set and the primary turn completes, ChatgptREST sends a follow-up message in the same conversation to reformat the answer)
- `format_preset: string` (default `thinking_heavy`; preset used for the formatting follow-up)

Notes:
- `format_prompt` is a **second prompt** and is therefore subject to server-side send throttling (ChatGPT: `CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS`; Gemini: `CHATGPTREST_GEMINI_MIN_PROMPT_INTERVAL_SECONDS`; Qwen: `CHATGPTREST_QWEN_MIN_PROMPT_INTERVAL_SECONDS`, default `0`).
- ChatGPT, Gemini, and Qwen use separate send-throttle counters (they do not share a single 61s interval); defaults: ChatGPT 61s, Gemini 61s, Qwen 0s.
- A common pattern is: `preset=pro_extended` for the primary answer, then `format_preset=thinking_extended` to reformat into strict Markdown/JSON with lower retry cost.
- Thinking-quality guard: for `preset in {pro_extended, thinking_extended, thinking_heavy}`, if a completed answer is still below `min_chars` and the UI result carries no usable `Thought for ...` trace, executor may trigger one same-thread `chatgpt_web_regenerate` attempt without sending a new user prompt.
- If that same-thread regenerate returns `in_progress` / `queued` / `cooldown` / `blocked`, the executor must return that non-completed state so the worker can continue waiting or respect the block. If regenerate is unavailable or fails, the original short no-thinking Pro answer must fail closed as `needs_followup` instead of being accepted as `completed`.
- For research/Pro contracts, a backend-exported assistant message that is complete/final but still below `min_chars` is a non-final quality result, not waitable progress. The worker should transition toward `needs_followup` instead of repeatedly retrying the same completed short answer until the browser-visible retry budget is exhausted.
- Compatibility: when `preset=deep_research` is used for ChatGPT, server normalizes to `preset=thinking_heavy` and sets `params.deep_research=true` before execution.
- If `send_timeout_seconds` is omitted, the server caps the initial send/ask stage to a conservative default (currently 180s; override via `CHATGPTREST_DEFAULT_SEND_TIMEOUT_SECONDS` or by explicitly setting `params.send_timeout_seconds`). For ChatGPT `deep_research=true`, `CHATGPTREST_CHATGPT_DEEP_RESEARCH_SEND_TIMEOUT_SECONDS` (default 240s) is applied as a send-timeout floor so attachment upload and Deep Research activation are not cut off by an overly low global cap.
- Send-phase transport failures distinguish between:
  - **same-session repair**: thread evidence exists or the browser clearly entered a verification/challenge state
  - **safe retry of unsent send**: idempotency evidence says `sent=false` and no thread URL was recovered
  - when available, these hints appear in metadata as `send_phase_evidence` (`idempotency_sent`, `recovered_conversation_url`, `requested_conversation_url`, `safe_to_retry_send`)
- If send retries are exhausted before a prompt-sent receipt, the job emits `web_send_retry_exhausted` with `recommended_params`, attachment statistics, and `safe_next_action`.
- For automation/public-MCP asks, default `min_chars` is still provider-specific (`chatgpt=800`, `gemini=200`), but ChatGPT compact-output prompts (for example “4 条以内要点回答”) are now auto-relaxed to `min_chars=200` unless the caller explicitly provides `min_chars`.
- For automation/public-MCP asks using push delivery (`push_only` / `push_plus_cache`), backend job `max_wait_seconds` is now floored to **1800s** even if the caller asks for a shorter foreground-style wait window. This prevents background Pro jobs from re-entering 30-second wait churn just because the client wants an immediate submit receipt.
- Deep Research note: ChatGPT Web may first ask for confirmation / clarifying questions before starting Deep Research. Optional: enable a single auto-followup (“OK…不要再反问”) via `CHATGPT_DEEP_RESEARCH_AUTO_FOLLOWUP=true` (default disabled).
- For `file_paths`:
  - Prefer **absolute paths**.
  - Relative paths are interpreted relative to the `ChatgptREST/` repo root.
  - Accepted roots are the ChatgptREST repo, `ChatgptREST/tmp/`, `/tmp/chatgptrest_uploads/`, and any explicit `CHATGPTREST_EXTRA_ALLOWED_FILE_ROOTS` entries. Arbitrary `/tmp/...` paths are rejected; callers must stage attachments into a sanctioned upload root rather than bypassing project provenance with ad hoc temp copies.
  - Public MCP job creation (`automation_ask`, `chatgptrest_ask`, and legacy MCP submit helpers) auto-stages explicit local `input.file_paths[]` that exist but are outside accepted roots into `/tmp/chatgptrest_uploads/mcp_staged/...` before calling `/v1/jobs`. The API contract remains fail-closed for direct `/v1/jobs` callers; auto-staging is a northbound MCP convenience, not a broad API allowlist. Staged jobs emit `mcp_attachment_staged` in job events and also retain `client.mcp_attachment_staging` metadata.
  - Paths outside allowed roots return HTTP 403 with `detail.error="file_paths_outside_allowed_directory"` and `detail.safe_next_action`.
  - Non-existent paths are rejected early (HTTP 400) to avoid “job created but upload fails later”.
  - If a declared `input.file_paths[]` entry disappears between enqueue and provider execution, executor fail-closes with `last_error_type=AttachmentFileNotFound` instead of retrying a broken upload flow.
  - If a ChatGPT ask carries too many text-like attachments for the web composer, ChatgptREST may auto-generate `CHATGPT_ATTACH_BUNDLE.md` + `CHATGPT_ATTACH_INDEX.md` and upload those instead. Corresponding worker event: `chatgpt_attachments_bundled`.
  - `.zip` attachments are uploaded as-is unless zip-expansion is enabled. If ChatGPT routes the upload into an external connector flow stub (e.g. Adobe Acrobat), disable the Adobe Acrobat App in ChatGPT.
  - Attachment-contract preflight is now stricter about what counts as a local file reference:
    - URI-like tokens containing `://` are **not** treated as local attachments.
    - slash-delimited conceptual labels such as `episodic/semantic/procedural` are **not** treated as local attachments.
    - real local paths like `/vol1/...`, `./bundle.md`, `../notes/report_v1.md`, `C:\tmp\review.pdf` still require explicit `input.file_paths`.
  - High-risk Web ask requests that tell ChatgptREST to read/review/audit a local bundle/file but omit `input.file_paths` fail closed at create time with HTTP 400 `detail.error="attachment_contract_missing"` and `detail.error_type="AttachmentContractMissing"` (`CHATGPTREST_FAIL_CLOSED_HIGH_RISK_ATTACHMENT_CONTRACT_ON_CREATE`, default `true`). Executor-level fail-closed remains as defense in depth.
- `file_paths` is part of the idempotency payload: if you reuse an `Idempotency-Key` but change path representation (absolute vs relative), you will get HTTP 409 with `detail.error="idempotency_collision"` and the existing job/hash hints.
- `/v1/jobs`, `/v1/ops`, and `/v1/issues` rejections with HTTP 400/401/403/409/429 are locally audited to `artifacts/monitor/api_rejections/YYYYMMDD.jsonl` with sanitized correlation fields (`Idempotency-Key`, `X-Client-Name`, `X-Client-Instance`, `X-Request-ID`). Authorization values are not recorded.
- ChatgptREST is tunnel-first. With `CHATGPTREST_REJECT_PUBLIC_INGRESS=1` (default), API requests whose real client IP is public/global are rejected with HTTP 403 `detail.error="public_ingress_blocked"`. Localhost, private networks, link-local/reserved addresses, and Tailscale/CGNAT `100.64.0.0/10` are allowed. Temporary fixed public exceptions can be declared with `CHATGPTREST_PUBLIC_INGRESS_ALLOW_CIDRS`, but the supported default is SSH/Tailscale tunnel access to `127.0.0.1:18711` and `127.0.0.1:18712/mcp`.
- Conversation single-flight (wind-control guard):
  - If a `chatgpt_web.ask` request targets an existing conversation (`input.conversation_url` or `input.parent_job_id` resolves to one),
    and the server detects another active ask job in that same conversation (`status in queued/in_progress`),
    it returns **HTTP 409** with `detail.error="conversation_busy"` unless you explicitly set `params.allow_queue=true`.
  - Even when `allow_queue=true`, send workers still enforce “one in-progress ask per conversation” using the `conversation_id` column
    (prevents rapid-fire user messages).
  - Global toggle: `CHATGPTREST_CONVERSATION_SINGLE_FLIGHT` (default `true`).
- Pro safety guardrails (default on):
  - `chatgpt_web.ask` + live smoke/test/probe style request returns HTTP 400 `detail.error="live_chatgpt_smoke_blocked"` unless `params.allow_live_chatgpt_smoke=true`.
    This covers `purpose=smoke/test/...`, explicit smoketest prefixes, known synthetic fault-probe prompts, and registered smoke client names.
  - Low-level web ask callers (`chatgpt_web.ask|gemini_web.ask|qwen_web.ask`) must declare a registered source identity.
    Preferred headers are `X-Client-Id` or `X-Client-Name`; optional provenance headers are `X-Client-Instance`, `X-Source-Repo`,
    `X-Source-Entrypoint`, and `X-Client-Run-Id`. Unknown or missing identities now fail closed with:
    - HTTP 403 `detail.error="low_level_ask_client_identity_required"`
    - HTTP 403 `detail.error="low_level_ask_client_not_registered"`
    For registered `auth_mode=hmac` profiles, the request must also include `X-Client-Timestamp`, `X-Client-Nonce`,
    and `X-Client-Signature`; replayed or invalid signatures fail with `low_level_ask_client_auth_failed`.
    Maintenance/internal low-level ask identities are now HMAC-scoped, not registry-name-only.
    Registered automation callers are also prevented from keeping registry-name-only low-level ask access: if an
    `automation_registered` profile still declares `allowed_surfaces=["low_level_jobs", ...]` without `auth_mode=hmac`,
    ingress now fails closed with HTTP 500 `detail.error="low_level_ask_registry_misconfigured"`.
    Registry source of truth: `ops/policies/ask_client_registry.json`.
  - Direct low-level `POST /v1/jobs kind=chatgpt_web.ask` is blocked by default with HTTP 403
    `detail.error="direct_live_chatgpt_ask_blocked"` for interactive coding clients. `params.allow_direct_live_chatgpt_ask=true`
    is no longer a bypass for interactive/unregistered callers; the only supported low-level exceptions are registered
    maintenance/internal identities (for example `chatgptrest-admin-mcp` or `chatgptrestctl-maint`), plus the in-process FastAPI
    `TestClient` harness exemption used by local tests.
    Preferred path for coding agents is the public MCP `automation-kernel-v1` contract. `/v3/agent/turn` is no longer the default shared backend entrypoint for Hermes / Codex / Claude Code / Antigravity.
  - For coding-agent client identities (for example `codex`, `claude-code`, `antigravity`, legacy bare MCP wrappers, or `chatgptrestctl`), direct low-level
    `POST /v1/jobs kind=gemini_web.ask|qwen_web.ask` is also blocked by default with HTTP 403
    `detail.error="coding_agent_low_level_ask_blocked"` unless the caller uses an explicitly allowed maintenance/internal identity.
    Preferred path for coding agents remains the public MCP `automation_*` surface at `http://127.0.0.1:18712/mcp`.
  - Registered automation callers on low-level ask are further gated by identity-aware intent review:
    - structured extractor / extractor-style JSON-only microtasks and sufficiency gates fail with HTTP 403 `detail.error="low_level_ask_intent_blocked"`
    - `testing_only` clients cannot create live ChatGPT ask jobs
    - gray-zone automation callers may be classified by `codex exec --output-schema` using `ops/schemas/ask_guard_decision.schema.json`; substantive review/report asks that prefer JSON output are allowed to reach this classifier instead of being hard-blocked up front
    - when the classifier returns `allow_with_limits`, ingress now enforces the limits by downgrading request fields such as `preset`, `deep_research`, and `min_chars` before the job is created
    - accepted low-level automation jobs may additionally be rejected by runtime controls such as `max_in_flight_jobs`, `max_in_flight_by_kind`, and `dedupe_window_seconds`, which surface as `low_level_ask_client_concurrency_exceeded`, `low_level_ask_client_kind_concurrency_exceeded`, or `low_level_ask_duplicate_recently_submitted`
    - duplicate detection for low-level ask uses a prompt fingerprint that includes readable `input.file_paths` by filename, size, and SHA-256 content, so restaging the same packet under a different allowed root does not create a fresh semantic request
    - `codex exec` for this classifier now prefers the repo's known wrapper install (`~/.home-codex-official/.local/bin/codex`) before generic `PATH` discovery, so low-level ask guard does not silently fall onto an unrelated PATH-level Codex binary with the wrong auth stack
    On accepted requests, normalized client identity and decision metadata are persisted in `client_json` and `params.ask_guard`.
  - `/v2/advisor/ask` now deduplicates recent equivalent requests within the configured window before controller dispatch. Matching first uses the current stable `request_fingerprint`; if the existing row predates fingerprint hashing, the server falls back to exact `question + intent_hint + session_id + user_id + role_id` matching so legacy advisor asks do not open a fresh ChatGPT conversation just because the fingerprint format changed.
  - Public MCP surface:
    - `automation-kernel-v1` is the only canonical shared public surface. Canonical tools: `automation_ask`, `automation_result`, `automation_job_create`, `automation_job_status`, `automation_job_answer`, `automation_job_cancel`, `automation_job_events`, `automation_conversation_fetch`, `automation_conversation_get`, `automation_conversation_find`, `automation_gemini_generate_image_submit`.
    - `automation_conversation_fetch` is the canonical URL-to-conversation recovery entry for human-created ChatGPT Web conversations. It creates a read-only `chatgpt_web.conversation_export` job with `manual_harvest=true`, `read_only_harvest=true`, and no prompt send; consumers then use `automation_result` for rendered Markdown or `automation_conversation_get` for raw export chunks.
    - Retained advanced MCP-only tools may still exist outside the canonical shared automation surface. In particular, `chatgptrest_consult` / `chatgptrest_consult_result` can be retained as an optional multi-model consultation capability even though `/v1/advisor/consult*` is retired on the main REST app surface.
    - Provider capability truth is frozen in `docs/contracts/2026-04-17_provider_capability_matrix_contract_v1.md`. Public MCP preflight must reason from the provider-effective preset, not only the caller-requested preset.
    - Public MCP no longer treats `advisor_agent_*` / `coding_agent_*` as the canonical shared tool family. Task understanding belongs in Hermes or other client agents; public MCP only exposes the explicit automation kernel plus operational helpers.
    - `automation_ask` request contract is explicit and narrow:
      - `question`
      - `provider`
      - `preset`
      - optional `requested_execution_lane`
      - optional `premium_allowed`
      - optional `task_object_contract`
      - optional `parent_job_id`
      - optional `conversation_url`
      - optional `file_paths`
      - optional `deep_research`
      - optional `preflight`
      - optional `provider_selection`
      - `delivery_preference`
      - `auto_wait`
      - `notify_done`
    - Execution-layer truth is frozen in `docs/contracts/2026-04-17_execution_layer_governance_contract_v1.md`:
      - caller/Hermes owns lane authorization (`requested_execution_lane`, `premium_allowed`)
      - ChatgptREST normalizes provider-effective truth inside the selected lane
      - canonical receipt / job view / result view now expose `requested/effective/rewrite/fallback` governance fields directly
    - Canonical acceptance, compat acceptance, and probe/smoke evidence are now explicitly split; `docs/ops/2026-04-17_public_surface_acceptance_split_v1.md` is the mouthpiece. Transport probes must not be reused as premium happy-path evidence.
    - Client agents must submit prompt, attachment inventory, preflight checklist, and provider-selection rationale together. Public MCP does not perform advisor/task-intake routing on behalf of the caller.
    - Streamable-HTTP MCP clients are expected to perform `initialize` (and best-effort `notifications/initialized`) before `tools/call`; the repo validation harness and shared wrappers follow this handshake.
    - Public MCP is sessionful by default. Successful `initialize` returns an `mcp-session-id` response header, and subsequent `tools/call` requests should send that header back. `CHATGPTREST_AGENT_MCP_STATELESS_HTTP=1` is an explicit compatibility override, not the default.
    - `automation_ask(auto_wait=true)` now defaults to push semantics on the sessionful public MCP runtime:
      - submit returns immediately
      - `completion_mode=push`
      - `background_wait_started=true`
      - `front_action=return_now`
      - `next_action.kind=await_push`
      - `next_action.channel=controller`
      - `next_action.fallback_tools=[automation_job_events, automation_result]`
      Front clients should not hand-roll polling loops or foreground wait.
    - Public MCP northbound identity is preserved, but low-level submit is projected onto registered internal submit wrappers (`chatgptrest_*_ask_submit`, `chatgptrest_gemini_generate_image_submit`) before `/v1/jobs` creation. This keeps public MCP stable while satisfying low-level ask HMAC and allowlist rules.
    - Public MCP startup/runtime contract fail-closes on missing shared allowlist identity. `automation_job_cancel` remains tool-level fail-closed when the running public client identity is missing from `CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST`, but cancel misconfiguration no longer takes the entire public MCP surface down.
    - `automation_job_cancel(job_id, reason="...")` accepts an explicit cancellation reason. If `CHATGPTREST_REQUIRE_EXPLICIT_MCP_CANCEL_REASON=1`, the public MCP cancel tool refuses to send `/cancel` without that explicit `reason` and returns `error_type="ExplicitCancelReasonRequired"`.
  - `Pro + trivial prompt` (e.g. “请回复OK”) returns HTTP 400 `detail.error="trivial_pro_prompt_blocked"` with no request-level override.
  - `Pro + purpose=smoke/test/...` returns HTTP 400 `detail.error="pro_smoke_test_blocked"` with no request-level override.
  - Unified env toggle: `CHATGPTREST_ENFORCE_PROMPT_SUBMISSION_POLICY=1` (default on).
  - Worker completion guard now has a legacy trivial wait-loop breaker. If an old synthetic/trivial ask survives ingress and repeatedly hits `completion_guard_downgraded(reason=answer_quality_suspect_short_answer)`, the worker will finalize the job after `CHATGPTREST_LEGACY_TRIVIAL_WAIT_LOOP_BREAKER_THRESHOLD` repeated downgrades instead of requeueing forever.
  - Pro/thinking thought guard now fail-closes high-value research/review contracts that complete without a usable `Thought for ...` observation, even when `answer_chars >= min_chars`. This default is controlled by `CHATGPTREST_THOUGHT_GUARD_REQUIRE_TRACE_FOR_RESEARCH=1`.
  - For such jobs, `gpt-5-5-pro` plus `thinking_effort=extended` export metadata proves model selection, but not thinking-path quality. A completed answer without a UI thinking trace is repaired by same-thread regenerate; if regenerate cannot start, the result becomes `needs_followup` with `error_type="ThoughtGuardMissingTrace"`.

For `kind=gemini_web.ask` (Gemini web automation):

`input`:
- `question: string` (required)
- `conversation_url: string | null` (optional follow-up; Gemini web URL)
- `parent_job_id: string | null` (optional follow-up; server will reuse the parent job's `conversation_url`)
- `file_paths: string[] | null` (optional; server-local paths; see Notes)
- `github_repo: string | null` (optional; repo URL for Gemini “导入代码”; requires `params.enable_import_code=true`)

`params`:
- `preset: string` (required; supported: `pro`, `deep_think`; aliases: `default`/`defaults`/`auto` → `pro`, `deepthink` → `deep_think`, `thinking`/`pro_thinking` → `pro`)
- `deep_research: bool` (optional; default `false`; when `true`, Gemini executor uses the Deep Research tool path)
- `purpose: string` (optional; recommended `prod|smoke`; used by policy/audit)
- `timeout_seconds: int` (legacy; used for both send+wait timeouts when the split fields are omitted)
- `send_timeout_seconds: int` (optional; tool timeout for the initial send/ask stage)
- `wait_timeout_seconds: int` (optional; per-call timeout for wait polling)
- `max_wait_seconds: int` (best-effort; controls server-side waiting behavior)
- `min_chars: int` (best-effort; used for wait heuristics)
- `allow_queue: bool` (default `false`; same semantics as `chatgpt_web.ask`)
- `answer_format: string` (`markdown` or `text`; default `markdown`)
- `enable_import_code: bool` (default `false`; when true and `input.github_repo` is set, driver runs Gemini UI “导入代码”)
- `drive_name_fallback: bool` (default `false`; when true and a Drive URL can’t be resolved, driver falls back to picker filename search instead of `cooldown`)

Notes:
- For public repo review on ChatGPT web, the public GitHub URL is sufficient. A separate review repo is optional and mainly for private mirrors, curated subsets, or import-size control.
- Gemini web jobs support `input.github_repo` **only** when `params.enable_import_code=true` (otherwise server returns HTTP 400).
- Gemini web jobs support `params.deep_research=true`; this cannot be combined with `input.github_repo` (executor returns `error` for that invalid combination).
- `input.file_paths` is supported. For the common phase-1 case of exactly one small readable text file with `deep_research=false`, ChatgptREST may inline that file into the Gemini prompt body and skip Drive upload entirely; `meta.attachment_preprocess.single_text_inlined=true` records this shortcut. If the file is oversized for that inline lane, ChatgptREST fail-closes back to the Drive upload path and records `single_text_inline_skipped=true` with `inline_skip_reason=file_too_large`. All other attachment cases continue on the Drive-attach workflow below.
- `input.file_paths` is otherwise treated as a **Drive-attach workflow**:
  - The worker uploads each local path into Drive via `rclone copyto` to `CHATGPTREST_GDRIVE_RCLONE_REMOTE` (default `gdrive`) under `CHATGPTREST_GDRIVE_UPLOAD_SUBDIR` (default `chatgptrest_uploads`).
  - The worker then resolves each uploaded file’s Drive ID via `rclone lsjson` and passes a Drive URL (`https://drive.google.com/open?id=<id>`) to the internal driver.
  - The internal driver attaches those files via Gemini UI: `+` → `从云端硬盘添加` → paste URL → `插入`.
  - Before upload, executor-side preprocessing can enforce a per-prompt file cap (`CHATGPTREST_GEMINI_MAX_FILES_PER_PROMPT`, default `10`) and auto-generate:
    - `GEMINI_ATTACH_INDEX.md` (inventory / dropped / merged details),
    - `GEMINI_ATTACH_BUNDLE.md` and/or `GEMINI_ATTACH_OVERFLOW.zip` when needed to keep upload count within cap.
  - Deep Research path can expand `.zip` into readable text bundle before upload (`CHATGPTREST_GEMINI_DEEP_RESEARCH_EXPAND_ZIP`, default `true`) to reduce “zip attached but not read” failures.
  - If Drive URL resolution fails, the default behavior is **fail-closed**: return `status=cooldown` (set `params.drive_name_fallback=true` only if you accept unreliable filename search).
- Deep Research send phase can run a no-prompt UI probe first (`gemini_web_self_check`; controlled by `CHATGPTREST_GEMINI_DEEP_RESEARCH_SELF_CHECK`, default `true`):
  - if probe explicitly shows Deep Research tool missing, executor returns `status=needs_followup` (`error_type=GeminiDeepResearchToolUnavailable`) instead of blind-send.
- Send exception retry policy: executor-side outer retry is limited to transport-like connection failures (for example `connection refused`). `deadline exceeded` / SSE stream timeouts do not get an extra outer retry cycle.
- Drive upload/ID resolution error policy:
  - retryable errors (timeouts/transient API issues) -> `status=cooldown` (`reason_type=DriveUploadNotReady`)
  - permanent errors (rclone misconfig/auth, file too large) -> `status=error` (`error_type=DriveUploadFailed`)
- Size precheck: `CHATGPTREST_GDRIVE_MAX_FILE_BYTES` (default `209715200` / 200MiB; set to `0` to disable).
- Optional cleanup (disabled by default): `CHATGPTREST_GDRIVE_CLEANUP_MODE` (`never` | `on_success` | `always`).
- Gemini Web can still use app mentions: if your prompt includes `@Google 云端硬盘` / `@Google Drive` (or `@Google 文档` / `@Google Docs`), the internal driver inserts the real Gemini app mention (not plain text). Treat this as a convenience for **referencing existing Drive resources**, not as a reliable substitute for attachments.
- Policy: ChatgptREST does **not** allow clients to force Gemini's "Thinking" mode. Requests for `thinking` / `pro_thinking` are normalized to `preset=pro`.
- Important: Gemini does **not** currently expose a true non-Pro `auto` tier on the low-level web lane. `preset=auto` is an alias to `preset=pro`, not a low-cost/non-Pro execution mode.
- Pro safety guardrail: `preset=pro` + `purpose=smoke/test/...` returns HTTP 400 `detail.error="pro_smoke_test_blocked"` with no request-level override.
- `preset=deep_think` depends on the Gemini account/UI capability (Ultra + feature rollout); if it fails, use `preset=pro` as fallback.
- For compatibility, `preset` also accepts ChatGPT-style values (`pro_extended`, `thinking_extended`, `thinking_heavy`) and treats them as `pro`.
- Gemini answer quality guard (default enabled): ChatgptREST may sanitize leading Gemini UI transcript noise before finalizing the answer, and exposes details in `meta.answer_quality_guard`.
- Optional strict semantic gate: if `CHATGPTREST_GEMINI_SEMANTIC_CONSISTENCY_GUARD=1`, detected mixed `next_owner` semantics can be downgraded to `needs_followup` for explicit normalization.

For `kind=qwen_web.ask` (Qwen web automation):

`input`:
- `question: string` (required)
- `conversation_url: string | null` (optional follow-up; Qwen thread URL like `https://www.qianwen.com/chat/<32hex>`)
- `parent_job_id: string | null` (optional follow-up; server will reuse the parent job's `conversation_url`)

`params`:
- `preset: string` (required; supported: `auto`, `deep_thinking`, `deep_research`; aliases: `default`/`defaults` → `auto`, `thinking` → `deep_thinking`, `research` → `deep_research`)
- `deep_research: bool` (optional; when `preset=auto`, `true` maps to `deep_research`, otherwise default `deep_thinking`)
- `timeout_seconds: int` (legacy; used for both send+wait timeouts when split fields are omitted)
- `send_timeout_seconds: int` (optional; tool timeout for the initial send/ask stage)
- `wait_timeout_seconds: int` (optional; per-call timeout for wait polling)
- `max_wait_seconds: int` (best-effort; controls server-side waiting behavior)
- `min_chars: int` (best-effort; used for wait heuristics)
- `allow_queue: bool` (default `false`; same semantics as `chatgpt_web.ask`)
- `answer_format: string` (`markdown` or `text`; default `markdown`)

Notes:
- Recommended deployment is a **dedicated Qwen CDP Chrome** (`QWEN_CDP_URL`, default `http://127.0.0.1:9335`) without proxy.
- `preset=deep_research` may hit Qwen daily quota limits; when quota is exhausted, the job can return `status=cooldown`.
- Server-side send throttling for Qwen is controlled by `CHATGPTREST_QWEN_MIN_PROMPT_INTERVAL_SECONDS` (default `0`).
- Conversation single-flight and cross-provider `conversation_url`/`parent_job_id` validation apply to Qwen just like ChatGPT/Gemini.

For `kind=gemini_web.generate_image` (Gemini web UI image generation):

`input`:
- `prompt: string` (required)
- `conversation_url: string | null` (optional; Gemini web URL; continue in an existing thread)
- `file_paths: string[] | null` (optional; server-local paths; reference images; see Notes)

`params`:
- `timeout_seconds: int` (default `600`)
- `drive_name_fallback: bool` (default `false`; when true and a Drive URL can’t be resolved, driver falls back to picker filename search instead of `cooldown`)

Output:
- Images are copied into `artifacts/jobs/<job_id>/images/` and referenced from the job answer Markdown.
- The driver may also return its own `images[].path`; ChatgptREST attaches stable `job_images[]` paths under the job artifacts.

Notes:
- When `input.file_paths` is provided, ChatgptREST uses the same Drive-attach pipeline as `gemini_web.ask`:
  - Upload each local path into Drive via `rclone copyto` then resolve a Drive URL via `rclone lsjson`.
  - Attach via Gemini UI: `+` → `从云端硬盘添加` → paste URL → `插入`.
  - Default is fail-closed: if Drive URL resolution fails, job returns `status=cooldown` (`reason_type=DriveUploadNotReady`).

Idempotency rules:
- Same `Idempotency-Key` + same request payload (`kind/input/params`) -> returns the **same** `job_id` (HTTP 200).
- Same `Idempotency-Key` + different payload -> HTTP 409 with `detail.error="idempotency_collision"` (includes `existing_job_id` + `existing_request_hash` + `request_hash`).

For `kind=repair.check` (diagnostics / repair daemon, no prompt send):

`input`:
- `job_id: string | null` (optional; target job to inspect)
- `symptom: string | null` (optional; client-reported issue, e.g. “cloudflare”, “409 idempotency”, “driver down”)
- `conversation_url: string | null` (optional; used only for best-effort `chatgpt_web_self_check` in `mode=full`)

`params`:
- `mode: string` (`quick` or `full`; default `quick`)
- `timeout_seconds: int` (default `60`; caps diagnostic probes)
- `probe_driver: bool` (default `true`; calls driver tools like `chatgpt_web_blocked_status`/`tab_stats`)
- `capture_ui: bool` (default `false`; when `mode=full`, best-effort `chatgpt_web_capture_ui(mode=basic)`; no prompt send)
- `recent_failures: int` (default `5`; include N recent `error/blocked/cooldown/needs_followup` jobs from DB)

Output:
- Answer is stored as `artifacts/jobs/<job_id>/answer.md` and can be fetched via `/v1/jobs/<job_id>/answer`.
- A machine-readable report is written to `artifacts/jobs/<job_id>/repair_report.json`.

For `kind=repair.autofix` (Codex-driven autofix, no prompt send):

`input`:
- `job_id: string` (required; target job to help recover)
- `symptom: string | null` (optional; hint for Codex)
- `conversation_url: string | null` (optional; if present, enables ChatGPT UI actions like `refresh/regenerate` without re-sending prompts)

`params`:
- `timeout_seconds: int` (default `600`; caps Codex + actions)
- `model: string | null` (optional Codex model override)
- `max_risk: string` (`low|medium|high`; default `low`)
- `allow_actions: string | string[] | null` (optional allowlist; default env `CHATGPTREST_CODEX_AUTOFIX_ALLOW_ACTIONS`)
- `apply_actions: bool` (default `true`; when false, runs Codex analysis but skips executing actions)

Output:
- Answer is stored as `artifacts/jobs/<job_id>/answer.md`.
- Report is stored as `artifacts/jobs/<job_id>/repair_autofix_report.json`.
- Codex artifacts are stored under `artifacts/jobs/<job_id>/codex/` (e.g. `prompt.txt`, `sre_actions.json`).
- `repair_autofix_report.json` may include `codex_fallback` + `fallback.reason=codex_maint_agent_fallback` when the primary Codex run fails and secondary fallback planning is used.
- `repair_autofix_report.json` also records `execution_path` and `codex_profile`.

Notes:
- `repair.autofix` now has a deterministic runtime-recovery fast path ahead of Codex. For known infra/UI signatures (for example CDP/browser disconnects, blocked runtime state, wait-stage stalls, and Gemini region mismatch), executor may plan the guarded action list directly and skip Codex prompt generation entirely.
- The fast path is enabled by default and controlled by `CHATGPTREST_CODEX_AUTOFIX_ENABLE_HEURISTIC_FAST_PATH` (default `true`).
- Default cheap-tier profile remains intentional: primary planning uses `gpt-5.3-codex-spark` with low reasoning, and optional secondary fallback planning stays on the same model with minimal reasoning.
- Secondary Codex fallback planning is now **opt-in** and controlled by `CHATGPTREST_CODEX_AUTOFIX_ENABLE_MAINT_FALLBACK` (default `false`). Clients must not assume `codex_fallback` will be present on every failed primary Codex run.
- Prompt assembly for `repair.autofix` is intentionally bounded and may summarize large evidence fields (`events_tail`, target-job errors, maint memory, `AGENTS.md`) before writing `artifacts/jobs/<job_id>/codex/prompt.txt`. This does not change the external REST schema; it changes only the default internal execution budget.

For `kind=repair.open_pr` (Codex-driven patch proposal; optional apply/commit/push/PR):

`input`:
- `job_id: string` (required; target job to fix / provide evidence context)
- `symptom: string | null` (optional; hint for Codex)
- `instructions: string | null` (optional; additional constraints, e.g. “only touch chatgpt_web_mcp/server.py”)

`params`:
- `mode: string` (`p0|p1|p2`; default `p0`)
  - `p0`: propose patch only (no git changes)
  - `p1`: apply patch in a git worktree + run tests + commit (no push/PR)
  - `p2`: apply + tests + commit + push + open PR (requires git/gh auth on the host)
- `timeout_seconds: int` (default `900`; caps Codex + tests)
- `model: string | null` (optional Codex model override)
- `reasoning_effort: string | null` (optional Codex reasoning override)
- `remote: string` (default `origin`)
- `base_ref: string` (default `HEAD`; git ref for worktree base)
- `base_branch: string` (default `master`; PR base branch when creating PR)
- `run_tests: bool | null` (optional; overrides default-by-mode)
- `push: bool | null` (optional; overrides default-by-mode)
- `create_pr: bool | null` (optional; overrides default-by-mode)

Output:
- Answer is stored as `artifacts/jobs/<job_id>/answer.md`.
- Report is stored as `artifacts/jobs/<job_id>/repair_open_pr_report.json`.
- Codex artifacts are stored under `artifacts/jobs/<job_id>/codex_pr/` (e.g. `prompt.txt`, `codex_patch.json`, `patch.diff`).

Notes:
- Prompt assembly for `repair.open_pr` is also budgeted by default and may summarize large debug artifacts or `AGENTS.md` excerpts before writing `artifacts/jobs/<job_id>/codex_pr/prompt.txt`.
- When `params.model` is omitted, `repair.open_pr` uses mode-based defaults instead of ambient model selection:
  - `p0 -> gpt-5.3-codex-spark + low`
  - `p1 -> gpt-5.3-codex + medium`
  - `p2 -> gpt-5.3-codex + high`
- `repair_open_pr_report.json` records `codex_profile`.

For `kind=sre.fix_request` (incident-scoped repair coordinator with lane memory):

`input`:
- `issue_id: string | null` (optional; link to Issue Ledger and reuse issue evidence)
- `incident_id: string | null` (optional; alternate lane anchor when no Issue Ledger id exists yet)
- `job_id: string | null` (optional; target job to inspect / route into `repair.autofix` or `repair.open_pr`)
- `symptom: string | null` (optional; client-reported symptom or failure summary)
- `instructions: string | null` (optional; requester guidance for downstream patch/fix routing)
- `lane_id: string | null` (optional; explicit lane name; otherwise derived from issue/job/symptom)
- `context: object | string | null` (optional; extra structured context stored with the lane request)

`params`:
- `timeout_seconds: int` (default `600`; caps the Codex diagnosis step)
- `model: string | null` (optional Codex model override)
- `resume_lane: bool` (default `true`; reuse the most recent Codex session in the same lane when one exists)
- `route_mode: string` (`plan_only|auto_runtime|auto_best_effort`; default `auto_best_effort`)
  - `plan_only`: diagnose only, do not create downstream jobs
  - `auto_runtime`: may auto-submit `repair.autofix`, but never `repair.open_pr`
  - `auto_best_effort`: may auto-submit `repair.autofix` or `repair.open_pr`
- `runtime_apply_actions: bool` (default `true`; passed through when routing to `repair.autofix`)
- `runtime_max_risk: string` (`low|medium|high`; default `low`)
- `runtime_allow_actions: string | string[] | null` (optional explicit allowlist override for runtime fixes)
- `open_pr_mode: string` (`p0|p1|p2`; default `p0`; used when routing to `repair.open_pr`)
- `open_pr_run_tests: bool | null` (optional; forwarded to `repair.open_pr`)
- `gitnexus_limit: int` (default `5`; max code-graph snippets to request when GitNexus CLI is enabled)

Output:
- Answer is stored as `artifacts/jobs/<job_id>/answer.md`.
- Report is stored as `artifacts/jobs/<job_id>/sre_fix_report.json`.
- Lane state is stored under `state/sre_lanes/<lane_id>/` (request history, prompt, decision, manifest).
- `request.json` / `sre_fix_report.json` now include `prompt_stats` with:
  - `prompt_chars`
  - `estimated_tokens` (lightweight chars/4 estimate for observability)
  - `sections[]` (`title`, `chars`)
- If `issue_id` is provided, the report is linked back into Issue Ledger via `issue_evidence_linked`.
- `route_mode=auto_*` may create downstream `repair.autofix` or `repair.open_pr` jobs; those job ids are included in the answer/report metadata.

Notes:
- Large `context_pack`, target job artifacts, and maint memory are compacted for the Codex prompt path; the stored request/report remains authoritative, while the prompt is allowed to be a smaller derived view for token control.
- When `params.model` is omitted, `sre.fix_request` now defaults to `gpt-5.3-codex-spark` instead of ambient model selection.
- Resume/default SRE diagnosis uses low reasoning; fresh diagnosis uses medium reasoning by default.
- If Codex diagnosis still fails after heuristic routing has already missed, SRE fails open to a structured `manual` decision and records the Codex error in `sre_fix_report.json -> codex`, instead of failing the whole controller job by default.

Alias:
- `kind=sre.diagnose` is accepted as a compatibility alias and uses the same executor.

### `POST /v1/advisor/advise` (advisor wrapper v1)

Run the advisor role as a first-class API entry (plan-only or execute mode).

Body:
- `raw_question: string` (required)
- `context: object` (optional; default `{}`)
- `force: bool` (optional; default `false`)
- `execute: bool` (optional; default `false`)
- `mode: string` (optional; `fast|balanced|strict`, default `balanced`)
- `orchestrate: bool` (optional; default `false`)
- `quality_threshold: int` (optional; default by mode: `fast=14`, `balanced=17`, `strict=20`)
- `crosscheck: bool` (optional; default `false`)
- `max_retries: int` (optional; `0..20`, default `0`)
- `agent_options: object` (optional; default `{}`)
  - Supported keys mirror `ops/chatgpt_wrapper_v1.py` / `ChatGPTAgentV0` constructor options (e.g. `session_id`, `preset`, timeouts, client trace fields).
  - OpenClaw orchestration options (optional): `openclaw_mcp_url`, `openclaw_agent_id`, `openclaw_model`, `openclaw_thinking`, `openclaw_session_key`, `openclaw_timeout_seconds`, `openclaw_session_timeout_seconds`, `openclaw_required`, `openclaw_cleanup`, `openclaw_allow_a2a`.
  - Security constraint: `base_url` / `api_token` / `state_root` are server-fixed and **forbidden** in `agent_options`; API returns HTTP 400 `detail.error="forbidden_agent_options"` if provided.
  - Unknown keys return HTTP 400 `detail.error="unknown_agent_options"`.

Behavior:
- `execute=false`: returns advisor planning output (`route/refined_question/followups/answer_contract`), no downstream ask job is submitted.
- `execute=true`: advisor runs plan first, then submits one downstream ask job and **returns immediately** (does not long-wait in this API call).
- `execute=true && orchestrate=true`: submits `kind=advisor.orchestrate` parent job (control-plane job) and returns immediately with `run_id` + `orchestrate_job_id`.
- When `execute=true`, write-operation gates apply:
  - client allowlist gate (`CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST`), and
  - trace-header gate (`CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE`).

Response:
- Returns advisor result object including planning fields:
  - `ok`, `status`, `route`, `route_decision`, `refined_question`, `followups`, `answer_contract`, `action_hint`
  - `mode`, `orchestrate`, `quality_threshold`, `crosscheck`, `max_retries`
  - optional: `assumptions`
- For `execute=true`, `status` is one of:
  - `job_created`: accepted and queued/in-progress (`job_id`, `phase`, `job_status`)
  - `cooldown`: accepted but delayed (`job_id`, `retry_after_seconds`, `reason`)
  - reject via HTTP error (allowlist / trace headers / invalid options / conversation_busy)
- For `execute=true && orchestrate=true`:
  - response includes `run_id`, `orchestrate_job_id` (same as `job_id`), `provider=advisor_orchestrate`.

### `GET /v1/advisor/runs/{run_id}`

Read advisor orchestrate run state (run header + steps).

Response fields (subset):
- `run_id`, `request_id`, `mode`, `status`, `route`
- `raw_question`, `normalized_question`, `context`
- `quality_threshold`, `crosscheck`, `max_retries`
- `orchestrate_job_id`, `final_job_id`, `degraded`, `error_type`, `error`
- `created_at`, `updated_at`, `ended_at`
- `steps[]` (`step_id`, `step_type`, `status`, `attempt`, `job_id`, lease fields, input/output, evidence_path)

### `GET /v1/advisor/runs/{run_id}/events?after_id=&limit=`

Advisor run event stream (event-sourcing timeline).

Returns:
- `ok`, `run_id`, `after_id`, `next_after_id`
- `events[]` with `id`, `run_id`, `step_id`, `ts`, `type`, `payload`
- Event payloads include a normalized envelope: `run_id`, `step_id`, `attempt`, `agent_id`, `session_key`, `correlation_id`, `idempotency_key`, `event_ts`, `evidence_path`.

### `GET /v1/advisor/runs/{run_id}/replay?persist=`

Rebuild run snapshot from `advisor_events` (event sourcing replay).

- `persist=false` (default): returns replay snapshot without mutating DB state.
- `persist=true`: applies replay result to run/step snapshots and writes `artifacts/advisor_runs/<run_id>/snapshot.json`.

Response fields:
- `ok`, `run_id`, `persisted`, `snapshot_path`
- `run`, `steps`, `replay` (reconstructed run status + step states)

### `POST /v1/advisor/runs/{run_id}/takeover`

Manual takeover + compensation entrypoint for degraded runs.

Body:
- `note: string` (optional)
- `actor: string` (optional; default `manual`)
- `compensation: object` (optional; custom handoff payload)

Behavior:
- Upserts step `manual_takeover` with `status=COMPENSATED`
- Emits `step.compensated` and `run.taken_over`
- Sets run status to `MANUAL_TAKEOVER` and writes `takeover.json` + `snapshot.json`

### `GET /v1/advisor/runs/{run_id}/artifacts`

List run-level artifacts under `artifacts/advisor_runs/<run_id>/` and linked child-job artifact paths.

### `GET /v1/jobs/{job_id}` (status)

- 404 if `job_id` does not exist.
- Returns a `JobView`.

`JobView` fields (subset):
- `job_id, status, created_at, updated_at`
- `kind` (job kind; e.g. `chatgpt_web.ask`)
- `parent_job_id` (optional; when enqueued as a follow-up)
- `phase` (`send` or `wait`; indicates which worker stage will handle the job next)
- `conversation_url` (when present; used for follow-up jobs)
- `conversation_export_path` (best-effort; saved conversation JSON under `ARTIFACTS_DIR`)
- `not_before` and `retry_after_seconds` (when waiting)
- `attempts` / `max_attempts` (send-phase retry counter / cap; may auto-extend for retryable infra issues)
- `queue_position` and `estimated_wait_seconds` (best-effort send-queue estimate for `chatgpt_web.ask` / `gemini_web.ask` / `qwen_web.ask`)
- `min_prompt_interval_seconds` (current server config; best-effort)
- `action_hint` (client guidance, e.g. `fetch_answer` / `retry_after_cooldown` / `wait_or_poll_send_queue`)
- `cancel_requested_at` (when cancel has been requested)
- `path` and `preview` (when answer exists)
- `reason_type`/`reason` (for `blocked/cooldown/needs_followup/error/canceled`)
- `error` (only when `status=error`)
- `completion_contract` (best-effort canonical completion block; present on modern jobs and additive for old jobs when enough state can be derived)

`completion_contract` fields:
- `kind`
- `answer_state: partial | provisional | final`
- `finality_reason`
- `answer_chars`
- `min_chars_required`
- `authoritative_answer_path`
- `answer_provenance`
- `export_available`
- `widget_export_available`

`canonical_answer` fields (additive hardening for modern jobs):
- `record_version`
- `ready`
- `answer_state`
- `finality_reason`
- `authoritative_answer_path`
- `answer_chars`
- `answer_format`
- `answer_provenance`
- `export_available`
- `widget_export_available`

Readiness rules:
- `GET /v1/jobs/{job_id}/answer` is gated by `canonical_answer.ready`, not by `status=completed` alone.
- `canonical_answer.ready=true` requires a final `completion_contract` and an `authoritative_answer_path` under `ARTIFACTS_DIR`.
- Short completed web answers can still be final when the content classifier confirms a real answer; truly suspicious short answers remain `answer_state=provisional` and `/answer` returns 409.
- `rescue_followup_shortcircuited` is a semantic finality event: the follow-up job's authoritative answer is the copied parent answer artifact, so it should not be re-blocked solely because the copied answer is concise.
- `completion_contract_recorded` is a semantic finality event for public job projection. If it records `answer_state=final`, later status/result views must not let an older `completion_guard_downgraded` diagnostic event downgrade the same completed job back to provisional.

Research-task contract:
- For `deep_research=true` or research/report-style jobs, callers should treat `completion_contract` as the authoritative completion view.
- `status=completed` is only a trustworthy research finalization signal when `completion_contract.answer_state=final`.
- Stalled or under-min-chars research jobs no longer finalize as “good enough completed”; they remain `in_progress` or transition to `needs_followup` with a non-final `completion_contract`.
- `conversation_export` / widget export / answer rehydrate are observations that feed the completion contract; they are not by themselves the canonical finality signal.
- `canonical_answer` is the explicit answer/deliverable view derived from `completion_contract` plus the currently authoritative answer artifact. It is additive to `completion_contract`, not a replacement for `status`.
- Consumer rule:
  - P0 clients should read `completion_contract.answer_state`, `completion_contract.authoritative_answer_path`, and `completion_contract.answer_provenance`.
  - Monitoring / issue / soak / evidence consumers should prefer `canonical_answer.ready`, `canonical_answer.authoritative_answer_path`, and `canonical_answer.answer_provenance` when deciding whether a research answer is ready to consume.
  - Do not infer research finality directly from `status == completed`, `answer.md`, or `conversation_export_path`.

### `GET /health/runtime-contract`

Machine-readable runtime contract health for the public MCP / low-level runtime boundary.

Returns:

- `service_identity`
- `allowlist_enforced`
- `allowlisted`
- `runtime_contract_ok`
- `completion_contract_version`
- `mcp_surface_version`
- plus supporting diagnostics such as `token_present`, `auth_source`, `base_url`, `mcp_host`, `mcp_port`

### `GET /v1/health/runtime-contract`

Alias of `GET /health/runtime-contract`.

### `GET /v1/jobs/{job_id}/result` (alias)

Same as `GET /v1/jobs/{job_id}`.

### `POST /v1/jobs/{job_id}/cancel`

- Recommended headers: `X-Cancel-Reason`, `X-Client-Name`, `X-Client-Instance`, `X-Request-ID`.
- Optional server gate: if `CHATGPTREST_REQUIRE_CANCEL_REASON=1`, cancellation must include `X-Cancel-Reason` (or `?reason=`) or API returns HTTP 400 `detail.error="missing_cancel_reason"`.
- Optional public MCP gate: if `CHATGPTREST_REQUIRE_EXPLICIT_MCP_CANCEL_REASON=1`, `automation_job_cancel` / `chatgptrest_job_cancel` must be called with an explicit `reason`; the MCP tool fails closed before sending HTTP `/cancel` if the argument is missing.
- 404 if `job_id` does not exist.
- If `queued`, transitions directly to `canceled`.
- If `in_progress`, sets `cancel_requested_at` and the worker should transition to `canceled` as soon as possible.
- If already terminal, returns current state.
- Cancel attribution: the `cancel_requested` job event includes a `payload.by` object (HTTP client host/port + a safe subset of headers like `User-Agent`, `X-Client-Name`, `X-Client-Instance`, `X-Request-Id`, `X-Cancel-Reason`, plus server metadata like `hostname/pid/received_at`) to help identify who issued the cancel.

### `GET /v1/jobs/{job_id}/wait?timeout_seconds=&poll_seconds=&auto_wait_cooldown=` (long poll)

Wait for a job to reach a "done-ish" status, then return a `JobView`:
- terminal: `completed/error/canceled`
- retryable: `blocked/cooldown/needs_followup`

If the timeout elapses, returns the current `JobView` (may still be `queued/in_progress`).

Optional behavior:
- If `auto_wait_cooldown=1`, the endpoint keeps waiting through `status=cooldown` (sleeping until `not_before`) until it becomes terminal or the timeout elapses.

Research-task client rule:
- For `deep_research` / `report_grade` / long-form research asks, `wait` callers should inspect `completion_contract.answer_state` rather than treating every `completed` as final by default.
- `answer_state=provisional` means the system recovered or materialized some answer signal, but the research completion contract still considers the run non-final.

## Client Issue Ledger (v1 additive)

Purpose:
- Track client-project incidents in a deduplicated ledger (fingerprint-based merge).
- Replace manual issue markdown logging with queryable records + event timeline.

Issue status:
- `open`
- `in_progress`
- `mitigated`
- `closed`

Severity:
- `P0|P1|P2|P3` (default `P2`)

### `POST /v1/issues/report`

Report or merge an issue.

Body:
- `project: string` (required)
- `title: string` (required)
- `severity: string | null` (optional; `P0..P3`)
- `kind: string | null` (optional; e.g. `chatgpt_web.ask`)
- `symptom: string | null`
- `raw_error: string | null`
- `job_id: string | null`
- `conversation_url: string | null`
- `artifacts_path: string | null`
- `source: string | null` (report source, e.g. `codex`, `client_mcp`)
- `fingerprint: string | null` (optional explicit dedupe key; otherwise server computes one from core fields)
- `tags: string[]` (optional)
- `metadata: object | null` (optional)
  - 默认开启已完成作业保护：当引用的作业（`job_id`，或 `metadata.job_ids`）都已 `completed` 且存在 `answer_path` 且无错误时，接口返回 `409 IssueReportJobAlreadyCompleted`，避免误报 open issue。
  - 如确需对已完成作业做复盘登记（postmortem），可在 `metadata` 里传 `allow_resolved_job=true`（或 `force=true`）。
  - 若未显式传 `job_id` 但传了 `metadata.job_ids`，服务端会把最后一个 `job_ids` 作为该 issue 的 `latest_job_id` 便于追踪。

Response:
- `ClientIssueReportView` (includes `created: bool`, `reopened: bool`).
- If an active issue with the same fingerprint exists, server merges and increments `count`.
- If a matched issue is `mitigated`, new report reopens it to `open`.
- Closed issues are not merged (a new issue row is created).

### `GET /v1/issues?project=&kind=&source=&status=&severity=&fingerprint_hash=&fingerprint_text=&since_ts=&until_ts=&before_ts=&before_issue_id=&limit=`

List issues with filters and cursor pagination.

Filters:
- `project` exact match (case-insensitive)
- `kind` exact match (case-insensitive)
- `source` exact match (case-insensitive)
- `status` comma-separated (`open,in_progress,...`)
- `severity` (`P0..P3`)
- `fingerprint_hash` exact match (sha256 string)
- `fingerprint_text` case-insensitive contains match
- `since_ts` / `until_ts` (filter by `updated_at` time window, inclusive)

Pagination:
- `before_ts` + `before_issue_id` for stable cursor pagination by `(updated_at DESC, issue_id DESC)`.

Returns:
- `issues[]`
- `next_before_ts`
- `next_before_issue_id`

### `GET /v1/issues/{issue_id}`

Fetch one issue by id.

### `POST /v1/issues/{issue_id}/status`

Update issue status.

Body:
- `status: open|in_progress|mitigated|closed` (required)
- `note: string | null`
- `actor: string | null`
- `linked_job_id: string | null`
- `metadata: object | null`

Effect:
- Updates issue status and appends `issue_status_updated` event.
- When `status=mitigated`, server can persist a structured verification record:
  - `metadata.verification_type`
  - `metadata.verification` object (`type/status/verifier/job_id/conversation_url/artifacts_path/metadata`)
- When `status=closed`, server can persist structured qualifying usage evidence:
  - `metadata.qualifying_success_job_ids`
  - `metadata.qualifying_successes[]`

### `POST /v1/issues/{issue_id}/evidence`

Link new evidence to issue and update latest pointers.

Body:
- `job_id: string | null`
- `conversation_url: string | null`
- `artifacts_path: string | null`
- `note: string | null`
- `source: string | null`
- `metadata: object | null`

Effect:
- Updates `latest_*` fields and appends `issue_evidence_linked` event.

### `POST /v1/issues/{issue_id}/verification`

Record a structured verification object for an issue.

Body:
- `verification_type: string` (required; e.g. `live`, `regression`, `quiet_window`)
- `status: string` (default `passed`)
- `verifier: string | null`
- `note: string | null`
- `job_id: string | null`
- `conversation_url: string | null`
- `artifacts_path: string | null`
- `metadata: object | null`

Behavior:
- Persists a row in `client_issue_verifications`
- Appends `issue_verification_recorded` event

### `GET /v1/issues/{issue_id}/verification?after_ts=&limit=`

List structured verification records for an issue.

Response:
- `issue_id`
- `verifications[]`

### `POST /v1/issues/{issue_id}/usage`

Record one qualifying client-success usage record for an issue.

Body:
- `job_id: string` (required)
- `client_name: string | null`
- `kind: string | null`
- `status: string` (default `completed`)
- `answer_chars: int | null`
- `metadata: object | null`

Behavior:
- Persists a row in `client_issue_usage_evidence`
- Appends `issue_usage_evidence_recorded` event
- Duplicate `(issue_id, job_id)` is deduped

### `GET /v1/issues/{issue_id}/usage?after_ts=&limit=`

List structured usage evidence rows for an issue.

Response:
- `issue_id`
- `usage[]`

### `GET /v1/issues/{issue_id}/events?after_id=&limit=`

Cursor-based issue event feed.

### `POST /v1/issues/graph/query`

Query the derived issue knowledge graph.

Body:
- `issue_id: string | null`
- `family_id: string | null`
- `q: string | null`
- `status: string | null`
- `include_closed: bool` (default `true`)
- `limit: int` (default `20`)
- `neighbor_depth: int` (default `1`)

Response:
- `generated_at`
- `summary`
- `matches[]` (matched issue records)
- `nodes[]`
- `edges[]`

Notes:
- The graph is a **derived projection** from the authoritative ledger and evidence tables.
- It does not own issue state.

### `GET /v1/issues/graph/snapshot?include_closed=&limit=`

Fetch the full derived issue graph snapshot currently visible to the API process.

### Health

- `GET /healthz` (canonical)
- `GET /health` (alias)
- `GET /v1/health` (alias)

These endpoints perform a lightweight DB connectivity check and return HTTP 503 when the DB is unavailable.

## Ops (v3 additive; for automation/monitoring)

These endpoints are additive and intended for “full auto closed-loop” observability and control.

Auth:
- If `CHATGPTREST_OPS_TOKEN` (or `CHATGPTREST_ADMIN_TOKEN`) is set, `/v1/ops/*` requires `Authorization: Bearer <ops_token>`.
- Otherwise, `/v1/ops/*` uses the same auth policy as the rest of the API (i.e. `CHATGPTREST_API_TOKEN` when configured).

### `GET /v1/ops/pause`

Returns the current global pause/drain state (stored in DB meta; enforced at worker claim time):

- `mode`: `none|send|all`
- `until_ts`: unix timestamp (float)
- `active`: bool
- `seconds_remaining`: best-effort
- `reason`: optional human-readable reason (truncated)

### `POST /v1/ops/pause`

Set or clear pause state.

Body:
- `mode: none|send|all`
- One of:
  - `until_ts: float` (unix ts; must be in the future), or
  - `duration_seconds: int` (adds to server-side `now`)
- `reason: string | null` (optional; truncated)

### `GET /v1/ops/status`

Compact ops summary for clients/monitors:
- `pause` (same shape as `/v1/ops/pause`)
- `jobs_by_status` (counts from DB)
- `active_incidents` (count where `status != resolved`)
- `active_incident_families` (distinct unresolved incident fingerprints)
- `active_open_issues` (count where issue status is `open|in_progress`)
- `active_issue_families` (distinct active issue families; explicit `family_id` or fingerprint fallback)
- `stuck_wait_jobs` (best-effort count of `phase=wait,status=in_progress` jobs older than the configured threshold)
- `ui_canary_ok` / `ui_canary_failed_providers` (best-effort read from `artifacts/monitor/ui_canary/latest.json`)
- `attention_reasons` (derived top-level health hints such as `active_incidents`, `active_open_issues`, `stuck_wait_jobs`, `ui_canary_failed`)
- `last_job_event_id` (best-effort)

### `GET /v1/ops/incidents?status=&severity=&before_ts=&before_incident_id=&limit=`

List incidents from DB (v3 incident tables).

Filters:
- `status=active` (special): returns all incidents where `status != resolved`
- `status=<comma-separated statuses>`: exact match on `LOWER(status)`
- `severity=P0|P1|P2`
- Pagination cursor:
  - legacy: `before_ts` paginates by `updated_at < before_ts`
  - stable: `before_ts` + `before_incident_id` paginates by `(updated_at < before_ts) OR (updated_at = before_ts AND incident_id < before_incident_id)`

Returns:
- `incidents[]` (see `IncidentView` in `chatgptrest/api/schemas.py`)
- `next_before_ts`: legacy cursor for pagination (best-effort)
- `next_before_incident_id`: tie-breaker cursor (best-effort)

### `GET /v1/ops/incidents/{incident_id}`

Fetch one incident by id.

### `GET /v1/ops/incidents/{incident_id}/actions?limit=`

List remediation actions for a given incident (`remediation_actions` table).

### `GET /v1/ops/events?after_id=&limit=`

Global job event feed (cursor-based; `job_events` table).

### `GET /v1/ops/jobs?status=&kind_prefix=&phase=&before_ts=&before_job_id=&limit=`

List recent jobs (summary view; does not read artifact previews).

Pagination:
- legacy: `before_ts` paginates by `created_at < before_ts`
- stable: `before_ts` + `before_job_id` paginates by `(created_at < before_ts) OR (created_at = before_ts AND job_id < before_job_id)`

Returns:
- `jobs[]` (summary objects)
- `next_before_ts` (best-effort)
- `next_before_job_id` (best-effort)

### `GET /v1/ops/idempotency/{idempotency_key}`

Lookup the idempotency record:
- `idempotency_key`
- `request_hash`
- `job_id`
- `created_at`

### Transient assistant errors (duplication prevention)

Some short assistant-side error strings (e.g. `"Error in message stream"`) can happen **after the prompt was already sent**.

ChatgptREST treats these as transient: it will best-effort `wait` in the same conversation instead of finalizing the job as `completed`.
If it still cannot obtain a real answer within `max_wait_seconds`, it returns a retryable `cooldown` state with:
- `reason_type=TransientAssistantError`
- `retry_after_seconds` (best-effort)

Client guidance: do **not** create a new job to "retry" (which would send a second user message). Prefer polling `/wait`, then read the answer via `/answer`.

### `GET /v1/jobs/{job_id}/events?after_id=&limit=` (job event log)

Return a slice of DB-backed job events (`job_events` table) after a given `after_id` (inclusive window is `id > after_id`).

### `GET /v1/jobs/{job_id}/answer?offset=&max_chars=` (chunked answer)

This endpoint exists to keep long answers out of tool/client message channels.

Semantics:
- `offset` and `max_chars` are **byte offsets / byte limits** into the UTF-8 encoded answer artifact.
- Server may adjust `offset` forward to the next valid UTF-8 boundary; the returned `offset` reflects the actual start.

Responses:
- 404 if `job_id` does not exist.
- 409 if the canonical answer is not readable yet (e.g. `status != completed`, non-final `completion_contract.answer_state`, missing `authoritative_answer_path`, or `canonical_answer.ready=false`), with `detail.status`, `detail.answer_state`, `detail.canonical_ready`, and optional `detail.retry_after_seconds`.
- 200 with `AnswerChunk` if readable.
- 503 if `status=completed` but the answer artifact file is missing (artifact consistency issue).

### `GET /v1/jobs/{job_id}/conversation?offset=&max_chars=` (chunked conversation export)

This endpoint exists to keep long conversation exports out of tool/client message channels.

Semantics:
- `offset` and `max_chars` are **byte offsets / byte limits** into the UTF-8 encoded conversation export artifact.
- The server may adjust `offset` forward to the next valid UTF-8 boundary; the returned `offset` reflects the actual start.

Responses:
- 404 if `job_id` does not exist.
- 409 if the conversation export is not readable yet (missing `conversation_export_path`), with `detail.status` and optional `detail.retry_after_seconds`.
- 200 with a `ConversationChunk` if readable.
- 503 if the conversation export artifact file is missing (artifact consistency issue).

### `GET /healthz`

Returns `{ "ok": true, "status": "ok" }`.

## Retired Advisor / Agent Control Plane

The historical advisor/planning control plane (`/v1/advisor/*`, `/v2/advisor/*`, `/v3/agent/*`) is retired.

Current contract:
- For coding agents (Codex / Claude Code / Antigravity), the supported default integration path is the public MCP surface at `http://127.0.0.1:18712/mcp`, using the `automation_*` tool family.
- ChatgptREST remains a shared execution backend: automation-kernel, job queue, worker lifecycle, result retrieval, and observability.
- Do not integrate new clients against `/v3/agent/*` or advisor-style MCP tool names.
- If maintenance tooling must call low-level `/v1/jobs`, keep that path behind an explicit maintenance identity and separate docs.

Historical documents may still mention `/v3/agent/*` for change history, but those endpoints are no longer mounted or supported as production surfaces.

## Chrome CDP Architecture & Isolation (Important for AI Agents)

ChatgptREST depends on dedicated headless Chrome instances to maintain long-running, stable LLM web sessions (handling CAPTCHAs, SSE streams, DOM mutations).

To prevent `TargetClosedError` and session interference, **external AI Coding Agents (e.g. Antigravity, Claude Code, Cursor, Codex) MUST NOT connect their browser automation MCPs (like `chrome-devtools` or `browser-use`) to the ChatgptREST driver ports**.

**Official Port Allocation:**
- `127.0.0.1:9226` : Reserved exclusively for **ChatGPT Driver**. Do not attach external tools.
- `127.0.0.1:9335` : Reserved exclusively for **Qwen Driver**. Do not attach external tools.
- `127.0.0.1:9222` : **User's primary browser** (forwarded via SSH). This is the correct target for `browser-use` and `chrome-devtools` MCP extensions.
