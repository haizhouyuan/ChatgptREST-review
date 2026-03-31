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
- Compatibility: when `preset=deep_research` is used for ChatGPT, server normalizes to `preset=thinking_heavy` and sets `params.deep_research=true` before execution.
- If `send_timeout_seconds` is omitted, the server caps the initial send/ask stage to a conservative default (currently 180s; override via `CHATGPTREST_DEFAULT_SEND_TIMEOUT_SECONDS` or by explicitly setting `params.send_timeout_seconds`).
- Deep Research note: ChatGPT Web may first ask for confirmation / clarifying questions before starting Deep Research. Optional: enable a single auto-followup (“OK…不要再反问”) via `CHATGPT_DEEP_RESEARCH_AUTO_FOLLOWUP=true` (default disabled).
- For `file_paths`:
  - Prefer **absolute paths**.
  - Relative paths are interpreted relative to the `ChatgptREST/` repo root.
  - Non-existent paths are rejected early (HTTP 400) to avoid “job created but upload fails later”.
  - `.zip` attachments are uploaded as-is. If ChatGPT routes the upload into an external connector flow stub (e.g. Adobe Acrobat), disable the Adobe Acrobat App in ChatGPT.
  - Attachment-contract preflight is now stricter about what counts as a local file reference:
    - URI-like tokens containing `://` are **not** treated as local attachments.
    - slash-delimited conceptual labels such as `episodic/semantic/procedural` are **not** treated as local attachments.
    - real local paths like `/vol1/...`, `./bundle.md`, `../notes/report_v1.md`, `C:\tmp\review.pdf` still require explicit `input.file_paths`.
- `file_paths` is part of the idempotency payload: if you reuse an `Idempotency-Key` but change path representation (absolute vs relative), you will get HTTP 409 with `detail.error="idempotency_collision"` and the existing job/hash hints.
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
    Preferred path for coding agents is `advisor_agent_turn` via the public MCP surface. `/v3/agent/turn` remains backend ingress for that surface plus internal runtime paths, not a separate default client entrypoint.
  - For coding-agent client identities (for example `codex`, `claude-code`, `antigravity`, legacy bare MCP wrappers, or `chatgptrestctl`), direct low-level
    `POST /v1/jobs kind=gemini_web.ask|qwen_web.ask` is also blocked by default with HTTP 403
    `detail.error="coding_agent_low_level_ask_blocked"` unless the caller uses an explicitly allowed maintenance/internal identity.
    Preferred path for coding agents remains the public MCP `advisor_agent_turn` surface at `http://127.0.0.1:18712/mcp`.
  - Registered automation callers on low-level ask are further gated by identity-aware intent review:
    - structured extractor / extractor-style JSON-only microtasks and sufficiency gates fail with HTTP 403 `detail.error="low_level_ask_intent_blocked"`
    - `testing_only` clients cannot create live ChatGPT ask jobs
    - gray-zone automation callers may be classified by `codex exec --output-schema` using `ops/schemas/ask_guard_decision.schema.json`; substantive review/report asks that prefer JSON output are allowed to reach this classifier instead of being hard-blocked up front
    - when the classifier returns `allow_with_limits`, ingress now enforces the limits by downgrading request fields such as `preset`, `deep_research`, and `min_chars` before the job is created
    - accepted low-level automation jobs may additionally be rejected by runtime controls such as `max_in_flight_jobs` and `dedupe_window_seconds`, which surface as `low_level_ask_client_concurrency_exceeded` or `low_level_ask_duplicate_recently_submitted`
    - `codex exec` for this classifier now prefers the repo's known wrapper install (`~/.home-codex-official/.local/bin/codex`) before generic `PATH` discovery, so low-level ask guard does not silently fall onto an unrelated PATH-level Codex binary with the wrong auth stack
    On accepted requests, normalized client identity and decision metadata are persisted in `client_json` and `params.ask_guard`.
  - `/v2/advisor/ask` now deduplicates recent equivalent requests within the configured window before controller dispatch. Matching first uses the current stable `request_fingerprint`; if the existing row predates fingerprint hashing, the server falls back to exact `question + intent_hint + session_id + user_id + role_id` matching so legacy advisor asks do not open a fresh ChatGPT conversation just because the fingerprint format changed.
  - Public advisor-agent MCP surface:
    - `advisor_agent_turn.attachments` accepts either a single string path or `list[string]`; the public MCP normalizes to `attachments[]` before posting to `/v3/agent/turn`.
    - Streamable-HTTP MCP clients are expected to perform `initialize` (and best-effort `notifications/initialized`) before `tools/call`; the repo validation harness and shared `chatgptrest_call.py` wrapper both follow this handshake now.
    - Public MCP is sessionful by default. Successful `initialize` returns an `mcp-session-id` response header, and subsequent `tools/call` requests should send that header back. `CHATGPTREST_AGENT_MCP_STATELESS_HTTP=1` is an explicit compatibility override, not the default.
    - For long-running goals, requested `delivery_mode=sync` may be downgraded to deferred/background. The public MCP now returns explicit handoff fields such as `accepted_for_background`, `why_sync_was_not_possible`, `recommended_client_action`, and `wait_tool=advisor_agent_wait`.
    - Public MCP now exposes `advisor_agent_wait(session_id, timeout_seconds)` so coding agents do not need to hand-roll polling loops around `advisor_agent_status`.
    - `task_intake.context` from the public MCP is merged into the live agent context before routing/prompt synthesis. This is how wrapper-carried fields such as `legacy_provider`, `github_repo`, `enable_import_code`, and `drive_name_fallback` reach the service-side router.
    - Public MCP now forwards the upstream MCP caller identity into `client.name` / `task_intake.context.client` using the real MCP `clientInfo` (`mcp_client_name`, `mcp_client_version`, `mcp_client_id`) instead of collapsing every caller into a generic `mcp-agent`.
    - When a client explicitly requests a provider, public agent responses/session status may include `provenance.provider_selection` with `requested_provider`, `final_provider_family`, `request_honored`, and `fallback`.
    - Public advisor-agent is reserved for user-facing end-to-end turns. Structured extractor / JSON-only microtasks and sufficiency-gate prompts are rejected with HTTP 400 `error="public_agent_microtask_blocked"`.
    - Duplicate heavy public-agent turns from the same MCP caller are rejected with HTTP 409 `error="duplicate_public_agent_session_in_progress"` and return the existing running session plus `wait_tool=advisor_agent_wait`.
    - Public MCP now preserves structured 4xx response fields from `/v3/agent/*` instead of flattening them into a generic transport error. Clients can rely on `existing_session_id`, `wait_tool`, `reason`, `hint`, `recommended_client_action`, and related `detail.*` fields when a turn is rejected.
      This dedupe also applies when the caller pre-generates a fresh `session_id`; only true resume/patch calls against an already-existing session bypass the duplicate guard.
  - `Pro + trivial prompt` (e.g. “请回复OK”) returns HTTP 400 `detail.error="trivial_pro_prompt_blocked"` with no request-level override.
  - `Pro + purpose=smoke/test/...` returns HTTP 400 `detail.error="pro_smoke_test_blocked"` with no request-level override.
  - Unified env toggle: `CHATGPTREST_ENFORCE_PROMPT_SUBMISSION_POLICY=1` (default on).
  - Worker completion guard now has a legacy trivial wait-loop breaker. If an old synthetic/trivial ask survives ingress and repeatedly hits `completion_guard_downgraded(reason=answer_quality_suspect_short_answer)`, the worker will finalize the job after `CHATGPTREST_LEGACY_TRIVIAL_WAIT_LOOP_BREAKER_THRESHOLD` repeated downgrades instead of requeueing forever.

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
- `input.file_paths` is supported, but ChatgptREST treats it as a **Drive-attach workflow**:
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
- Drive upload/ID resolution error policy:
  - retryable errors (timeouts/transient API issues) -> `status=cooldown` (`reason_type=DriveUploadNotReady`)
  - permanent errors (rclone misconfig/auth, file too large) -> `status=error` (`error_type=DriveUploadFailed`)
- Size precheck: `CHATGPTREST_GDRIVE_MAX_FILE_BYTES` (default `209715200` / 200MiB; set to `0` to disable).
- Optional cleanup (disabled by default): `CHATGPTREST_GDRIVE_CLEANUP_MODE` (`never` | `on_success` | `always`).
- Gemini Web can still use app mentions: if your prompt includes `@Google 云端硬盘` / `@Google Drive` (or `@Google 文档` / `@Google Docs`), the internal driver inserts the real Gemini app mention (not plain text). Treat this as a convenience for **referencing existing Drive resources**, not as a reliable substitute for attachments.
- Policy: ChatgptREST does **not** allow clients to force Gemini's "Thinking" mode. Requests for `thinking` / `pro_thinking` are normalized to `preset=pro`.
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
- If `issue_id` is provided, the report is linked back into Issue Ledger via `issue_evidence_linked`.
- `route_mode=auto_*` may create downstream `repair.autofix` or `repair.open_pr` jobs; those job ids are included in the answer/report metadata.

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
- 409 if the answer is not readable yet (e.g. `status != completed` or missing `path`), with `detail.status` and optional `detail.retry_after_seconds`.
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

## Public Agent Facade (v3/agent)

The v3/agent endpoints provide a high-level agent interaction surface that abstracts away job/wait/answer machinery.

Client policy:
- For coding agents (Codex / Claude Code / Antigravity), the supported default integration path is the public MCP surface at `http://127.0.0.1:18712/mcp`.
- `/v3/agent/*` remains the backend ingress used by that public MCP surface, plus internal runtime / plugin / ops / validation paths.
- Do not expose `/v3/agent/*` as the default integration surface for other coding agents when the public MCP is available.
- Do not teach coding agents to call low-level `/v1/jobs kind=*web.ask` directly; if `/v1/jobs` must be used for ops or maintenance, keep that path behind an explicit maintenance client identity and separate documentation.

### `POST /v3/agent/turn`

Execute a single agent turn. The server handles routing, execution, and response formatting.

**Request body:**
```json
{
  "message": "user message",
  "session_id": "optional-session-id",
  "goal_hint": "code_review|research|image|report|repair",
  "depth": "light|standard|deep|heavy",
  "execution_profile": "default|thinking_heavy|deep_research|report_grade",
  "task_intake": {"spec_version": "task-intake-v2", "objective": "..."},
  "workspace_request": {"spec_version": "workspace-request-v1", "action": "deliver_report_to_docs", "payload": {}},
  "contract_patch": {"decision_to_support": "...", "audience": "..."},
  "timeout_seconds": 300,
  "context": {},
  "client": {"name": "...", "instance": "..."}
}
```

Notes:
- `depth=heavy` is treated as a compatibility alias for `execution_profile=thinking_heavy`.
- `execution_profile=thinking_heavy` is the fast premium analysis lane: deeper reasoning with optional websearch support, but not the long-running `deep_research` lane.

**Response:**
```json
{
  "ok": true,
  "session_id": "agent_sess_xxx",
  "run_id": "run_xxx",
  "status": "completed",
  "answer": "...",
  "delivery": {
    "format": "markdown",
    "mode": "sync",
    "stream_url": "/v3/agent/session/agent_sess_xxx/stream",
    "answer_chars": 4210,
    "accepted": false,
    "answer_ready": true,
    "watchable": true,
    "artifact_count": 1,
    "terminal": true
  },
  "lifecycle": {
    "phase": "completed",
    "status": "completed",
    "turn_terminal": true,
    "session_terminal": true,
    "blocking": false,
    "resumable": false,
    "same_session_patch_allowed": false,
    "next_action_type": "followup",
    "stream_supported": true
  },
  "artifacts": [{"kind": "conversation_url", "uri": "https://..."}],
  "effects": {
    "artifact_delivery": {"count": 1, "available": true, "kinds": ["conversation_url"]}
  },
  "provenance": {"route": "dual_review", "provider_path": ["chatgpt_pro"], "final_provider": "chatgpt"},
  "next_action": {"type": "followup", "safe_hint": "..."},
  "recovery_status": {"attempted": false, "final_state": "clean"},
  "task_intake": {"spec_version": "task-intake-v2", "objective": "..."},
  "control_plane": {
    "requested_execution_profile": "thinking_heavy",
    "effective_execution_profile": "thinking_heavy",
    "contract_source": "client",
    "contract_completeness": 1.0
  },
  "clarify_diagnostics": {}
}
```

Notes:
- `lifecycle.phase` is the northbound lifecycle state intended for coding agents:
  - `accepted`
  - `clarify_required`
  - `progress`
  - `completed`
  - `failed`
  - `cancelled`
- `delivery.accepted=true` is used on the initial `202 deferred` accept response.
- `effects.workspace_action` is projected for workspace actions and workspace clarify flows.

### `GET /v3/agent/session/{session_id}`

Retrieve session state (fallback, not primary use).

**Response:**
```json
{
  "ok": true,
  "session_id": "...",
  "run_id": "...",
  "status": "completed|running|needs_followup|failed|cancelled",
  "last_message": "...",
  "last_answer": "...",
  "route": "...",
  "delivery": {"mode": "deferred", "stream_url": "/v3/agent/session/.../stream"},
  "lifecycle": {"phase": "progress", "next_action_type": "check_status"},
  "effects": {"artifact_delivery": {"count": 0, "available": false, "kinds": []}},
  "task_intake": {"spec_version": "task-intake-v2", "objective": "..."},
  "control_plane": {"contract_source": "client", "contract_completeness": 1.0},
  "clarify_diagnostics": {"missing_fields": ["decision_to_support"]},
  "next_action": {"type": "followup", "safe_hint": "..."}
}
```

### `POST /v3/agent/cancel`

Cancel a running session.

**Request body:**
```json
{"session_id": "session-to-cancel"}
```

**Response:**
```json
{
  "ok": true,
  "session_id": "...",
  "status": "cancelled",
  "message": "Session cancelled successfully",
  "delivery": {"mode": "deferred", "terminal": true},
  "lifecycle": {"phase": "cancelled", "session_terminal": true}
}
```

### `GET /v3/agent/health`

Health check for agent service.

**Response:**
```json
{"status": "ok", "version": "v3-agent", "active_sessions": 5}
```

## Chrome CDP Architecture & Isolation (Important for AI Agents)

ChatgptREST depends on dedicated headless Chrome instances to maintain long-running, stable LLM web sessions (handling CAPTCHAs, SSE streams, DOM mutations).

To prevent `TargetClosedError` and session interference, **external AI Coding Agents (e.g. Antigravity, Claude Code, Cursor, Codex) MUST NOT connect their browser automation MCPs (like `chrome-devtools` or `browser-use`) to the ChatgptREST driver ports**.

**Official Port Allocation:**
- `127.0.0.1:9226` : Reserved exclusively for **ChatGPT Driver**. Do not attach external tools.
- `127.0.0.1:9335` : Reserved exclusively for **Qwen Driver**. Do not attach external tools.
- `127.0.0.1:9222` : **User's primary browser** (forwarded via SSH). This is the correct target for `browser-use` and `chrome-devtools` MCP extensions.
