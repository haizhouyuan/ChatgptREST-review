# 2026-03-11 Gemini Conversation URL Recovery And Issue Graph Walkthrough v1

## Scope

This note covers one narrow Gemini failure shape:

- browser/Gemini thread already has a real answer
- ChatgptREST job remains `needs_followup`
- `conversation_url` stays empty or non-stable during `send -> wait`
- operator sees "answer exists in browser, but antigravity says there is a problem"

It also records how this failure currently appears inside `issue_domain`, and how
to search for nearby historical failures without relying on guesswork.

## Live Evidence

### 1. The reported Gemini thread is extractable now

Read-only probe:

- source URL: `https://gemini.google.com/app/2f7ddf5e8efabe4a`
- tool: `gemini_web.extract_answer`
- result job: `e06db059950f4135b06063c3931adfa1`
- observed outcome:
  - `status=completed`
  - `answer_chars=6813`
  - `conversation_url=https://gemini.google.com/app/2f7ddf5e8efabe4a`

This proves the current problem is not "Gemini page has no answer".

The failure is state recovery inside ChatgptREST, not inability to read the page.

### 2. The open issue-domain symptom still exists

Open issue snapshot on 2026-03-11:

- issue `iss_61a6698c420c44aabafc365e80afd98b`
  - title: `gemini_web.ask needs_followup: WaitNoThreadUrlTimeout`
  - latest job: `10ddd0c3dc274488914bac88c443922f`
  - latest `conversation_url=null`
  - metadata family: `gemini_no_thread_url`
- issue `iss_2ece6404e9254e4e81129c861a7133ac`
  - title: `gemini_web.ask needs_followup: WaitNoProgressTimeout`
  - latest job: `45b51b178d0e4b9988c22ebf9e13b8c2`
  - latest stable thread URL exists
  - metadata family: `gemini_stable_thread_no_progress`

### 3. Historical Gemini issues are still only partially family-structured

SQLite audit:

```sql
SELECT COALESCE(json_extract(metadata_json,'$.family_id'),''), status, COUNT(*)
FROM client_issues
WHERE kind='gemini_web.ask'
GROUP BY COALESCE(json_extract(metadata_json,'$.family_id'),''), status;
```

Observed counts:

- blank family id:
  - `closed=48`
  - `mitigated=28`
  - `open=4`
- `gemini_no_thread_url`
  - `open=3`
- `gemini_stable_thread_no_progress`
  - `open=1`

This means current runtime writes family IDs for the newer wait failures, but a
large amount of historical Gemini debt still requires symptom-text search and/or
backfill.

## Root Cause

The Gemini driver already persists idempotency records for ask/deep-research
calls, including `conversation_url` once the thread becomes known.

Before this change, `GeminiWebMcpExecutor` did not have a read-only recovery path
equivalent to ChatGPT's `chatgpt_web_idempotency_get()` flow.

That created a bad gap:

1. Gemini send call returned `in_progress`
2. stable thread URL was not yet present in the immediate tool result
3. executor moved into `WaitingForConversationUrl` / `WaitNoThreadUrlTimeout`
4. later, the page actually had an answer, but the job state machine had no
   reliable way to recover the thread URL from the existing idempotency record

This is why the operator can see a valid answer in the browser while the job is
still operationally stuck.

## Issue-Domain / EvoMap View

Current issue-domain shape around this failure is:

- `gemini_no_thread_url`
  - semantic meaning: wait entered without a stable Gemini thread URL
  - operational meaning: no safe resume target
- `gemini_stable_thread_no_progress`
  - semantic meaning: stable thread exists, but wait loop made no progress
  - operational meaning: different class; resume target exists

This split is the correct EvoMap-facing boundary:

- `no_thread_url` means "state recovery / thread discovery failure"
- `stable_thread_no_progress` means "harvest/wait stagnation after thread bind"

They should not be merged into one generic Gemini wait bucket.

## Changes Landed

### Runtime fix

Added read-only Gemini idempotency lookup and executor recovery:

- `chatgpt_web_mcp/providers/gemini/ask.py`
  - new `gemini_web_idempotency_get()`
- `chatgpt_web_mcp/providers/gemini_web.py`
  - exported new provider function
- `chatgpt_web_mcp/tools/gemini_web.py`
  - registered MCP tool `gemini_web_idempotency_get`
- `chatgptrest/executors/gemini_web_mcp.py`
  - recover `conversation_url` from Gemini idempotency record in `send`
  - recover `conversation_url` from Gemini idempotency record in `wait`
  - carry recovery evidence into final result metadata
- `chatgptrest/executors/config.py`
  - added `CHATGPTREST_GEMINI_IDEMPOTENCY_GET_TIMEOUT_SECONDS`

### Issue-history normalization

Updated `docs/issue_family_registry.json` to normalize Gemini wait families to
the names actually emitted by current worker logic:

- `gemini_no_thread_url`
- `gemini_stable_thread_no_progress`

Backward-compatible matcher terms still accept the older names:

- `gemini_followup_thread_handoff`
- `gemini_wait_no_progress`

This does not fully rewrite already-materialized canonical projections, but it
stops future matching drift and gives a deterministic normalization rule.

## How To Find Similar History Reliably

Do not rely on one search surface.

Use this order:

1. Issue ledger by `kind='gemini_web.ask'`
   - first filter by `error_type` / `symptom`:
     - `WaitNoThreadUrlTimeout`
     - `WaitNoProgressTimeout`
     - Deep Research planning-stub `RuntimeError`
2. Group by `metadata.family_id`
   - if present, trust it first
3. For older records without `family_id`
   - use `fingerprint_text`
   - use `raw_error`
   - use historical docs already linked by issue-domain review material
4. Distinguish by resume semantics
   - no thread URL
   - stable thread but no progress
   - planning stub / needs-confirmation
   - upload / Drive gating

This separation is important because the fixes are different.

## Remaining Gaps

### 1. Canonical graph labels are not fully refreshed

After normalizing the registry, live `match_issue_family()` returns the new
labels, but some existing canonical `issue_graph` views still show the older
label text from prior projection materialization.

That means the registry is now correct, but canonical backfill/reprojection is
still needed for a completely clean historical graph surface.

### 2. Historical Gemini debt is under-labeled

At audit time, most historical Gemini issues still had blank `family_id`.

The right next step is a narrow backfill that maps older Gemini issues into:

- `gemini_no_thread_url`
- `gemini_stable_thread_no_progress`
- planning-stub / followup families
- upload / attachment gating families

### 3. Recovery fixes state, not yet automatic closeout

This change improves URL recovery and makes more waits resumable, but already-open
historical issues still need normal verification / usage evidence to move from
`open` to `mitigated` or `closed`.

## Verification

Targeted regression coverage:

- `tests/test_gemini_wait_conversation_hint.py`
- `tests/test_gemini_wait_transient_handling.py`
- `tests/test_driver_startup_smoke.py`
- `tests/test_gemini_followup_wait_guard.py`
- `tests/test_worker_and_answer.py`
- `tests/test_issue_family_registry.py`
- `tests/test_issue_canonical_api.py`

The new cases specifically cover:

- send-phase idempotency recovery into `wait`
- wait-phase recovery when only Gemini base `/app` URL is available
- issue-family normalization for old and new Gemini family IDs
