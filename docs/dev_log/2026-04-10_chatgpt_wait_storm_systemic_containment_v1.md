# 2026-04-10 ChatGPT Wait Storm Systemic Containment v1

## Why this note exists

This is the broader follow-up to the single contaminated-thread fix. The visible incident was
ChatGPT Web showing:

- `Too many requests`

But the real problem was wider than one bad job. Historical job/event data showed multiple storm
families that could all amplify Web pressure if we only patched one branch at a time.

## Incident families found

From `state/jobdb.sqlite3`:

- `wait_requeued`: `465481`
- `completion_guard_downgraded`: `12714`

Top downgrade reasons:

- `answer_quality_suspect_short_answer`: `10737`
- `answer_too_short_for_min_chars`: `1085`
- `conversation_export_missing_reply`: `803`
- `answer_quality_suspect_context_acquisition_failure`: `40`
- `tool_payload_not_final`: `27`
- `deep_research_ack`: `22`

This means the biggest storm family was not just export lag. It was repeated shallow-answer
downgrades that kept re-entering `wait`.

## Root causes (system-level)

### 1) Top-level ask could silently reuse an old ChatGPT thread

When `conversation_url` was absent, the send path only made a best-effort attempt to click
`New chat`. If that failed, execution could continue on an existing `/c/...` thread.

That allowed unrelated top-level jobs to land in the same ChatGPT conversation. Once that happened,
later wait/export logic could not reliably attribute replies to the right job.

### 2) Wait path previously treated contaminated threads as ordinary export lag

We already fixed one branch where:

- export matched the current user turn
- another `user` turn appeared before any assistant reply

That case is no longer allowed to keep looping in `wait`.

### 3) Repeated shallow answers had no generic fail-closed breaker

Even when the thread was not obviously contaminated, many jobs kept receiving short but non-empty
answers that completion guard judged suspicious. Without a generic breaker, those jobs could spin
through:

- `completion_guard_downgraded(reason=answer_quality_suspect_short_answer)`
- `wait_requeued`

for hundreds or thousands of cycles.

## Code changes landed

### A) Fresh-thread fail-closed at send time

File:

- `chatgpt_web_mcp/_tools_impl.py`

Key behavior:

- `_chatgpt_pick_existing_cdp_page(...)` no longer reuses existing ChatGPT thread tabs when the
  caller did not pin a `conversation_url`
- `_chatgpt_ensure_fresh_chat_context(...)` now explicitly verifies that the page is on a
  non-thread composer before a top-level ask is sent
- if `New chat` + landing-page navigation still cannot guarantee a fresh context, the executor now
  returns terminal:
  - `status=error`
  - `error_type=ConversationFreshThreadUnavailable`

This is an intentional fail-closed policy: better to reject the send than contaminate another job's
thread.

### B) Generic suspicious-short-answer loop breaker

File:

- `chatgptrest/worker/worker.py`

Key behavior:

- repeated `answer_quality_suspect_short_answer` downgrades on non-trivial jobs now trigger a
  breaker
- the breaker only fires if the answer does not show material length improvement
- terminal projection becomes:
  - `status=needs_followup`
  - `error_type=SuspiciousShortAnswerLoop`
  - event `completion_guard_suspicious_short_answer_loop_broken`

This is distinct from the earlier narrow legacy-trivial breaker.

## Tests

Validated with:

```bash
./.venv/bin/pytest -q tests/test_chatgpt_cdp_page_reuse.py tests/test_worker_and_answer.py
./.venv/bin/pytest -q tests/test_e2e.py
```

New/updated coverage:

- `tests/test_chatgpt_cdp_page_reuse.py`
  - top-level no-conversation asks skip thread tabs
  - fresh-chat guard fails closed if thread persists
  - fresh-chat guard recovers via landing-page navigation
- `tests/test_worker_and_answer.py`
  - repeated suspicious short answers now terminate with `SuspiciousShortAnswerLoop`

## Operator guidance

If ChatGPT Web starts surfacing `Too many requests`, do **not** assume it is just global rate
limit. Check for storm signatures:

- many `wait_requeued`
- many `completion_guard_downgraded`
- repeated `answer_quality_suspect_short_answer`
- multiple top-level jobs sharing one `conversation_url`

Useful checks:

```bash
sqlite3 state/jobdb.sqlite3 \
  "select type,count(*) from job_events where type in ('wait_requeued','completion_guard_downgraded') group by type;"

sqlite3 state/jobdb.sqlite3 \
  "select json_extract(payload_json,'$.reason') as reason, count(*) \
    from job_events where type='completion_guard_downgraded' \
    group by reason order by count(*) desc limit 10;"
```

If a current storm job is already contaminated or looping, cancel it after the worker restart rather
than trying to “wait it out”.

## What this does not solve yet

This change does **not** yet widen same-thread single-flight across every non-terminal state. The
current durable protections are:

- fail closed before a top-level ask can silently reuse a thread
- fail closed if export proves the thread is contaminated
- fail closed if repeated shallow answers show no material progress

Possible future hardening:

- stronger conversation-level dedupe across `needs_followup` / `cooldown` / `blocked`
- explicit operator dashboards for `completion_guard_downgraded -> wait_requeued` families
- provider-specific storm budgets that trip before Web itself shows `Too many requests`
