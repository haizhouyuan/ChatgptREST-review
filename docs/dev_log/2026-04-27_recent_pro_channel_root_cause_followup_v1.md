# 2026-04-27 Recent Pro Channel Root Cause Follow-up v1

## Investigation Window

Reviewed runtime state and artifacts after the Codex2 to Codex1 handoff, focusing on recent client-visible ChatGPT Web / Pro failures rather than repeating the earlier 429-only framing.

Evidence checked:

- `journalctl --user` for API, MCP, driver, send worker, and wait worker since 2026-04-26 08:00 CST.
- `artifacts/monitor/api_rejections/20260426.jsonl` and `20260427.jsonl`.
- `jobs`, `job_events`, `cooldowns`, and `client_issues` in `state/jobdb.sqlite3`.
- Recent job artifacts for `927e6245...`, `7cf5541c...`, `d2444740...`, `7ad0ce07...`, `c4e2352...`, and `ca0d32d8...`.

## Findings

No fresh ChatGPT backend/export `429` or Cloudflare cooldown was observed in the reviewed slice. The recent failures were adjacent reliability failures on the same Pro automation channel:

1. `chatgpt_web.extract_answer` completed with a one-character newline answer for `c4e2352e61d44e21b4806d0e7c3d718e`, even though its forced conversation export contained a later `14653` character assistant answer.
2. Pro wait jobs `7cf5541cd6e24238b3913d4ba3acf712` and `d24447409bc840c8a3f27ae45a0c8767` reached `WaitNoProgressTimeout` while ChatGPT was still doing active internal finalization. The final answer for that conversation appeared later in the export.
3. Recent `403 file_paths_outside_allowed_directory` entries were correctly blocked by admission control. They are not provider failures, but they show clients still need to stage review packets under sanctioned upload roots or explicitly configure extra allowed roots.
4. Local `401 missing_or_invalid_bearer_token` entries came from maintenance probes without loaded tokens. They did not create jobs.
5. Gemini `GeminiBlankSendTimeout` remains a separate provider-lane issue and was already fail-closed instead of retry-storming.

## Root Causes

### Extract-answer finality was too weak

`chatgpt_web.extract_answer` internally uses conversation export and has no original `question`. The worker's generic reconciliation path still called the export extractor with `allow_fallback_last_assistant=false`, so it could not select the latest assistant response when no question match existed.

After the export, the raw executor answer was blank. Because `min_chars=0`, the worker allowed the blank/newline artifact to be stored as `completed/final`. This repeated the same class of bug as earlier short-answer evidence failures: a structurally successful provider/export operation was treated as a usable answer without content-quality finality.

### Pro active-finalization timeout was too short for the runtime override

The code default for `CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS` is conservative, but the live worker environment overrides it to `300` seconds. That is acceptable for ordinary blank waits, but too aggressive for Pro/thinking threads when the export explicitly shows live active finalization (`active_count` / `in_progress_count` > 0).

In the observed jobs, progress reached a stable internal-tool state around 55%, then the worker timed out after roughly 7 minutes of no progress. The final assistant text appeared later, so the timeout was a false terminal decision caused by using one generic stall threshold for both ordinary no-progress and active Pro finalization.

## Fix Implemented

1. `*.extract_answer` jobs now allow export fallback to the latest non-empty assistant message when no original question is available.
2. `*.extract_answer` jobs now fail closed to `needs_followup / ExtractAnswerEmpty` if the export still has no extractable assistant response. They no longer finalize blank or whitespace-only answer artifacts.
3. Pro/thinking wait jobs with live active-finalization export state now use `CHATGPTREST_WAIT_ACTIVE_FINALIZATION_NO_PROGRESS_TIMEOUT_SECONDS` before escalating to `WaitNoProgressTimeout`.
4. `docs/runbook.md` documents the new active-finalization grace knob and interpretation.

## Validation

Ran:

```bash
PYTHONPATH=. ./.venv/bin/python -m py_compile chatgptrest/worker/worker.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_worker_and_answer.py -k 'extract_answer or active_finalization or no_progress'
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_conversation_export_reconcile.py tests/test_longest_candidate_extraction.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_worker_and_answer.py tests/test_conversation_export_reconcile.py tests/test_longest_candidate_extraction.py tests/test_low_level_ask_guard.py
```

All targeted tests passed.

## Runtime Rollout Note

A Labebe Pro job was active during this fix (`c33acc4b812e41cea92f4e317efad589`). To avoid interrupting client usage, do not restart the ChatGPT workers mid-job unless the job is already terminal or the operator accepts a short wait-worker recycle.

After active Pro jobs drain, restart the affected workers so the new worker code is live:

```bash
systemctl --user restart chatgptrest-worker-send.service chatgptrest-worker-wait.service
```

The restart is for code pickup only; it is not needed for API/MCP availability.
