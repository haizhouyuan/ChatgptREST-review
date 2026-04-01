# 2026-03-31 Wrapped Review ChatGPT Lane Serialization and Same-Session Resume v1

## Background

During the dual-model external harness review workflow, two packaged `chatgptrest_call.py` review runs were sent to the same ChatGPT Pro CDP lane (`:9226`) in close succession.

The wrapper path itself was healthy enough to:

- initialize MCP correctly
- submit the public advisor-agent turn
- wait through deferred delivery

but both long-running review sessions still ended in:

- `status = needs_followup`
- `next_action.type = same_session_repair`
- `error_type = Blocked`

and the driver-side blocked state showed:

- `reason = verification_pending`

That meant the failure was no longer “wrapper cannot send the review at all”; it was a higher-order concurrency fault on the shared ChatGPT review lane.

## Root Cause

The packaged review workflow still lacked two controls:

1. **Provider-lane serialization**
   - multiple ChatGPT Pro review-style wrapper processes could submit against the same browser lane at the same time
   - the existing 61-second interval gate reduced burst rate, but did not prevent overlapping long review sessions

2. **Automatic same-session recovery for verification cooldowns**
   - when the public surface correctly projected `needs_followup + same_session_repair`
   - the wrapper returned that state to the caller, but did not automatically continue the same session after the published cooldown

So the system behaved correctly at the public contract layer, but the packaged review workflow stopped one step too early.

## Fix

Updated `skills-src/chatgptrest-call/scripts/chatgptrest_call.py` to add:

1. **ChatGPT review lane lock**
   - default lock file: `state/skill/chatgptrest_call_chatgpt_review.lock`
   - only enabled for ChatGPT Pro review-style agent calls
   - serializes review/report/research runs that use repo/file attachments or `github_repo`

2. **Automatic same-session resume**
   - when the wrapper receives:
     - `status = needs_followup`
     - `next_action.type = same_session_repair`
     - `error_type = Blocked`
   - and driver blocked state indicates `verification_pending`
   - the wrapper now waits through the published cooldown and resubmits the **same** `session_id`
   - no browser bypass, no new session, no manual prompt fallback

3. **Summary projection**
   - final summary now records:
     - `auto_resumed`
     - `same_session_repair_attempts`
   - so downstream review automation can distinguish a clean first-pass completion from an automatically recovered one

## Validation

Passed:

```bash
cd /vol1/1000/projects/ChatgptREST
python3 -m py_compile \
  skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  tests/test_skill_chatgptrest_call.py

./.venv/bin/pytest -q tests/test_skill_chatgptrest_call.py -k \
  'parser_accepts_chatgpt_review_lane_controls \
   or serializes_chatgpt_review_lane \
   or auto_repairs_same_session_blocked_review \
   or backgrounds_code_review_and_waits \
   or wait_transport_retries_after_incomplete_read'
```

Coverage added/confirmed:

- parser accepts new lane-control flags
- review-style ChatGPT runs enter the serialized lane lock
- deferred review still backgrounds and waits normally
- `verification_pending -> needs_followup + same_session_repair` now auto-resumes the same session and reaches `completed`
- wait transport recovery path still works

## Operational Result

The packaged dual-model review workflow no longer needs a browser-side manual fallback just because two ChatGPT Pro long reviews overlap on the same review lane.

Expected operator behavior is now:

1. use the packaged review workflow
2. let ChatGPT Pro review calls serialize on the shared lane
3. if the driver enters `verification_pending`, let the wrapper cool down and resume the same session automatically
4. only escalate to manual/browser intervention if the lane remains blocked after the wrapper’s bounded same-session repair attempts
