# 2026-03-09 Wait Priority And Cold Client Quickstart

## What changed

### 1. Wait-lane priority for Gemini DR with a stable thread URL

Files:

- `chatgptrest/core/job_store.py`
- `tests/test_claim_priority.py`

Change:

- Added a narrow `_build_claim_order_by()` helper inside `claim_next_job()`.
- The priority only applies when `phase='wait'`.
- Order is now:
  1. `gemini_web.ask` + `deep_research=true` + stable `conversation_id`
  2. any wait job with stable `conversation_id`
  3. other wait jobs
  4. preserve historical FIFO (`not_before`, `created_at`) inside each bucket

Why:

- Recent live failures split into two families:
  - `WaitNoThreadUrlTimeout` before a stable thread URL exists
  - plan-stub / preamble style `needs_followup` after a stable thread URL already exists
- The second family was being mixed into a large generic wait backlog.
- This change biases the wait worker toward jobs that can make progress immediately without rewriting worker state machines.

### 2. Fixed entry doc for fresh Codex clients

Files:

- `docs/codex_fresh_client_quickstart.md`
- `docs/runbook.md`
- `docs/client_projects_registry.md`
- `ops/codex_cold_client_smoke.py`
- `tests/test_codex_cold_client_smoke.py`

Change:

- Added one canonical quickstart for a fresh Codex client.
- Wired the cold-client harness prompt to explicitly include that quickstart.
- Recorded a runtime caveat discovered by live acceptance:
  - loopback-blocked sandboxes may need MCP fallback
  - current stateless MCP runtime may not support background wait

Why:

- A new Codex session should not depend on hidden maintainer context.
- The acceptance lane should prove the client can discover the right path, not rely on oral tradition.

## Validation

### Unit / targeted regression

Passed:

- `PYTHONPATH=. ./.venv/bin/pytest -q tests/test_claim_priority.py tests/test_codex_cold_client_smoke.py tests/test_pause_queue.py tests/test_conversation_url_upgrade.py`
- `./.venv/bin/python -m py_compile chatgptrest/core/job_store.py ops/codex_cold_client_smoke.py tests/test_claim_priority.py tests/test_codex_cold_client_smoke.py`

### Live deploy

Service action:

- restarted `chatgptrest-worker-wait.service`
- final stable state after forced drain/reset:
  - `ActiveState=active`
  - `SubState=running`
  - `ActiveEnterTimestamp=Mon 2026-03-09 13:06:11 CST`

### Live Gemini DR smoke (service-side)

Job:

- `fb3f01973e3048069738b21a6ffab78f`

Observed sequence:

- `13:06:31` job created and claimed by send worker
- `13:07:51` `conversation_url_set` -> `https://gemini.google.com/app/3f6e396581639a46`
- `13:07:51` `phase_changed` `send -> wait`
- `13:07:51` `wait_requeued`
- `13:09:28` wait worker reclaimed the same job

Interpretation:

- The post-send path reached a stable Gemini thread URL.
- The wait job re-entered the queue and was reclaimed by the wait worker after becoming ready.
- This is the live evidence that the new wait-lane priority is active on a real Gemini DR path.

Artifacts:

- `artifacts/jobs/fb3f01973e3048069738b21a6ffab78f/events.jsonl`

### Live cold-client acceptance

Artifact dir:

- `artifacts/cold_client_smoke/20260309_130522/`

Observed behavior from nested Codex transcript:

- It read the new `docs/codex_fresh_client_quickstart.md`
- It preferred the documented wrapper path first
- The wrapper failed with loopback transport denial:
  - `URLError: <urlopen error [Errno 1] Operation not permitted>`
- It then followed the repository-documented MCP fallback path
- It submitted a real Gemini job:
  - `c02f47006bfc43b48d0ebba1c6792b8d`
- That job reached:
  - stable `conversation_url = https://gemini.google.com/app/eebb19d337d8d30f`
  - `phase=wait`

Important new finding:

- Under the current ChatgptREST MCP stateless runtime, `chatgptrest_job_wait` could not start a background watcher and fell back to bounded foreground wait.
- This is now documented in the quickstart and runbook as a runtime limitation, not a client misuse.

Artifacts:

- `artifacts/cold_client_smoke/20260309_130522/codex.exec.jsonl`
- `artifacts/jobs/c02f47006bfc43b48d0ebba1c6792b8d/events.jsonl`

## Notes

- The outer `ops/codex_cold_client_smoke.py` process may outlive the useful evidence window when the nested Codex chooses a long bounded wait. The acceptance evidence above was already sufficient before outer process completion.
