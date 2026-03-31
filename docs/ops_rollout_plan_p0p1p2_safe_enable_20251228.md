# ChatgptREST P0/P1/P2 Rollout Plan (Safe-Enable First)

Date: 2025-12-28

Goal: merge/land all review-driven improvements while **only enabling the “safe, low side‑effect” behaviors first**, then soak/observe, then progressively enable the “automatic actions” (repair/restart/cleanup) behind explicit guards.

This document exists to avoid losing context to chat history compression.

---

## Definitions (important)

- **Land**: code exists in repo, documented, testable, but may be disabled by default.
- **Enable**: behavior is active in production (env defaults / startup scripts / systemd timers turned on).
- **Side-effect actions**: anything that changes system state automatically (restarting Chrome, rewriting answers, pruning DB, aggressive export retries). These are the primary operational risk.

Rule of thumb:
- **Land everything** is fine.
- **Enable everything immediately** is risky.

---

## Current stack (ports)

- Chrome (CDP, logged-in): `http://127.0.0.1:9222`
- ChatgptREST driver MCP (internal): `http://127.0.0.1:18701/mcp`
- ChatgptREST REST API: `http://127.0.0.1:18711`
- ChatgptREST MCP adapter: `http://127.0.0.1:18712/mcp`

---

## Phase 0 — Implement + Enable “Safe Core” (do now)

These directly reduce duplicate prompts / data loss / queue stalls with minimal new side-effects.

### P0-1 Zero-duplicate hard check (enable)

Objective: **never send a second user message** for the same logical request when the first one was already sent.

Plan:
- In `chatgptrest/executors/chatgpt_web_mcp.py`, before any “fallback preset” resend:
  - call driver `chatgpt_web_idempotency_get(primary_key)` and treat `record.sent==true` or `record.conversation_url` as a hard “do not resend”.
  - if hard “sent”, force `status=in_progress` and go to wait loop instead of fallback ask.
  - record `_fallback_suppressed_reason` in meta for forensics.

Success signal:
- In `artifacts/jobs/<job_id>/events.jsonl`, you should see `fallback_suppressed` (or similar meta markers) instead of a second `sent` action in the conversation.

### P0-2 Persist driver critical state paths (enable)

Objective: avoid “restart resets idempotency / blocked state → duplicate sends / misdiagnosis”.

Plan:
- In `ops/start_driver.sh` set defaults to persistent paths (under `state/driver/`):
  - `MCP_IDEMPOTENCY_DB`
  - `CHATGPT_BLOCKED_STATE_FILE`
  - `CHATGPT_GLOBAL_RATE_LIMIT_FILE`
- Ensure directories exist and are writable.

Success signal:
- Driver `chatgpt_web_rate_limit_status.global_rate_limit_file` points under `state/driver/`.
- `state/driver/mcp_idempotency.sqlite3` exists and keeps growing across driver restarts.

### P0-3 Throttle conversation export attempts (enable, conservative)

Objective: export fallback fixes “refresh才出答案”，但不能变成高频 UI 拉取造成风控/资源压力。

Plan:
- Add **per-job export cooldown + backoff**:
  - If export succeeded in the last `~120s`, skip.
  - If export failed recently, backoff (e.g. 60s → 120s → 300s) and skip until next window.
  - Completion-time "force" only bypasses the OK cooldown; it **must not** bypass failure backoff (`cooldown_until`).
- Add an optional **global export pacing** key in the existing `rate_limits` table (separate from send pacing).

Success signal:
- No tight loop of `conversation_export_failed` events for a single job.
- Wait workers requeue smoothly and don’t overwhelm the driver / Chrome.

### P2-4 Make worker JSON snapshots atomic (enable)

Objective: avoid half-written JSON in artifacts when processes crash.

Plan:
- Make worker-written JSON snapshots use atomic write (`write tmp -> rename`) for:
  - `mihomo_delay_snapshot.json` (and any other direct JSON write sites).

Success signal:
- No malformed JSON in incident packs / artifacts under normal crashes.

### P0-4 Send-stage timeout cap + “no conversation_url yet” requeue (enable)

Objective: avoid a single send worker being pinned for 20–30 minutes (attachment uploads / slow UI) while still preventing duplicate user messages.

Plan:
- Default-cap send stage when `params.send_timeout_seconds` is omitted:
  - `CHATGPTREST_DEFAULT_SEND_TIMEOUT_SECONDS` (default `180`)
- If the driver reports `status=in_progress` but conversation_url is missing:
  - keep the job `in_progress` and requeue it into `phase=wait`
  - wait phase polls driver idempotency until conversation_url appears (no resend)

Success signal:
- Send worker stays responsive (does not hold a lease for > a few minutes in common cases).
- No duplicated user messages in the UI for the same job_id/idempotency.

### P0-5 Deep Research ack + min_chars completion guard (enable)

Objective: avoid a false `completed` when the captured assistant message is only a short “我将开始调研/稍后请查收” acknowledgement (or when the answer is shorter than the caller’s `min_chars`).

Plan:
- Worker-side guard in `chatgptrest/worker/worker.py`:
  - if `deep_research=true` and the captured answer matches the ACK patterns, downgrade `completed → in_progress` and requeue.
  - if `min_chars>0` and the captured answer is shorter than `min_chars`, downgrade `completed → in_progress` and requeue.
  - record event `completion_guard_downgraded` with a short preview for forensics.

Success signal:
- You no longer see “short ack answers” stored as `completed`.
- `events.jsonl` contains `completion_guard_downgraded` for those cases, and the job keeps waiting for the real report.

### P1-1 Wait refresh cooldown (enable, conservative)

Objective: mitigate “刷新才出” without turning long waits into repeated refreshes (wind-control / UI load risk).

Plan:
- Embedded driver `chatgpt_web_wait` refresh is guarded by a persistent state file:
  - `CHATGPT_WAIT_REFRESH_STATE_FILE` (default under `state/driver/`)
  - `CHATGPT_WAIT_REFRESH_MIN_INTERVAL_SECONDS` (default `900`)
- Same conversation should refresh at most once per window (across wait slices).

Success signal:
- `chatgpt_web_wait` output includes `wait_refresh_guard` showing cooldown decisions.

### P2-3 Job-scoped debug artifacts (enable)

Objective: make “job_id ↔ evidence” linking trivial when investigating intermittent UI issues.

Plan:
- When driver returns debug artifacts (png/html/txt), copy them into:
  - `artifacts/jobs/<job_id>/debug/`
- Emit a `debug_artifacts_attached` event listing the copied paths.

---

## Phase 1 — Soak / Observe (time window: 24h–7d, low traffic)

Principles:
- Prefer **read-only monitoring**; avoid additional “test prompts”.
- If you must test, use human-like low-risk prompts (see `ops/smoke_test_chatgpt_auto.py`), and keep frequency low (still obey 61s).

What to watch:
- `blocked/cooldown` rate and reasons
- `send_throttled` occurrences (pacing working)
- `conversation_export_failed` rate (should be low, not repeated tight loops)
- `tab_stats` (tab limit hits should stay near zero)
- `stuck in_progress` jobs (should surface as `needs_followup`/`cooldown` rather than blocking the queue)
- Proxy health (`artifacts/monitor/mihomo_delay/mihomo_delay_YYYYMMDD.jsonl`)

Convenience tooling:
- `ops/maint_daemon.py` (resident, no prompt send) → incidents in `artifacts/monitor/maint_daemon/incidents/`
- `ops/monitor_chatgptrest.py` → DB event stream JSONL
- `ops/summarize_monitor_log.py` → one-file summary of a soak run

Rollback rules during soak:
- If you see duplicate user messages in UI for the same job_id → disable/rollback P0-1 changes immediately.
- If you see export storms (many exports per minute) → increase cooldown/backoff, or temporarily disable export fallback and rely on wait.

---

## Phase 2 — Land “Automatic Actions”, keep Disabled by Default (do after Phase 0 merge)

These should be merged with flags, but **NOT enabled** until Phase 1 looks clean.

### P1-3 DB lifecycle tooling (land; disabled)

Add `ops/cleanup_db.py`:
- Default: `--dry-run` prints what would be deleted.
- Only target terminal jobs (completed/error/canceled/blocked/cooldown/needs_followup) older than N days.
- Provide optional archive to `artifacts/monitor/db_archives/`.

Do NOT enable timer until at least 3 dry runs show safe behavior.

### P1-4 Stuck job “self-heal actions” (land; disabled)

Keep a strict “no new prompt” constraint. Allowed actions:
- Evidence pack capture
- Chrome/CDP restart only when:
  - no send-phase job is running, AND
  - continuous failures N times, AND
  - cooldown window not violated

### P2-2 Rolling Chrome restart by metrics (land; disabled)

Only enable after:
- stable tab_stats,
- low stuck rate,
- and clear safeguards are in place (no active send, backoff/cooldown, max once per X hours).

### Repair daemon (land as detect-only; disabled for writes)

MVP design (initially read-only):
- Trigger: detect inconsistency (e.g., answer.md is tiny vs conversation.json) for completed jobs.
- Action: create incident pack with evidence + suggested command to repair (no automatic rewrite).
- Later (opt-in): allow “safe rewrite” only when source of truth exists (e.g., answer_id or export reconciliation).

---

## Phase 3 — Enable “Automatic Actions” progressively (after Phase 1)

Enable order (one change at a time, soak after each):
1) DB cleanup timer (weekly/daily, low-peak)
2) Repair daemon “write mode” (only for known-safe repair classes)
3) Rolling Chrome restart (very conservative thresholds)

---

## Operator checklist (quick)

- Health: `curl -fsS http://127.0.0.1:18711/healthz`
- Driver stats: `chatgpt_web_rate_limit_status`, `chatgpt_web_tab_stats`
- Logs:
  - `logs/chatgptrest_api.log`
  - `logs/chatgptrest_worker.log`
  - `artifacts/monitor/maint_daemon/maint_YYYYMMDD.jsonl`
  - `artifacts/monitor/mihomo_delay/mihomo_delay_YYYYMMDD.jsonl`
