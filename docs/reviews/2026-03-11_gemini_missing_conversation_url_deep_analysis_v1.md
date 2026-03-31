# 2026-03-11 Gemini Missing Conversation URL Deep Analysis v1

## Purpose

This document records the full investigation for one narrow Gemini production
failure shape:

- the Gemini browser thread already contains a real answer
- ChatgptREST still reports the job as problematic
- the job remains in `needs_followup` or `in_progress`
- `conversation_url` is missing, base-only, or otherwise not resumable

This is a narrower and more actionable problem than issue `#113`, which remains
an intentionally mixed intake bucket.

This document also records:

- how the failure appears in the current `issue_domain`
- what the root cause actually is
- which fixes are tactical versus fundamental
- how to search for similar historical failures without relying on manual memory
- what should be represented in EvoMap versus what should remain canonical issue
  history only

## Executive Judgment

### Main conclusion

The reported Gemini thread was not blocked by "no answer available" or "UI no
longer readable".

The real failure was:

1. Gemini produced an answer in the browser thread
2. ChatgptREST had already crossed the `send -> wait` boundary
3. the executor had no Gemini-side equivalent of ChatGPT's idempotency-based
   conversation recovery path
4. the job state machine therefore remained unable to safely resume the thread
   and eventually drifted into `WaitNoThreadUrlTimeout`

### Stronger phrasing

This is primarily a **state recovery failure**, not a content generation failure.

The user-observed symptom "browser has answer, antigravity says broken" is
consistent with an executor/worker contract gap, not with Gemini failing to
generate.

### Secondary conclusion

The issue-domain / graph layer is directionally correct, but its historical
Gemini family normalization is incomplete.

Newer runtime failures already expose meaningful split families:

- `gemini_no_thread_url`
- `gemini_stable_thread_no_progress`

But historical Gemini issues are still under-labeled, and canonical issue-graph
materialization still shows older labels in some views.

## User Trigger

The trigger for this analysis was a live user report:

- Gemini conversation URL:
  - `https://gemini.google.com/app/2f7ddf5e8efabe4a`
- user observation:
  - browser view already showed a real answer
  - Antigravity / ChatgptREST side still treated the job as problematic
  - in the second round with attachments, `conversation_url` was still `null`

The user explicitly asked for three things:

1. enter the current issue-graph domain / EvoMap view
2. determine the fundamental fix, not just a surface workaround
3. find similar historical failures and explain how to search them reliably

## Evidence Collected

### A. Live read-only proof that the thread has an answer

Read-only probe:

- tool:
  - `gemini_web.extract_answer`
- input URL:
  - `https://gemini.google.com/app/2f7ddf5e8efabe4a`
- result job:
  - `e06db059950f4135b06063c3931adfa1`

Observed result:

- `status=completed`
- answer preview present
- `answer_chars=6813`
- `conversation_url=https://gemini.google.com/app/2f7ddf5e8efabe4a`

Judgment:

- the page is currently extractable
- the answer is not missing
- the failure is not "Gemini never produced output"

### B. Open issue-domain rows that match the symptom class

Issue ledger snapshot on 2026-03-11 showed:

1. `iss_61a6698c420c44aabafc365e80afd98b`
   - title:
     - `gemini_web.ask needs_followup: WaitNoThreadUrlTimeout`
   - latest job:
     - `10ddd0c3dc274488914bac88c443922f`
   - latest `conversation_url`:
     - `null`
   - metadata family:
     - `gemini_no_thread_url`

2. `iss_2ece6404e9254e4e81129c861a7133ac`
   - title:
     - `gemini_web.ask needs_followup: WaitNoProgressTimeout`
   - latest job:
     - `45b51b178d0e4b9988c22ebf9e13b8c2`
   - latest stable thread URL:
     - `https://gemini.google.com/app/7465d72fb7eac9b6`
   - metadata family:
     - `gemini_stable_thread_no_progress`

Judgment:

- these are related but not identical failures
- one is missing the resumable thread target
- the other already has the resumable thread target but still fails to harvest

### C. Concrete artifact-level evidence from a no-thread case

Sample job:

- `10ddd0c3dc274488914bac88c443922f`

Observed shape:

- `kind=gemini_web.ask`
- `preset=deep_think`
- attachment-heavy request
- result entered wait path
- `conversation_url=NULL`
- events later included `wait_no_progress_timeout` / `WaitNoThreadUrlTimeout`

Judgment:

- this is exactly the bad operational shape where send succeeded enough to create
  a logical Gemini run, but not enough to persist a resumable thread URL

### D. Historical scope from the issue ledger

SQLite audit:

```sql
SELECT COALESCE(json_extract(metadata_json,'$.family_id'),''), status, COUNT(*)
FROM client_issues
WHERE kind='gemini_web.ask'
GROUP BY COALESCE(json_extract(metadata_json,'$.family_id'),''), status;
```

Observed counts at audit time:

- blank family id:
  - `closed=48`
  - `mitigated=28`
  - `open=4`
- `gemini_no_thread_url`
  - `open=3`
- `gemini_stable_thread_no_progress`
  - `open=1`

Judgment:

- most historical Gemini debt is still under-structured
- family-aware history search works for newer data only
- old Gemini history still needs fallback search through text fingerprints

### E. Canonical issue graph check

Canonical issue graph query for `family_id=gemini_no_thread_url` returned a live
family node and linked issue node, proving that the issue-domain -> canonical
projection path is working.

However, some canonical graph views still surfaced the older label text
`Gemini follow-up / thread handoff` even after runtime family naming had moved to
`gemini_no_thread_url`.

Judgment:

- current graph is usable
- current graph is not yet perfectly normalized
- a backfill/reprojection step is still needed

## Why The Browser Had The Answer But The Job Looked Broken

### What did not happen

This is not best explained by:

- Gemini refusing the prompt outright
- extractor inability to read the page
- generalized CDP outage
- generalized Antigravity outage

Those can happen in other Gemini issue families, but they do not best explain
this specific incident.

### What likely happened

The likely sequence is:

1. Gemini accepted the prompt
2. Gemini generated or continued generating inside a browser thread
3. the immediate send response returned `in_progress`
4. the immediate send response still lacked a stable thread URL
5. ChatgptREST moved into wait semantics without a Gemini-side recovery path
6. later, the thread URL existed inside driver idempotency state and/or the page
   itself, but the executor no longer knew how to retrieve it safely

### Why this matters

Without a resumable thread URL, the worker cannot distinguish between:

- "no answer yet"
- "answer exists but thread handle was lost"
- "page exists but only base `/app` is known"

This ambiguity is exactly what produces false operational stuck states.

## Code-Level Root Cause

### The asymmetry

ChatGPT executor already had a read-only recovery path based on idempotency
lookup.

Gemini executor did not.

That asymmetry was the key bug.

### The missing seam

The Gemini driver/provider already persisted idempotency information, including
`conversation_url`, but that persisted state was not exposed as a read-only MCP
tool that `GeminiWebMcpExecutor` could call later.

So the system had the state, but not the retrieval seam.

### Strong judgment

This is a contract gap between:

- provider persistence
- executor recovery
- worker wait semantics

The provider knew more than the executor was allowed to recover.

## Tactical Fix That Landed

### Runtime change

Added a new read-only Gemini MCP tool:

- `gemini_web_idempotency_get`

Wired it into:

- `[ask.py](/vol1/1000/projects/ChatgptREST/chatgpt_web_mcp/providers/gemini/ask.py)`
- `[gemini_web.py](/vol1/1000/projects/ChatgptREST/chatgpt_web_mcp/providers/gemini_web.py)`
- `[gemini_web.py](/vol1/1000/projects/ChatgptREST/chatgpt_web_mcp/tools/gemini_web.py)`
- `[gemini_web_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/executors/gemini_web_mcp.py)`
- `[config.py](/vol1/1000/projects/ChatgptREST/chatgptrest/executors/config.py)`

### Behavior change

Gemini executor now:

- tries idempotency recovery in send stage if send returns `in_progress` without
  usable `conversation_url`
- tries idempotency recovery in wait stage before giving up on missing
  `conversation_url`
- preserves recovery evidence in final result metadata

### Why this is the right tactical fix

It does not invent a thread URL.

It reuses already-authoritative state created by the original send call.

That makes it safe and auditable.

## Fundamental Fix, Not Just Tactical Fix

The idempotency recovery path is necessary, but it is not the full fundamental
solution.

The fundamental solution has four layers.

### Layer 1. Provider/executor contract completeness

Every web provider that can:

- create a resumable conversation
- return `in_progress`
- later be resumed by `conversation_url`

must also expose a read-only idempotency recovery seam.

Judgment:

- ChatGPT had this
- Gemini now has it
- this should be treated as a provider contract requirement, not a one-off patch

### Layer 2. Wait semantics must classify by resumability

The system should continue treating these as distinct operational classes:

- no stable thread URL
- stable thread URL but no progress

Judgment:

- this split is correct
- merging them would blur both diagnosis and repair strategy

### Layer 3. Historical issue families must be normalized

A runtime fix alone does not solve observability debt.

We also need:

- stable family naming
- backward-compatible matching
- historical backfill for older Gemini issues

Judgment:

- without this, repeated failures will keep looking novel when they are not

### Layer 4. Canonical graph / EvoMap ingestion must preserve semantics

Issue-domain should record authoritative incident truth.

EvoMap should ingest only reviewed and semantically separated lessons.

Judgment:

- raw open incidents should not become runtime retrieval advice
- reviewed family-level operational lessons should

## How Similar Historical Failures Should Be Found

This was one of the user's explicit asks.

### The wrong way

Do not search only one of these:

- GitHub issues
- issue family id
- raw `conversation_url`
- docs grep

Each surface is incomplete by itself.

### The right search order

1. Search issue ledger by `kind='gemini_web.ask'`
2. Segment by symptom / error type:
   - `WaitNoThreadUrlTimeout`
   - `WaitNoProgressTimeout`
   - planning-stub `RuntimeError`
   - upload / Drive gating
3. Trust `metadata.family_id` first when present
4. For older rows without family id:
   - search `fingerprint_text`
   - search `raw_error`
   - search linked review/devlog documents
5. Only after that, correlate with GitHub issues

### Why GitHub alone is insufficient

Issue `#113` is useful as a mixed intake anchor, but it is too broad to answer:

- "is this another no-thread failure?"
- "is this stable-thread no-progress?"
- "is this a planning stub / Deep Research confirmation failure?"

That is why issue-domain and canonical graph are required.

## Similar Failure Classes Nearby

The following are related but must stay distinct:

### 1. `gemini_no_thread_url`

Meaning:

- wait entered without a resumable thread URL

Fix family:

- recover thread URL
- fail closed if recovery impossible

### 2. `gemini_stable_thread_no_progress`

Meaning:

- thread exists
- harvest/wait is stalled

Fix family:

- wait watchdogs
- export salvage
- stuck-thread diagnostics

### 3. Deep Research planning-stub / confirmation failures

Meaning:

- the thread is real
- Gemini responds with a plan or confirmation stub
- the system may terminalize or loop incorrectly

Fix family:

- explicit followup guard
- needs-confirmation semantics
- post-plan resume rules

### 4. Upload / Drive gating failures

Meaning:

- the answer path may never start because attachments were not truly ready

Fix family:

- upload readiness handling
- quota/backoff
- attachment-family tagging

Judgment:

These are all "Gemini instability" in a loose sense, but they are not one bug.

## Issue-Domain And EvoMap Interpretation

### What belongs in canonical issue-domain

- issue identity
- family id
- latest job
- fix commit
- verification evidence
- usage evidence

### What should not go straight into runtime EvoMap retrieval

- raw open-issue text
- one-off artifact excerpts
- temporary operator notes
- unresolved mixed-bucket GitHub issue prose

### What should become EvoMap material later

- family-level lessons after verification
- replayable troubleshooting procedures
- provider contract rules such as:
  - any resumable provider must support read-only idempotency recovery

Judgment:

Issue-domain is the truth plane.

EvoMap should become the governed lesson plane.

## Changes Landed During This Investigation

Code commits:

- `05733ac`
  - `fix(gemini): recover conversation url from idempotency`
- `1e3bc18`
  - `docs(gemini): record conversation url recovery investigation`

Associated walkthrough:

- `[walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_gemini_conversation_url_recovery_and_issue_graph_walkthrough_v1.md)`

### Additional normalization landed

Updated:

- `[issue_family_registry.json](/vol1/1000/projects/ChatgptREST/docs/issue_family_registry.json)`

to normalize Gemini wait family IDs to:

- `gemini_no_thread_url`
- `gemini_stable_thread_no_progress`

while keeping compatibility with older labels:

- `gemini_followup_thread_handoff`
- `gemini_wait_no_progress`

## Verification Performed

Targeted tests run:

- `tests/test_gemini_wait_conversation_hint.py`
- `tests/test_gemini_wait_transient_handling.py`
- `tests/test_driver_startup_smoke.py`
- `tests/test_gemini_followup_wait_guard.py`
- selected worker regression cases in `tests/test_worker_and_answer.py`
- `tests/test_issue_family_registry.py`
- selected canonical issue tests in `tests/test_issue_canonical_api.py`

Key new coverage:

- send-phase recovery from Gemini idempotency into wait
- wait-phase recovery from Gemini idempotency when only base `/app` is available
- issue-family normalization for old/new Gemini wait family names

## Remaining Gaps

### 1. Historical backfill is still needed

Most historical Gemini issues still have blank `family_id`.

That makes cross-run clustering weaker than it should be.

### 2. Canonical issue graph still has stale labels in some materialized views

The registry is now normalized, but some canonical graph surfaces still expose
older label text until reprojection/backfill happens.

### 3. Existing open incidents still need verification closure

Fixing recovery logic does not auto-close already-open issue-domain rows.

They still need:

- verification evidence
- usage evidence
- normal issue lifecycle progression

## Recommendations

### Immediate

1. Keep the newly landed Gemini idempotency recovery path
2. Open a narrow GitHub issue for this specific failure shape
3. Link it back to `#113` as a decomposed child/sibling issue

### Near-term

1. Backfill old Gemini issues into normalized families
2. Reproject canonical issue graph labels
3. Add a repair/verification path that can mark recovered historical incidents as
   mitigated once a real answer extraction succeeds

### Structural

1. Treat idempotency recovery as a mandatory provider contract
2. Preserve `no_thread_url` versus `stable_thread_no_progress` as separate
   operational families
3. Feed only reviewed family-level lessons into EvoMap retrieval

## Proposed GitHub Issue Scope

The new GitHub issue should be narrowly titled around:

- Gemini answered thread exists, but ChatgptREST loses resumable
  `conversation_url`
- executor must recover from idempotency
- issue families / history search must distinguish no-thread versus
  stable-thread-no-progress

It should explicitly reference `#113` as related context, not as the sole home
for this failure.

## Final Judgment

This incident was valuable because it falsified an easy but wrong explanation.

The wrong explanation was:

- "Gemini is flaky again"

The stronger explanation is:

- "Gemini may already have succeeded, but ChatgptREST lacked the recovery seam
  needed to prove and resume that success"

That distinction matters because it changes the fix from vague reliability work
into a concrete state-contract repair and a better historical issue taxonomy.
