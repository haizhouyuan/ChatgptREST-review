# ChatgptREST Handoff: Development Record & Historical Issues

This document captures the concrete problems observed so far and the code changes that addressed them, plus the operational milestones that shaped the current production posture. It exists so new maintainers can quickly answer:
- “What happened before, what was fixed, and where is the code?”
- “If it breaks, where do I look first?”
- “What’s safe to enable now, and what’s intentionally gated for later?”

Status note:
- The **chatgptMCP driver code has already been merged into this repo** (PR #1). `chatgptMCP` can be treated as a legacy/external fallback, not a production dependency, as long as `CHATGPTREST_DRIVER_MODE=internal_mcp`.

## Scope

- Repository: `ChatgptREST`
- Time range: v1 contract freeze → internal driver merge → safe-enable rollout → Gemini Web integration → SRE/guardrails hardening
- Focus: bug fixes, reliability improvements, and behavior changes that affect send/wait semantics, idempotency, answer integrity, SRE diagnostics, or wind-control risk

## Milestones (for quick orientation)

- v1 contract freeze: `docs/contract_v1.md`
- Two-phase scheduling (send vs wait) + timeout split: `8a42629`
- Follow-up via `parent_job_id` (server resolves `conversation_url`): `01ef24d`
- Duplicate-send prevention for “Error in message stream”: `1ff5ebc`
- Guard send-stage “in_progress but no conversation_url” (no duplicate resend): `590c6f4`
- Internal driver merged (chatgptMCP-in-repo): PR #1 / merge commit `8cb1658`
- Pro P1/P2 hardening batch: `b319916`
- Safe-enable rollout defaults (idempotency sent-guard + export throttling + driver state): `f492245`
- Ops defaults alignment (blocked-state path) + soak helper: `779d1e2`, `b410fd0`
- Gemini Web integration (ask + Drive attachments + Import code): `d8d794e`, `232cc86`
- Guard against ChatGPT/Gemini conversation_url mismatch: `5f9b1b7`
- Anti-detection hardening (realism + diagnostics): `c95dffd`, `d63be18`, `237d8df`
- SRE diagnostics job (`repair.check`): `e493e6b`
- Thinking-time quality guard (Pro) + window limits: `a8d6af6`, `d594367`, `627bc68`, `bb3ee6b`
- Viewer noVNC + safe UI viewing: `f10356a`

## Where to look first (when something is “weird”)

- One job end-to-end: `artifacts/jobs/<job_id>/` (`request.json`, `events.jsonl`, `result.json`, `answer.md`, `conversation.json`)
- DB truth: `state/jobdb.sqlite3` (tables: `jobs`, `job_events`, `idempotency`, `rate_limits`)
- Ops checklist: `docs/runbook.md`
- Historical root causes: this doc + linked file paths

## Key Fixes and Enhancements (Chronological)

1) **Answer path consistency (single source of truth)**
- Problem: `answer.md`/`answer.txt` could coexist; previews/readers sometimes picked the wrong one.
- Fix: persist `answer_path` in DB; preview and `/answer` always use the DB path. Added `reconcile_job_artifacts` to heal missing artifacts.
- Files: `chatgptrest/core/artifacts.py`, `chatgptrest/api/routes_jobs.py`, `chatgptrest/core/job_store.py`

2) **Lease token + CAS and staged writes**
- Problem: reclaimed jobs could be overwritten by old workers; partial writes could corrupt answers.
- Fix: lease token + CAS checks for `store_answer_result`; staged write + atomic replace; heartbeat renewals.
- Files: `chatgptrest/core/job_store.py`, `chatgptrest/worker/worker.py`, `chatgptrest/core/artifacts.py`

3) **Cancel attribution and status transitions**
- Problem: cancellation lacked audit data and could not be traced to caller.
- Fix: `/cancel` now records safe client metadata (UA, X-Client-* headers) into job events.
- Files: `chatgptrest/api/routes_jobs.py`, `chatgptrest/core/job_store.py`

4) **Transient assistant errors treated as retryable**
- Problem: short UI errors like "Error in message stream" were treated as final answers.
- Fix: detect transient assistant errors, mark `in_progress`, and continue waiting in-place; if still unresolved, return retryable cooldown with `reason_type=TransientAssistantError`.
- Files: `chatgptrest/executors/chatgpt_web_mcp.py`

5) **Answer rehydration via answer_id**
- Problem: long answers could be truncated in tool output; full text was saved in chatgptMCP but not reloaded.
- Fix: if `answer_saved` + `answer_id` present and answer is truncated, rehydrate from `chatgpt_web_answer_get` and replace in-memory answer.
- Files: `chatgptrest/executors/chatgpt_web_mcp.py`

6) **Conversation export reconciliation (DOM export normalization)**
- Problem: conversation exports could include `json\nCopy code\n{...}` artifacts; reconciliation failed and left `answer.md` truncated.
- Fix: normalize DOM export into fenced code blocks, reconcile against conversation export before finalizing the answer.
- Files: `chatgptrest/worker/worker.py`
- Tests: `tests/test_conversation_export_reconcile.py`

7) **Answer/preview UTF-8 chunking by byte offset**
- Problem: long answers could be truncated or break UTF-8 boundaries when streamed.
- Fix: `/answer` and `/conversation` chunk APIs use byte offsets with UTF-8 boundary correction.
- Files: `chatgptrest/core/artifacts.py`, `chatgptrest/api/routes_jobs.py`

8) **Proxy correlation snapshots (mihomo delay)**
- Problem: blocked/cooldown events were not correlated with proxy health.
- Fix: on blocked/cooldown, snapshot mihomo delay results into job events + artifacts.
- Files: `chatgptrest/worker/worker.py`, `chatgptrest/core/mihomo_delay.py`

9) **Two-phase scheduling (send vs wait)**
- Problem: single worker could block queue for long-running asks; retries risked re-sending prompts.
- Fix: added `phase` column with `send|wait`, worker roles `send|wait|all`, and a requeue path that releases the lease and flips phase to `wait` when a job remains `in_progress`.
- Files: `chatgptrest/core/db.py`, `chatgptrest/core/job_store.py`, `chatgptrest/worker/worker.py`, `chatgptrest/api/routes_jobs.py`
- Notes:
  - `release_for_wait` updates phase to `wait` and clears the lease.
  - Queue estimates now only count `phase=send` jobs.

10) **Timeout split: send vs wait**
- Problem: client timeout and server wait timeout were conflated.
- Fix: `send_timeout_seconds` and `wait_timeout_seconds` introduced; legacy `timeout_seconds` still works as a fallback.
- Files: `chatgptrest/executors/chatgpt_web_mcp.py`, `chatgptrest/mcp/server.py`, `docs/contract_v1.md`

11) **Wait refresh + export fallback**
- Problem: sometimes "thinking" ended but the answer did not surface until refresh/export.
- Fixes:
  - Driver `chatgpt_web_wait` does a best-effort refresh on timeout and retries extraction (no prompt send).
  - Wait phase can stay `in_progress` even when `conversation_url` is temporarily unavailable (polls driver idempotency until URL appears).
  - Worker attempts `conversation_export` on wait-stage `in_progress` and can finalize from export (`answer_completed_from_export`).
- Files: `chatgptrest/executors/chatgpt_web_mcp.py`, `chatgptrest/worker/worker.py`

12) **Worker role support in ops**
- Update: `ops/start_worker.sh` accepts `send|wait|all` to enable two-phase operation.
- Files: `ops/start_worker.sh`, `docs/runbook.md`, `README.md`

13) **Attachment send stuck guard**
- Problem: some attachment/new-chat sends returned `in_progress` without `conversation_url`, blocking the send worker.
- Fix: keep the job `in_progress` and requeue to wait-phase; wait-phase polls driver idempotency until `conversation_url` becomes available (no prompt resend, no send-throttle consumption).
- Files: `chatgptrest/executors/chatgpt_web_mcp.py`, `docs/runbook.md`

14) **chatgptMCP driver merged into ChatgptREST repo**
- Problem: dependency on external chatgptMCP repo made deployments and debugging harder.
- Fix: internal driver added (embedded + internal MCP daemon), with a driver backend abstraction and mode switch.
- Files: `chatgptrest/driver/*`, `chatgpt_web_mcp/*`, `chatgptrest_driver_server.py`, `ops/start_driver.sh`, `README.md`, `docs/runbook.md`

15) **Driver tab limit + stats**
- Problem: uncontrolled concurrent tabs can destabilize Chrome.
- Fix: driver-side concurrent-page semaphore with `cooldown` on limit hit, plus `chatgpt_web_tab_stats` for observability.
- Files: `chatgpt_web_mcp/server.py`, `ops/maint_daemon.py`, `docs/runbook.md`

16) **Driver persistent state defaults**
- Problem: driver restarts could lose idempotency/blocked/rate-limit state, increasing duplicate-send and misdiagnosis risk.
- Fix: `ops/start_driver.sh` defaults these to `state/driver/`:
  - `MCP_IDEMPOTENCY_DB`
  - `CHATGPT_BLOCKED_STATE_FILE`
  - `CHATGPT_GLOBAL_RATE_LIMIT_FILE`
- Files: `ops/start_driver.sh`, `docs/runbook.md`

17) **Conversation export cooldown + backoff**
- Problem: wait slicing could trigger frequent conversation exports, amplifying UI/network load and wind-control risk.
- Fix: per-job export throttling via `artifacts/jobs/<job_id>/conversation_export_state.json`:
  - success cooldown (default 120s)
  - exponential backoff on failures (default 60s base, max 600s)
  - optional global export pacing via DB `rate_limits` key `chatgpt_web_conversation_export`
- Files: `chatgptrest/worker/worker.py`, `docs/runbook.md`

18) **Hard guardrail: suppress fallback resends when idempotency says sent**
- Problem: preset fallback could mistakenly resend if tool debug timeline was missing/incomplete.
- Fix: consult driver `chatgpt_web_idempotency_get(record.sent)` before fallback; if sent, suppress resend and proceed to wait.
- Files: `chatgptrest/executors/chatgpt_web_mcp.py`

19) **Atomic worker JSON snapshots**
- Problem: crash during JSON write could leave half-written artifacts (confusing repair/incident tooling).
- Fix: worker JSON snapshots now use atomic write (tmp + rename).
- Files: `chatgptrest/worker/worker.py`

20) **Ops: blocked-state default path aligned with driver state**
- Problem: ops tools (monitor/maint) defaulted to `.run/chatgpt_blocked_state.json` and could miss the real driver blocked-state after the state-dir move.
- Fix: `ops/monitor_chatgptrest.py` and `ops/maint_daemon.py` now default to `state/driver/chatgpt_blocked_state.json` when available.
- Files: `ops/monitor_chatgptrest.py`, `ops/maint_daemon.py`

21) **Ops: soak helper for long observation windows**
- Problem: ad-hoc one-hour observation was error-prone to start/restart in tmux panes.
- Fix: added `ops/run_soak.sh` to run `monitor_chatgptrest` for N seconds and write a summary.
- Files: `ops/run_soak.sh`, `ops/monitor_chatgptrest.py`, `ops/summarize_monitor_log.py`

22) **Idempotency collision: `file_paths` absolute vs relative**
- Symptom: MCP callers can see `HTTP 409 idempotency_key collision` even though they “used the same file”.
- Root cause: idempotency compares the JSON payload; `input.file_paths=["state/tmp/x.zip"]` and `["/abs/path/state/tmp/x.zip"]` are different payloads.
- Fix:
  - On `kind=chatgpt_web.ask`, the API canonicalizes `input.file_paths`:
    - absolute stays absolute (after resolve)
    - relative is interpreted relative to `ChatgptREST/` repo root
    - missing paths fail early with HTTP 400 (avoid creating a doomed job)
  - Collision errors now include the existing job id + hash prefixes to speed up debugging.
- Files: `chatgptrest/api/routes_jobs.py`, `chatgptrest/core/idempotency.py`

23) **MCP wrapper: transient HTTP disconnects during long-poll**
- Symptom: `chatgptrest_job_wait` may fail with `"Remote end closed connection without response"` even when `/healthz` is OK.
- Common cause: local API restart during an in-flight long poll, or transient socket reset.
- Fix: the MCP REST wrapper now retries once on common transient network errors (URLError/RemoteDisconnected/timeout) before surfacing an error.
- Files: `chatgptrest/mcp/server.py`

24) **Avoid false `needs_followup`: “Answer now / Writing code”**
- Symptom: jobs could be marked `needs_followup` with `stuck_in_writing_code_answer_now` even when ChatGPT was simply thinking or using internal tools.
- Root cause: debug artifact text contains both “Answer now” and “Writing code” in normal flows.
- Fix: treat this as a non-terminal `in_progress` marker and continue in wait/export recovery (no prompt resend).
- Files: `chatgptrest/executors/chatgpt_web_mcp.py`, `chatgptrest/worker/worker.py`

25) **Health endpoint aliases + MCP input tolerance**
- Fixes:
  - REST: `/health` and `/v1/health` now exist as aliases for `/healthz`.
  - MCP: `chatgptrest_chatgpt_ask_submit.file_paths` accepts either `string` or `string[]` and normalizes internally.
- Files: `chatgptrest/api/routes_jobs.py`, `chatgptrest/mcp/server.py`

26) **Race: rescue follow-up sent right before parent completes**
- Symptom: operators/scripts may send a "rescue follow-up" (e.g. "继续…不要再写代码…") because the job appears stuck, but the parent job completes within ~1s, causing a duplicate user message in the same ChatGPT conversation.
- Root causes:
  - `conversation_export` OK cooldown could suppress the final export attempt at completion, leaving `conversation.json` with only the user message and misleading `conversation_export_chars`.
  - Manual follow-up runs in parallel with the parent job completion, and nothing prevented "send" from happening.
- Fixes:
  - **Completion export is conditional + safer**: if the existing `conversation.json` still has no assistant reply, bypass the OK cooldown to attempt one final export; **never bypass failure backoff** (respects `cooldown_until`).
  - **Rescue follow-up guard is race-scoped**: only applies when the parent is still `in_progress` at follow-up start; if the parent completes within a tiny grace window, short-circuit the follow-up to the parent answer (no new prompt sent).
- Files: `chatgptrest/worker/worker.py`, `tests/test_conversation_export_force.py`, `tests/test_rescue_followup_guard.py`

27) **Deep Research: short “ack” wrongly treated as completed**
- Symptom: Deep Research sometimes returns a short confirmation (“我将立即开展…/稍后请查收/报告准备好后…”). If the server marks that as `completed`, clients stop waiting for the real long report and may start a new Round → duplicate conversations/prompts.
- Root causes:
  - driver-side ack classifier regex was too narrow; short confirmations fell through and were treated as a normal completed answer
  - wait worker’s “finalize from conversation export” path can also bypass driver classification unless it applies the same “ack ≠ completed” rule
- Fixes:
  - expand the ack patterns to include common “稍后请查收/报告准备好后/确认我将开始…” phrasing (driver + worker)
  - add a **worker-side completion guard**: if `deep_research=true` and the captured answer looks like a short “ack”, downgrade `completed → in_progress` and requeue the job (event: `completion_guard_downgraded`)
  - enforce `min_chars` on completion: if the caller asked for `min_chars>0` but the captured answer is shorter, downgrade `completed → in_progress` and keep waiting (same event)
  - implementation note: the worker must read `deep_research` from the decoded `params_obj` (the DB job record omits params)
- Files: `chatgpt_web_mcp/server.py`, `chatgptrest/worker/worker.py`
- Tests: `tests/test_conversation_export_reconcile.py`
- Example artifacts: `artifacts/jobs/2a0922036c674213bec3299ed875b5e7/answer.md`, `artifacts/jobs/eb0b9f206fb547be921e76f323d9aa10/answer.md`

28) **Answer quality cross-check (offline verifier)**
- Goal: prevent “clients blindly trusting a partial/malformed answer” by offering a cheap, offline cross-check between `answer.*` and `conversation.json` (no extra UI calls).
- Tool: `ops/verify_job_outputs.py` writes:
  - `artifacts/jobs/<job_id>/verify_report.json`
  - `artifacts/jobs/<job_id>/verify_report.md`
- It flags common integrity risks:
  - `unbalanced_fences` (Markdown code fence not closed)
  - `tool_answer_truncated_not_rehydrated` (tool returned truncated answer and rehydration did not happen)
  - `answer_export_low_similarity` (exported assistant text does not match saved answer, after normalization)
  - plus a note when `conversation.json` has no assistant (export backend 404/race), so you know cross-check is incomplete.
- Docs: `docs/runbook.md` (“Answer Quality Cross-check (offline)”)

29) **Duplicate prompt: same question sent twice in one conversation**
- Symptom: the same user prompt appears twice in `chatgpt.com` for the same thread (wind-control risk).
- Most common cause: client retries using a different `Idempotency-Key` (e.g. default key included `--out` path, and the retry wrote to a different file → new key).
- Fixes:
  - **Driver-side guard (server-side fail-safe)**: before typing in an existing conversation, compare `question` vs the last user message already in DOM; if equal, skip send and resume wait (no new user message).
    - Env: `CHATGPT_DUPLICATE_PROMPT_GUARD` (default `true`)
    - File: `chatgpt_web_mcp/server.py`
    - Test: `tests/test_duplicate_prompt_guard.py`
  - **Client-side key stability**: `codexread/scripts/chatgpt_mcp_ask.py` default idempotency key no longer includes `--out`; it hashes `tool+question+conversation_url/parent_job_id+timeout_seconds+min_chars+uploads`.

30) **Conversation single-flight: prevent rapid-fire follow-ups**
- Symptom: a single `chatgpt.com` conversation shows multiple user messages sent within seconds (often because a client did not wait for the previous job to complete/appear).
- Root causes (common in the wild):
  - multiple submission paths (script + raw REST/MCP) were used for the same conversation without reusing a stable `Idempotency-Key`
  - follow-up jobs were accepted while a previous ask job in the same conversation was still `queued/in_progress`
- Fixes:
  - **Hard gate at enqueue time** (default): when a follow-up targets a conversation that already has an active ask job (`queued/in_progress`), `POST /v1/jobs` returns `HTTP 409 detail.error=conversation_busy` unless `params.allow_queue=true`.
    - Env: `CHATGPTREST_CONVERSATION_SINGLE_FLIGHT` (default `true`)
    - Files: `chatgptrest/api/routes_jobs.py`, `chatgptrest/core/job_store.py`
  - **Worker-side enforcement**: send workers refuse to claim a send-stage job when another ask is already `in_progress` for the same `conversation_id` (prevents overlapping prompts even when jobs are queued).
    - Files: `chatgptrest/core/job_store.py::claim_next_job`
  - **Attribution**: job creation now persists `client` (body) into `jobs.client_json` and includes `requested_by` (safe HTTP headers + host/port + server pid/hostname) in `job_created` events/artifacts to help identify who created the job.
    - Files: `chatgptrest/core/db.py`, `chatgptrest/api/routes_jobs.py`, `chatgptrest/core/job_store.py`

31) **Gemini Web: attach server files via Google Drive picker (no local upload)**
- Symptom: Gemini Web “上传文件”按钮被禁用/受限，或上传大小限制导致无法直接通过 UI 上传本地包。
- Goal: keep the “clients only pass file_paths + question” experience while avoiding Gemini local upload limits.
- Fix:
  - Allow `kind=gemini_web.ask` to accept `input.file_paths` (server-local paths).
  - Worker uploads each file to Drive via `rclone copyto` to `CHATGPTREST_GDRIVE_RCLONE_REMOTE` (default `gdrive`) under `CHATGPTREST_GDRIVE_UPLOAD_SUBDIR` (default `chatgptrest_uploads`).
  - Worker resolves the Drive file ID via `rclone lsjson` and passes a Drive URL (`https://drive.google.com/open?id=<id>`) to the driver.
  - Driver attaches those files via Gemini UI: `+` → `从云端硬盘添加` → paste URL → `插入`.
  - Default is fail-closed: if any `drive_url` can’t be resolved, return `status=cooldown` (`DriveUploadNotReady`). Only enable filename-search fallback when explicitly requested (`params.drive_name_fallback=true`).
- Files:
  - `chatgptrest/api/routes_jobs.py` (input canonicalization + allow file_paths for Gemini)
  - `chatgptrest/executors/gemini_web_mcp.py` (copy to Drive + pass `drive_files` to driver)
  - `chatgpt_web_mcp/server.py` (Gemini picker automation: attach drive file before send)
  - Docs: `docs/contract_v1.md`, `docs/runbook.md`, `AGENTS.md`
- Ops notes:
  - Requires `rclone` configured + authorized for Drive (override config path via `CHATGPTREST_RCLONE_CONFIG` when needed).
  - Drive name search can lag after upload; ID→URL attach is preferred for fresh uploads (and is the default).

32) **Gemini Web: “导入代码 / Import code” (repo URL) gated behind explicit param**
- Goal: let clients ask Gemini to review a repo without any UI automation client-side.
- Fix:
  - Allow `kind=gemini_web.ask` to accept `input.github_repo` (repo URL) **only** when `params.enable_import_code=true`.
  - Driver runs the Gemini UI “导入代码 / Import code” flow before sending the prompt.
- Files:
  - `chatgptrest/api/routes_jobs.py` (HTTP 400 unless explicitly enabled)
  - `chatgptrest/executors/gemini_web_mcp.py` (pass `github_repo` to driver tool args)
  - `chatgpt_web_mcp/server.py` (`_gemini_import_code_repo` + tool args)

33) **Conversation URL kind validation (ChatGPT vs Gemini)**
- Symptom: callers accidentally pass a `chatgpt.com` conversation URL to `kind=gemini_web.*` (or vice versa), causing wrong-driver execution and confusing blocked/cooldown signals.
- Fix: validate the conversation URL “kind” and reject mismatches early.
- Commit: `5f9b1b7`
- Files: `chatgptrest/core/job_store.py`, `chatgptrest/mcp/server.py`, `chatgpt_web_mcp/server.py`
- Tests: `tests/test_conversation_url_kind_validation.py`

34) **Avoid stuck `cooldown` at `max_attempts`**
- Symptom: a job could remain in `cooldown` even after exhausting attempts (looks like “forever retrying”).
- Fix: avoid leaving jobs stuck in cooldown at the retry cap; force a terminal/next-step transition.
- Commit: `08db9a3`
- Files: `chatgptrest/core/job_store.py`
- Tests: `tests/test_leases.py`

35) **Web automation realism hardening (wind-control risk reduction)**
- Goal: reduce “machine-like” signals and make UI automation failures easier to triage.
- Commits: `c95dffd`, `d63be18`, `237d8df`
- Files: `chatgpt_web_mcp/server.py`, `ops/chrome_start.sh`
- Docs: `docs/runbook.md`

36) **Gemini wait reliability (URL handoff + completion detection + quota/picker guards)**
- Symptom: `gemini_web_wait` could miss completion, get stuck on a base app URL, or crash on Drive picker retries; Pro/Thinking quota notices needed explicit handling.
- Fix: harden wait completion detection and conversation URL upgrades/handoff; add guards for quota notices and picker retry edge cases.
- Commits: `73bde2b`, `a630e93`, `3e2c5f9`, `7d3bd28`, `614ceee`, `f869b04`, `7ce6084`
- Files: `chatgpt_web_mcp/server.py`, `chatgptrest/executors/gemini_web_mcp.py`, `chatgptrest/core/job_store.py`
- Tests: `tests/test_conversation_url_upgrade.py`, `tests/test_gemini_wait_conversation_hint.py`, `tests/test_gemini_conversation_url_helpers.py`, `tests/test_gemini_mode_quota_notice.py`

37) **`min_chars` completion guard: fail-open**
- Problem: strict `min_chars` gating can stall jobs indefinitely when answers are legitimately short or export recovery is incomplete.
- Fix: switch the guard to fail-open behavior (still records evidence, but avoids permanent stalling).
- Commit: `5567d66`
- Files: `chatgptrest/worker/worker.py`
- Tests: `tests/test_min_chars_completion_guard.py`

38) **Fix export answer attribution when assistant reply is missing**
- Symptom: a conversation export can be present but missing the assistant reply, leading to incorrect attribution/overwrites during finalization.
- Fix: adjust reconcile/finalize attribution so missing-assistant exports don’t corrupt the saved answer.
- Commit: `97e2b5b`
- Files: `chatgptrest/worker/worker.py`
- Tests: `tests/test_conversation_export_reconcile.py`

39) **ChatGPT Web: netlog capture + “Answer now / Writing code” stuck handling**
- Symptom: “Pro thinking • Writing code” + `Answer now` can wedge a review job; without evidence it’s hard to debug UI/network causes.
- Fix:
  - optional redacted browser netlog capture for incident triage
  - treat “Answer now / Writing code” as non-terminal and keep recovery paths conservative (avoid false completion / risky resends)
- Commit: `437e85a`
- Files: `chatgpt_web_mcp/server.py`, `chatgptrest/executors/chatgpt_web_mcp.py`, `ops/start_driver.sh`, `docs/runbook.md`
- Tests: `tests/test_answer_now_writing_code_stuck.py`, `tests/test_chatgpt_web_netlog_redact_url.py`

40) **API guard: block smoketest prompt prefix by default**
- Goal: avoid accidentally sending “smoke test” prompts in production.
- Commit: `89acec9`
- Files: `chatgptrest/api/routes_jobs.py`
- Tests: `tests/test_block_smoketest_prefix.py`

41) **SRE diagnostics job: `repair.check` (no prompt send)**
- Goal: on-demand diagnostics/evidence collection without touching ChatGPT/Gemini UI.
- Commit: `e493e6b`
- Files: `chatgptrest/executors/repair.py`, `chatgptrest/worker/worker.py`, `chatgptrest/mcp/server.py`
- Docs: `docs/contract_v1.md`, `docs/runbook.md`
- Tests: `tests/test_repair_check.py`

42) **Thinking-time quality guard (Pro) + rate-limited automatic actions**
- Symptom: Pro thinking can show `Skipping` / `Answer now`; naive automation risks false completion or spammy refresh/regenerate loops.
- Fix: capture structured `thinking_observation` (and optional debug artifacts), enforce per-window limits for refresh/regenerate, and harden parsing.
- Commits: `a8d6af6`, `d594367`, `627bc68`, `bb3ee6b`
- Files: `chatgpt_web_mcp/server.py`, `chatgptrest/executors/chatgpt_web_mcp.py`, `chatgptrest/worker/worker.py`, `ops/start_driver.sh`, `docs/runbook.md`
- Tests: `tests/test_chatgpt_thought_for_seconds.py`, `tests/test_guardrail_window_limits.py`
- Review notes: `docs/reviews/pro_code_review_intelligent_sre_guardrails_20260102_191dd90.md`, `docs/reviews/gemini_code_review_guardrails_20260102_a783cab.md`

43) **Safe UI viewing: viewer Chrome + view-only noVNC**
- Goal: view ChatGPT UI safely without racing the worker’s CDP automation (separate profile/display; view-only mirror).
- Commit: `f10356a`
- Files: `ops/viewer_start.sh`, `ops/worker_viewonly_start.sh`, `ops/tailscale_serve_chatgptrest.sh`, `docs/runbook.md`

44) **Ops: Codex SRE incident analyzer scaffold**
- Goal: analyze incident evidence packs into structured suggestions/actions (offline, guardrailed).
- Commit: `209065f`
- Files: `ops/codex_sre_analyze_incident.py`, `ops/schemas/codex_sre_actions.schema.json`, `docs/maint_daemon.md`

45) **ChatGPT attachment upload: "+ menu" selector timeout + worker-triggered autofix**
- Symptom: `chatgpt_web.ask` with `input.file_paths` fails in send stage with `TimeoutError` like:
  - `Locator.click: Timeout … waiting for [role='menu']:visible … "Add photos" … "Upload file"`
  - Example job: `fba58ea330b6431ba28986b7851db59d`
- Root cause: ChatGPT Web UI A/B tests the “+” menu; generic file upload may be implemented via a hidden composer `input[type=file]` instead of a stable menu item.
- Fixes:
  - Driver upload prefers direct composer `input[type=file]` (fallback to menu only when needed).
  - Unsent transient UI/infra errors are classified as retryable: driver returns `status=cooldown` with `retry_after_seconds` (prevents terminal `error` before prompt send).
  - Workers auto-submit `kind=repair.autofix` for retryable `cooldown/blocked` infra/UI failures (event: `auto_autofix_submitted`).
- Files: `chatgpt_web_mcp/server.py`, `chatgptrest/worker/worker.py`, `docs/runbook.md`
- Tests: `tests/test_worker_auto_autofix_submit.py`

46) **Deep Research: auto-follow up “confirmation/clarification” prompts**
- Symptom: `deep_research=true` jobs can stop at `status=needs_followup` because ChatGPT asks to “confirm / clarify” before starting research; some clients treat `needs_followup` as terminal and never send the follow-up → research never starts.
- Root cause: driver correctly classifies these short “确认/澄清” replies as `needs_followup`, but unattended pipelines may need an explicit policy to proceed without a human follow-up.
- Fix (optional):
  - When enabled, driver `chatgpt_web_ask` auto-sends a **single** safe follow-up (`OK` + “按原提问开始调研；信息缺口做最小假设并标注；不要再反问”) when:
    - `deep_research` was explicitly requested, and
    - the first assistant reply is classified as `needs_followup`.
  - Gate: `CHATGPT_DEEP_RESEARCH_AUTO_FOLLOWUP` (default `false`). If the second assistant reply is still `needs_followup`, surface it to the caller (no loops).
- Files: `chatgpt_web_mcp/server.py`
- Tests: `tests/test_deep_research_classify.py`

47) **API died: MCP/maint auto-start ChatgptREST API**
- Symptom: clients see `Connection refused` / “Empty reply from server” when calling ChatgptREST tools; `job_get` fails even though jobs/artifacts exist in SQLite/artifacts.
- Root cause: REST API process was not supervised; when it exits (session ends / crash / manual stop), nothing restarts it.
- Fix:
  - MCP adapter bypasses proxies for localhost base_url and can best-effort auto-start the API when the port is down (rate-limited, local-only; gated by `CHATGPTREST_MCP_AUTO_START_API=1`).
- maint daemon gains `--enable-api-autostart` to auto-start API when the port is down (safe: no prompt send).
- Files: `chatgptrest/mcp/server.py`, `ops/maint_daemon.py`, `docs/runbook.md`

48) **2026-02-21 incident: API `start-limit-hit` + Pro trivial smoke prompt guardrails**
- Symptom:
  - Client-side MCP submit failed with `Connection refused` (`Errno 111`) because API `18711` was down.
  - Found multiple Pro trivial test prompts (`请回复OK`) that should not be used for production smoke checks.
- Findings:
  - Around `2026-02-21 15:42` user systemd logs showed a restart storm; `chatgptrest-api.service` entered `failed (start-limit-hit)` and stayed down.
  - `chatgptrest-mcp.service` was up, but API autostart in the unit was disabled (`CHATGPTREST_MCP_AUTO_START_API=0`), so callers got hard failures instead of self-heal.
- Fixes:
  - API-side guardrails (default ON):
    - `CHATGPTREST_BLOCK_TRIVIAL_PRO_PROMPT=1` blocks trivial prompts on Pro presets (`trivial_pro_prompt_blocked`).
    - `CHATGPTREST_BLOCK_PRO_SMOKE_TEST=1` blocks `params.purpose=smoke/test/...` on Pro presets (`pro_smoke_test_blocked`).
    - `2026-03-22` update: request-level Pro override flags are no longer honored; Pro smoke/trivial is now hard-blocked.
  - systemd template now enables MCP API autostart by default:
    - `ops/systemd/chatgptrest-mcp.service` sets `CHATGPTREST_MCP_AUTO_START_API=1`.
  - Runbook now includes `start-limit-hit` recovery commands (`reset-failed` + restart + health check).
- Files: `chatgptrest/api/routes_jobs.py`, `tests/test_block_smoketest_prefix.py`, `ops/systemd/chatgptrest-mcp.service`, `docs/runbook.md`

49) **OpenClaw guardian: timer化 + 误报修正（忽略已取消/终态违规样本）**
- Symptom:
  - guardian dry-run 会把“已取消的历史 Pro 短提示词 job”持续计入 `policy_violations`，导致长期 `needs_attention=true`。
- Fixes:
  - `ops/openclaw_guardian_run.py` 仅对活动状态（`queued/in_progress/cooldown/blocked/needs_followup`）计入 policy violation。
  - 新增 systemd 单元：`chatgptrest-guardian.service` + `chatgptrest-guardian.timer`（每 15 分钟巡查）。
- runbook/AGENTS 补充 guardian 入口与告警配置。
- Files: `ops/openclaw_guardian_run.py`, `ops/systemd/chatgptrest-guardian.service`, `ops/systemd/chatgptrest-guardian.timer`, `docs/runbook.md`, `AGENTS.md`

50) **Client Issue 自动收口 + monitor-12h 固化**
- Symptom:
  - 客户端 issue 已支持自动登记，但长期无复发的 `open/in_progress` issue 没有自动收口，台账会持续堆积。
  - `monitor-12h` 仅作为一次性 transient 任务，缺少稳定 timer 管理。
- Fixes:
  - guardian 增加 `client_issue_sweep`：默认每轮扫描 `worker_auto` + `open/in_progress`，对超过 TTL（默认 `72h`）无复发 issue 自动标记 `mitigated`。
  - 新增参数（支持 env 覆盖）：`CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_*`。
  - 新增脚本 `ops/run_monitor_12h.sh` 与 systemd 单元：
    - `chatgptrest-monitor-12h.service`
    - `chatgptrest-monitor-12h.timer`
  - runbook/client registry 更新闭环口径与参数说明。
- Files:
  - `ops/openclaw_guardian_run.py`
  - `tests/test_openclaw_guardian_issue_sweep.py`
  - `ops/run_monitor_12h.sh`
  - `ops/systemd/chatgptrest-monitor-12h.service`
  - `ops/systemd/chatgptrest-monitor-12h.timer`
  - `docs/runbook.md`
  - `docs/client_projects_registry.md`
  - `ops/systemd/chatgptrest.env.example`
  - `ops/systemd/install_user_units.sh`

51) **OpenClaw orch agent 开发补齐（reconcile + wake + timer）**
- Symptom:
  - `chatgptrest-orch` / `chatgptrest-codex-w*` 出现“在册但本地 `agentDir` 缺失/漂移”，导致 orch 调度不稳定。
- Fixes:
  - 新增 `ops/openclaw_orch_agent.py`：
    - 检查必需 agent（orch + w1/w2/w3 + guardian）是否存在、workspace/model 是否匹配、agentDir 是否存在。
    - `--reconcile` 会对漂移项执行 `delete + add` 重建。
    - `--ping` 可逐个 agent 做一次 healthcheck turn（可选）。
  - 新增 `ops/openclaw_orch_wake.sh`（固定 `chatgptrest-orch` + `chatgptrest-orch-main`）。
  - 新增 systemd 可选巡检：
    - `chatgptrest-orch-doctor.service`
    - `chatgptrest-orch-doctor.timer`
  - runbook/AGENTS/install 脚本同步 orch 入口与操作方式。
- Files:
  - `ops/openclaw_orch_agent.py`
  - `ops/openclaw_orch_wake.sh`
  - `ops/systemd/chatgptrest-orch-doctor.service`
  - `ops/systemd/chatgptrest-orch-doctor.timer`
  - `ops/systemd/install_user_units.sh`
  - `docs/runbook.md`
  - `AGENTS.md`
  - `tests/test_openclaw_orch_agent.py`

52) **MCP 后台 wait（Codex 不阻塞）**
- Symptom:
  - Codex 调用 `chatgptrest_job_wait` 时会前台阻塞，无法并行处理其他工作；用户常见感知是“viewer 已出答案但 agent 卡在 wait”。
- Fixes:
  - 新增后台 wait 工具：
    - `chatgptrest_job_wait_background_start`
    - `chatgptrest_job_wait_background_get`
    - `chatgptrest_job_wait_background_list`
    - `chatgptrest_job_wait_background_cancel`
  - 后台任务复用 `chatgptrest_job_wait` 的 cooldown/auto-repair/autofix 语义，但调用方可立即返回继续工作。
  - 支持 tmux controller 通知（start/done/error/canceled），并对完成 watcher 提供保留窗口（默认 24h）。
  - 修复取消竞态：即使 cancel 发生在 runner 早期，watch 状态也会收敛为 `canceled`。
- Files:
  - `chatgptrest/mcp/server.py`
  - `tests/test_mcp_job_wait_background.py`
  - `docs/runbook.md`
  - `docs/client_interactions_v3.md`
  - `AGENTS.md`

53) **周期 UI 漂移巡检闭环（ui_canary + orch/guardian 联动）**
- Symptom:
  - 现有 `self_check/capture_ui` 主要在 incident 发生后被动触发，缺少“定期主动巡检”，UI 改版容易在首个线上作业时才暴露。
  - `openclaw_orch_agent` 之前仅覆盖 agent 注册漂移，不含 UI 健康态与近期 incident 联动。
- Fixes:
  - `maint_daemon` 增加周期 `ui_canary`（默认开启）：
    - 定期执行 provider `self_check`（chatgpt/gemini/qwen）。
    - 连续失败达到阈值后创建 `category=ui_canary` incident，落盘 `ui_canary_probe.json` + `cdp_version.json`。
    - 失败时按冷却触发 `capture_ui`（不发 prompt）。
    - 输出总览：`artifacts/monitor/ui_canary/latest.json`，并将状态持久化进 `state/maint_daemon_state.json`。
  - Gemini 补齐 `capture_ui` 工具链：
    - 新增 `gemini_web_capture_ui`（tools/provider/runtime paths 全链路可用）。
    - `repair.check` / `maint_daemon` provider 映射均已支持 Gemini `capture_ui`。
  - `openclaw_orch_agent` 扩展：
    - 汇总 `ui_canary` 报告 + 近期 `ui_canary/proxy` open incidents。
    - 新增可选 `--wake-on-attention`（带 cooldown）触发 orch 会话处理。
  - `openclaw_guardian` 扩展：
    - 默认纳入 orch doctor 报告（`latest_report.json`）参与 `needs_attention` 判定与告警摘要。
- Files:
  - `ops/maint_daemon.py`
  - `chatgpt_web_mcp/providers/gemini/capture_ui.py`
  - `chatgpt_web_mcp/providers/gemini_web.py`
  - `chatgpt_web_mcp/tools/gemini_web.py`
  - `chatgpt_web_mcp/runtime/paths.py`
  - `chatgptrest/executors/repair.py`
  - `ops/openclaw_orch_agent.py`
  - `ops/openclaw_guardian_run.py`
  - `ops/systemd/chatgptrest-maint-daemon.service`
  - `ops/systemd/chatgptrest-orch-doctor.service`
  - `docs/runbook.md`
  - `AGENTS.md`
  - `tests/test_maint_daemon_provider_tools.py`
  - `tests/test_maint_daemon_ui_canary.py`
  - `tests/test_repair_provider_tools.py`
  - `tests/test_openclaw_orch_agent.py`
  - `tests/fixtures/mcp_tools_snapshot.json`

54) **rescue follow-up 竞态补强（parent 已完成但晚于 follow-up 创建）**
- Symptom:
  - `chatgpt_web.ask` rescue follow-up 在 send guard 启动时，parent 可能已经从 `in_progress` 变为 `completed`；
  - 旧逻辑只 guard `initial_parent_status=in_progress`，会漏掉该竞态，导致 follow-up 继续执行并落成 `cooldown`。
- Fixes:
  - rescue guard 增加 `parent.updated_at >= follow_job.created_at` 判定：
    - 若 parent 虽已 `completed`，但完成时间晚于 follow-up 创建时间，仍进入短路窗口并复用 parent answer。
  - 短路事件 payload 增补 `initial_parent_status/initial_parent_updated_at/follow_created_at` 便于复盘。
- Files:
  - `chatgptrest/worker/worker.py`
  - `tests/test_rescue_followup_guard.py`

55) **guardian 缺失 openclaw 命令时降级而非崩溃**
- Symptom:
  - `chatgptrest-guardian.service` 在需要触发 guardian agent/feishu channel 时，若系统无 `openclaw` 命令会抛 `FileNotFoundError`，oneshot 直接失败并无结构化产出。
- Fixes:
  - `_run_guardian_agent` / `_notify_feishu_channel` 捕获 `FileNotFoundError`（及通用异常），返回结构化错误对象，不再抛异常终止。
  - systemd 单元新增 `SuccessExitStatus=2`：将“未解决 attention”与“脚本异常崩溃”区分开，避免把业务告警误记为执行失败。
  - runbook 增补说明：可通过 `--openclaw-cmd` 指定命令路径。
  - 新增单测覆盖缺失命令降级路径。
- Files:
  - `ops/openclaw_guardian_run.py`
  - `ops/systemd/chatgptrest-guardian.service`
  - `tests/test_openclaw_guardian_issue_sweep.py`
  - `docs/runbook.md`

56) **viewer `error code 15` 自愈：watchdog 识别 GPU crash burst**
- Symptom:
  - noVNC 端口/HTTP 探针仍健康，但 viewer Chrome 侧反复出现 `GPU process exited unexpectedly: exit_code=15`，用户体感为 viewer 黑屏/不稳定。
- Fixes:
  - `viewer_watchdog` 新增 `chrome.log` 扫描：
    - 在最近窗口（默认 200 行）内统计 `exit_code=15` 次数；
    - 达到阈值（默认 3）即判定 unhealthy，并强制 `--full` 重启。
  - 新增可调参数：
    - `CHATGPTREST_VIEWER_WATCHDOG_GPU_EXIT15_THRESHOLD`
    - `CHATGPTREST_VIEWER_WATCHDOG_CHROME_LOG_LINES`
- Files:
  - `ops/viewer_watchdog.py`
  - `tests/test_viewer_watchdog.py`
  - `ops/systemd/chatgptrest.env.example`
  - `docs/runbook.md`
  - `docs/issues_registry.yaml`

57) **driver singleton lock 冲突导致 MCP 启动失败（`Unexpected content type: None`）**
- Symptom:
  - Codex 启动 MCP 时提示：
    - `chatgpt_web` handshake failed (`Unexpected content type: None`)
    - 常伴随 `MCP startup incomplete`。
  - `systemd --user status chatgptrest-driver.service` 可见反复重启或 `start-limit-hit`；
    driver 日志出现：`Another MCP server instance is already running (singleton lock held)`。
- Root cause:
  - driver 由 systemd 管理时，若走到脚本直启兜底，可能生成非 systemd 管理的进程；
    后续 systemd 重启会与 singleton lock 冲突，导致 `18701` 不可用，MCP 握手失败。
  - 同时锁文件默认在 `.run/`，运维定位不够直观，容易与其它状态路径混淆。
- Fixes:
  - 将 driver singleton lock 默认固定到 `state/driver/chatgpt_web_mcp_server.lock`：
    - `ops/start_driver.sh`
    - `ops/systemd/chatgptrest-driver.service`
  - `maint_daemon` / `repair.autofix` 的 `restart_driver` 行为改为：
    - 若检测到 systemd unit `LoadState=loaded`，systemd 重启失败时**禁止脚本兜底直启**，避免 orphan + lock 冲突。
  - runbook 增加“MCP 启动失败”专门排障步骤（含 singleton lock 诊断）。
- Files:
  - `ops/start_driver.sh`
  - `ops/systemd/chatgptrest-driver.service`
  - `ops/maint_daemon.py`
  - `chatgptrest/executors/repair.py`
  - `docs/runbook.md`
  - `docs/issues_registry.yaml`
  - `docs/repair_agent_playbook.md`

58) **CDP 端口被非 DevTools 监听劫持（常见于 9222）导致误判 `auth`/MCP 启动异常**
- Symptom:
  - `chatgpt_web` 反复报 `auth/blocked`，但同一 profile 实际已登录；
  - `chatgpt_web`/`codex_apps` MCP 初始化偶发失败（含 `Unexpected content type: None`）；
  - `chatgptrest-chrome.service` 日志出现持续 `CDP probe failed`，并提示端口已被占用。
- Root cause:
  - `127.0.0.1:9222` 被其他会话/转发进程占用，但并非 Chrome DevTools 端点；
  - driver 继续连错端口，导致页面探测与 blocked 判定全部失真。
- Fixes:
  - driver systemd 单元改为通过 `ops/start_driver.sh` 启动，统一默认：
    - `CHATGPT_CDP_URL` 若未显式配置，则由 `CHROME_DEBUG_PORT` 推导（默认 9222）；
    - 自动落盘 `CHATGPT_BLOCKED_STATE_FILE` 到 `state/driver/`。
  - chrome systemd 单元显式支持 `CHROME_DEBUG_PORT`（可在 env 中改为 9226+）。
  - `repair` / `maint_daemon` 默认 CDP 地址改为优先读取 `CHROME_DEBUG_PORT`，减少“工具诊断看错端口”。
  - driver 增加验证页自动点选尝试（`CHATGPT_AUTO_VERIFICATION_CLICK=1` 默认开启），失败后才进入人工步骤。
- Files:
  - `ops/start_driver.sh`
  - `ops/systemd/chatgptrest-driver.service`
  - `ops/systemd/chatgptrest-chrome.service`
  - `chatgpt_web_mcp/_tools_impl.py`
  - `chatgptrest/executors/repair.py`
  - `ops/maint_daemon.py`
  - `docs/runbook.md`
  - `docs/repair_agent_playbook.md`

59) **Gemini Deep Research 工具切换 UI 漂移导致误报 `tool state unknown after toggle`**
- Symptom:
  - `gemini_web.ask`（`deep_research=true`）在 send 阶段报错：
    - `RuntimeError: Gemini tool state unknown after toggle: (Deep Research|深入研究|深度研究)`
  - 已复现样本：
    - `c8c8c57d89f54ef88c45cc1741c316ba`
    - `0c144d84645742f286ae7723a4a7e31d`
- Root cause:
  - Gemini 新 UI 在部分会话下不再稳定暴露 `aria-checked` / `is-selected`；
    选中态改由 `toolbox-drawer-item-deselect-button`、`Tools` 按钮 `has-selected-item` 以及 prompt placeholder 体现。
  - 旧校验仅依赖 checkbox 属性，导致“已切换成功但状态读取为 unknown”的假失败。
- Fixes:
  - 扩展工具选中态判定：
    - `toolbox-drawer-item-deselect-button` 视为选中；
    - 增加 fallback：从 selected chip / `Tools` 按钮 class / placeholder 推断状态；
    - 支持负向推断（可判定“未选中”，不再只会返回 `True`）。
  - 收紧工具定位 selector，移除过宽 `button` 文本匹配，降低误点概率。
  - 增加回归测试覆盖：
    - fallback 推断 `True/False` 两路径；
    - placeholder 变体匹配；
    - deselect chip class 识别。
- Files:
  - `chatgpt_web_mcp/providers/gemini/core.py`
  - `tests/test_gemini_mode_selector_resilience.py`
  - `docs/runbook.md`

60) **send 阶段粘滞上传失败导致 `max_attempts` 扩展循环；新增护栏并沉淀为分类化 runbook**
- Symptom:
  - 同一 job 在 send/upload 阶段反复报：
    - `TargetClosedError`
    - `Locator.set_input_files ... input[type='file'] ... page/context/browser has been closed`
  - `max_attempts_extended` 持续累积，作业长期不终态，形成“重试风暴”。
- Root cause:
  - 旧逻辑对 retryable send 失败支持自动扩展 `max_attempts`，但缺少“同类粘滞错误”上限判断；
    对 `set_input_files` 这类稳定失败场景会持续放大重试。
- Fixes:
  - `job_store.store_retryable_result` 增加粘滞上传关闭面护栏：
    - 命中 `TargetClosedError + set_input_files/input[type=file]` 时，跳过 max-attempt 扩展；
    - 记录事件 `max_attempts_extension_skipped`（含 `guard_reason=sticky_upload_surface_closed`）；
    - 终态化为 `MaxAttemptsExceeded`，避免无限循环。
  - 新增扩展次数上限参数：
    - `CHATGPTREST_RETRYABLE_SEND_MAX_EXTENSIONS`（默认 `1`）
  - runbook / repair playbook 新增“按故障类别（R1-R6）处置”与“Codex 唤醒执行合同”。
- Files:
  - `chatgptrest/core/job_store.py`
  - `tests/test_leases.py`
  - `docs/runbook.md`
  - `docs/repair_agent_playbook.md`
  - `AGENTS.md`

## Files Most Likely to Matter (hotspots)

- `chatgpt_web_mcp/server.py` (ChatGPT/Gemini Web automation + guardrails)
- `chatgptrest/executors/chatgpt_web_mcp.py` (current driver boundary)
- `chatgptrest/executors/gemini_web_mcp.py` (Gemini Web + Drive attachments)
- `chatgptrest/executors/repair.py` (`repair.check` diagnostics)
- `chatgptrest/worker/worker.py` (phase handling + export fallback)
- `chatgptrest/core/job_store.py` (leases + phase transitions)
- `chatgptrest/core/db.py` (schema)
- `docs/contract_v1.md` (public contract)
- `docs/runbook.md` (ops guidance)

## Open Considerations (post driver-merge)

- The two-phase scheduler assumes a thin driver that can do `ask` (send) and `wait` separately.
- With the driver merged, careful tab/Chrome lifecycle control is needed to avoid over-allocating tabs on long waits.
- The wait refresh path is implemented inside the embedded driver (`chatgpt_web_wait` refresh-on-timeout) plus server-side export recovery; keep it conservative to avoid UI load/wind-control amplification.
