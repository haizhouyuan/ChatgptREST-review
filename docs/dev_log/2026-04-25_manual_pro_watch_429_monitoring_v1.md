# 2026-04-25 Manual Pro Watch and 429 Monitoring v1

## Purpose

The user reported repeated human-visible ChatGPT Pro 429 / frontend cooldown popups while they were using Pro manually. The goal was to stop ChatgptREST from touching the shared ChatGPT Web session, monitor for three hours, and identify adjacent failure modes that could still produce confusing Pro evidence gaps.

This incident is separate from any one client project. Paperclip, Labebe, Multica/Hermes, and AOP review jobs were symptoms because they depended on the same shared ChatGPT Web automation channel.

## Monitoring Window

- Start: `2026-04-25T19:10:35+08:00`
- End: `2026-04-25T22:10:36+08:00`
- Duration: `10800.192` seconds
- Samples: `181`
- Artifacts:
  - `artifacts/monitor/manual_pro_watch/20260425_191035/summary.json`
  - `artifacts/monitor/manual_pro_watch/20260425_191035/samples.jsonl`
  - `artifacts/monitor/manual_pro_watch/20260425_191035/alerts.jsonl`

## Root Cause Chain

The first export-side fixes were necessary but incomplete:

- Backend conversation export 429 could be hidden by DOM fallback and was fixed by shared cooldown handling.
- Completion-time export switched to DOM-only during ChatGPT backend cooldown.
- The frontend rate-limit modal was promoted from a generic transient UI error to a first-class `frontend_rate_limit` blocked state.

The remaining gap was northbound submission:

- Public MCP / REST submit could still create new ChatGPT Web jobs while the shared browser session was already rate limited.
- The first API gate covered `chatgpt_web.ask`, but direct low-level `chatgpt_web.conversation_export` / `chatgpt_web.extract_answer` submissions could still reach the same ChatGPT Web driver/export path.
- That meant a user could see Pro 429 even if a specific foreground Codex was not obviously using ChatgptREST.

## Fixes Applied

Committed fixes:

- `29fe7cb8 Block ChatGPT submits during frontend rate limits`
- `d055adb9 Gate all ChatGPT web submits during frontend holds`

The effective behavior is now:

- New `chatgpt_web.*` submissions are rejected at API submit time while a frontend hold is active.
- The rejection returns HTTP 429 with structured detail, `job_created=false`, `reason=frontend_rate_limit`, `blocked_until`, and `safe_next_action`.
- Existing idempotency keys still replay their existing job view instead of creating duplicates.
- Non-ChatGPT providers, including Gemini, are not blocked by this ChatGPT-specific gate.

Related wrapper / error-contract commits present after this incident:

- `0797fb16 mcp: require explicit cancel reasons when configured`
- `5c2beaef mcp: surface structured wrapper cooldown errors`

## Runtime Containment

During the watch window:

- Stopped `chatgptrest-driver.service`.
- Stopped `chatgptrest-worker-send.service`.
- Stopped `chatgptrest-worker-wait.service`.
- Left `chatgptrest-api.service` and `chatgptrest-mcp.service` active so clients receive structured 429 rather than connection errors.
- Added temporary user systemd hold drop-ins requiring `/run/user/1000/chatgptrest_manual_pro_watch_allow_web_automation` before driver/send/wait can start.
- Added API drop-in:
  - `CHATGPTREST_CHATGPT_FRONTEND_BLOCK_STATE_FILE=/vol1/1000/projects/ChatgptREST/state/driver/chatgpt_blocked_state.json`
  - `CHATGPTREST_BLOCK_CHATGPT_SUBMIT_ON_FRONTEND_RATE_LIMIT=1`
- Seeded frontend hold state:
  - DB cooldown key: `chatgpt_web_frontend_rate_limit`, until `2026-04-25 22:34:43 +0800`
  - Driver block state: `state/driver/chatgpt_blocked_state.json`, until `2026-04-25 22:39:53 +0800`

At the end of the watch:

- `chatgptrest-driver.service`: inactive
- `chatgptrest-worker-send.service`: inactive
- `chatgptrest-worker-wait.service`: inactive
- `chatgptrest-api.service`: active
- `chatgptrest-mcp.service`: active
- Active web jobs: 0

## Monitoring Findings

Alert counts:

- `unexpected_automation_unit_active`: 6
- `chatgpt_web_tool_call_observed`: 3
- `local_health_probe_failed`: 2
- `interesting_log_line`: 1

Important events:

- `19:33-19:41`: background ChatGPT Web actions were observed from queued Pro jobs. This confirmed the user-visible 429 was not explained by manual browser usage alone.
- `20:11`: API/MCP health briefly failed during controlled restart; no recurrence afterward.
- `21:21-21:23`: another Codex tried a ChatGPT Pro submission. The first attempt failed with file-path policy 403. After copying files into the allowed tree, the new submit was blocked by the frontend gate with HTTP 429 and `job_created=false`; this is the expected protected behavior.
- After the submit gate and runtime holds were active, no new ChatGPT Web tool calls were observed through the end of the three-hour window.

The dashboard log included `GET /dashboard/.env` from an external-looking IP, returning `401 Unauthorized`. The active API/MCP/dashboard surfaces are loopback-bound for the relevant control paths, and this event did not touch ChatGPT Web. It remains useful operational noise to watch, but it was not the Pro 429 cause.

## Paperclip Pro Evidence Status

Paperclip demo local configuration work is separate from the Pro evidence-chain problem.

Observed Pro jobs:

- Initial job: `1f4578ec01b941f590232ff33def6fe5`
- Conversation: `https://chatgpt.com/c/69eca67c-de2c-83e8-a93d-932479d5ac3e`
- Follow-up job: `c97eba7bc8cc42e89de666ea8331f5db`

The initial job produced provisional export traces showing that Pro inspected the package, but it was canceled before a complete final review answer was captured. The follow-up did not send because the ChatGPT frontend channel entered cooldown/rate-limit.

Conclusion:

- The provisional Pro traces can be used as weak diagnostic signal.
- They cannot be cited as a complete external Pro review verdict.
- Local fixes inspired by that signal still need local verification and, if external evidence is required, a fresh Pro run after the automation channel is intentionally resumed.

## Similar Failure Modes Identified

- Submit gate must cover all `chatgpt_web.*` kinds, not only `chatgpt_web.ask`.
- Export fallback success must not clear a backend 429 cooldown.
- Completion guards must continue treating short Pro confirmations as non-final.
- Wrapper clients must surface structured 429/cooldown detail instead of masking it as JSON decoding failure.
- Cancel operations need explicit reasons so incident cleanup remains auditable.
- MCP client configuration drift can cause false failures; `ops/check_public_mcp_client_configs.py --fix` repaired Antigravity MCP transport during this incident.
- Long-running maintenance or projection services can consume excessive resources; `chatgptrest-monitor-projection-refresh.service` was stopped during the watch after high memory use.
- One-off monitoring SQL used a projected `phase_detail` field as if it were a DB column. That caused the monitor DB summary to report `OperationalError: no such column: phase_detail`. Other monitoring channels remained valid, but future reusable monitors should query the canonical job/result projection or derive phase detail from events.

## Validation

Code validation completed before the runtime watch settled:

```bash
PYTHONPATH=. ./.venv/bin/python -m py_compile chatgptrest/api/routes_jobs.py tests/test_chatgpt_frontend_submit_gate.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_chatgpt_frontend_submit_gate.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_jobs_write_guards.py tests/test_low_level_ask_guard.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_contract_v1.py tests/test_ask_contract.py
PYTHONPATH=. ./.venv/bin/python scripts/check_doc_obligations.py --diff HEAD
```

Live probes also confirmed:

- New `chatgpt_web.ask` submit returns HTTP 429 with `job_created=false`.
- New direct `chatgpt_web.conversation_export` submit returns HTTP 429 with `job_created=false`.
- API health and public MCP health are active while driver/send/wait remain inactive.

## Resume Procedure

Do not resume ChatGPT Web automation automatically after this incident. Resume should be an explicit operator action after the user is no longer manually using Pro.

Minimum controlled resume:

```bash
rm -f /vol1/1000/projects/ChatgptREST/state/driver/chatgpt_blocked_state.json
touch /run/user/1000/chatgptrest_manual_pro_watch_allow_web_automation
systemctl --user daemon-reload
systemctl --user restart chatgptrest-driver.service chatgptrest-worker-send.service chatgptrest-worker-wait.service
```

Safer alternative: remove the temporary hold drop-ins instead of using the sentinel, then reload systemd and start only the specific unit needed for a controlled test.

## Residual Work

- Decide whether ChatGPT Web automation should stay disabled by default during known manual Pro use windows.
- Add or promote a reusable monitor that avoids DB schema assumptions and reads canonical job projections instead of raw columns.
- Clean up stale `needs_followup` jobs separately; do not re-open them automatically during a Pro cooldown incident.
- Re-enable or optimize `chatgptrest-monitor-projection-refresh.service` only after its memory behavior is understood.
- Re-run a single controlled Pro review only after the user explicitly approves resuming ChatGPT Web automation.
