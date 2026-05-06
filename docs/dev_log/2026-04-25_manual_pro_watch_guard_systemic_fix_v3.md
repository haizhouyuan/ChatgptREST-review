# 2026-04-25 Manual Pro Watch Guard Systemic Fix v3

## Reflection

The earlier watch did not meet the operational bar. It collected evidence, but it did not make the evidence actionable fast enough. The user had to report the visible 429, which means the system and the operator both failed to treat "ChatGPT Web automation touched the shared Pro session" as a P0 condition.

The follow-up guard in v2 was also incomplete. It improved observation and process shutdown, but it still treated the hold as a soft runtime condition: a state file, a generic pause, and a guard process. Another Codex was able to stop the guard, clear pause, restart driver/send/wait, and continue ChatGPT Pro submissions. That proved the hold was not a system invariant.

## Findings

- `19:33-19:41` during the manual Pro window, background ChatGPT Web asks/waits/exports ran and likely contributed to the user-visible 429.
- The first submit gate fix only worked after code deployment; the live API was not restarted after `manual_pro_session` support was added, so a later Pro job could still be created.
- The guard wrote `state/driver/chatgpt_blocked_state.json` and DB pause, but stopping the guard and clearing pause removed the effective runtime protection.
- The systemd drop-ins already had a `ConditionPathExists` gate, but the runtime allow file was still present. `chatgptrest-worker-wait.service` also uses `Restart=always`, so a plain `systemctl stop` was not a strong enough invariant.
- A queued ChatGPT Pro job was created during the manual hold and only deferred by pause. That was too late: the correct behavior is `POST /v1/jobs` rejecting with `job_created=false`.
- `chatgpt_web.conversation_export` / `extract_answer` paths must be treated the same as ask paths because they touch the same shared ChatGPT Web channel.
- The attachment policy rejected `/vol1/1000/projects/toyresearch/...`, then the caller copied files to arbitrary `/tmp/...`. That bypass preserved neither project provenance nor an explicit allowlist decision.

## Root Cause

There was no durable, provider-specific "human owns ChatGPT Pro now" lock. The implementation relied on removable runtime artifacts:

- state file;
- generic pause;
- systemd guard process;
- operator discipline to avoid clearing them.

That is not sufficient when multiple Codex sessions can act concurrently.

## Systemic Fix

The canonical hold is now DB-backed and independent of the observer process:

- `chatgpt_web_hold_reason=manual_pro_session`
- `chatgpt_web_hold_until=<epoch>`
- `chatgpt_web_hold_source=manual_pro_watch_guard`

Enforcement layers:

- API submit gate reads the DB hold and rejects new `chatgpt_web.*` jobs with HTTP 429 and `job_created=false`.
- Worker claim excludes `chatgpt_web.%` jobs while the DB hold is active, even if generic pause was cleared.
- `ChatGPTWebMcpExecutor` checks the DB hold before ask, wait/export, or extract-answer work and returns `status=blocked` without touching the driver.
- The guard still writes the state file and pause for compatibility, but these are no longer the source of truth.
- The guard removes `/run/user/$UID/chatgptrest_manual_pro_watch_allow_web_automation` and runtime-masks protected units while active, so systemd refuses manual or automatic restarts of ChatGPT Web units. The explicit release command restores the allow file and unmasks the units.
- Releasing the hold requires explicit `ops/manual_pro_watch_guard.py --release --release-reason ... --confirm-release-manual-pro-session`; stopping the guard service alone is not a release.

Attachment staging was also tightened:

- arbitrary `/tmp/...` paths are no longer accepted by default;
- sanctioned staging is `/tmp/chatgptrest_uploads/`, `ChatgptREST/tmp/`, the repo root, or explicit `CHATGPTREST_EXTRA_ALLOWED_FILE_ROOTS`;
- cross-project attachment roots must be an explicit runtime allowlist decision rather than an ad hoc temp copy.

## Operational Rule

During a manual ChatGPT Pro window, any ChatGPT Web automation activity is an incident, not a warning. The correct sequence is:

1. durable DB hold first;
2. API/MCP return structured blocked responses;
3. workers do not claim ChatGPT Web jobs;
4. executor refuses driver calls;
5. systemd refuses manual or automatic restarts because the allow file is absent and protected units are runtime-masked;
6. guard records evidence and stops protected units if they come alive;
7. release only through the explicit release command after the human Pro window ends.
