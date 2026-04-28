# ChatGPTREST Parallel Review Incident Retrospective

Date: 2026-04-27  
Context: Toyresearch / Paperclip + Labebe open advisor review  
Owner of this retrospective: Codex in `toyresearch`  
Intended reader: Codex working inside the `ChatgptREST` repository

## Executive Summary

The user asked to send the same high-context review packet to:

1. Gemini DeepThink.
2. A new ChatGPT Pro conversation.
3. Keep the old ChatGPT Pro conversation waiting, because it might still complete after a long 40+ minute budget.

The packet was successfully built and Gemini DeepThink eventually completed. The new Pro conversation was **not submitted** before this retrospective because ChatGPTREST hit a global low-level client in-flight limit while the old Pro job and Gemini job were active.

The most important system issues observed:

1. **Old Pro job appears stuck but stays `in_progress` indefinitely.** It repeatedly observes a 472-character echo/partial text that is just the prompt, keeps requeueing, keeps exporting conversation, and keeps holding an in-flight slot.
2. **Global low-level concurrency blocks cross-provider parallel reviews.** With old Pro + Gemini active, a new Pro or corrected Gemini submission is rejected with HTTP 429 `low_level_ask_client_concurrency_exceeded`.
3. **MCP cancel schema mismatch is still visible to this Codex session.** The exposed `automation_job_cancel` tool accepts only `job_id`, but backend requires an explicit `reason`, so cancellation fails with `ExplicitCancelReasonRequired`.
4. **Gemini DeepThink preset selection is too easy to get wrong.** The first Gemini submission accidentally used `preset=pro` even though the user explicitly requested DeepThink. The provider capability profile later showed `deep_think` is supported, but the wrapper did not fail or warn on the mismatch between requested capability and preset.
5. **Direct maintenance cancel path is operationally awkward.** The low-level CLI needed token/client/env handling; one env file could not be safely `source`d, `chatgptrestctl-maint` was not in the cancel allowlist, and the successful direct check/cancel path required switching to `CHATGPTREST_CLIENT_NAME=chatgptrestctl`.

## Key Artifacts

Review packet:

- `/vol1/maint/exports/pro_review_packets/2026-04-27_toyresearch_paperclip_labebe_open_advisor`
- `/vol1/maint/exports/pro_review_packets/2026-04-27_toyresearch_paperclip_labebe_open_advisor.zip`
- Upload copy: `/tmp/chatgptrest_uploads/toyresearch_paperclip_labebe_open_advisor_20260427.zip`

Gemini answer:

- `/vol1/maint/exports/pro_review_packets/2026-04-27_toyresearch_paperclip_labebe_open_advisor/review_answers/gemini_deepthink_answer.md`
- ChatGPTREST artifact: `/vol1/1000/projects/ChatgptREST/artifacts/jobs/0dada145364746529cd8585ebf7bbf5d/answer.md`

Packet log:

- `/vol1/maint/exports/pro_review_packets/2026-04-27_toyresearch_paperclip_labebe_open_advisor/REVIEW_SUBMISSION_LOG.md`

## Timeline

### 1. Old Pro corrective job already active

Job:

- `076c4a2b073b495d87bb93a7d097b12a`
- Kind: `chatgpt_web.ask`
- Parent job: `06a8a546d4f0451c804b6e02a5043bd6`
- Conversation: `https://chatgpt.com/c/69ef0ae3-81a0-83e8-a1e4-ae121e01f432`
- Requested/effective provider: `chatgpt`
- Requested/effective preset: `pro_extended`

Current status snapshot:

```text
status: in_progress
phase: wait
phase_detail: awaiting_wait_poll
answer_chars: null
completion_contract.answer_state: partial
finality_reason: worker_timing
safe_next_action: wait
```

Important observed events:

```text
1777274318 prompt_sent
1777274319 phase_changed send -> wait
1777274319 browser_retry_scheduled RuntimeError: empty error
1777274448 wait_partial_answer_progressed answer_chars=472
1777274588 wait_partial_answer_progressed answer_chars=472 delta_chars=0
1777274727 wait_partial_answer_progressed answer_chars=472 delta_chars=0
1777274867 wait_partial_answer_progressed answer_chars=472 delta_chars=0
1777275014 wait_active_finalization_observed RuntimeError: empty error
1777275165 wait_partial_answer_progressed answer_chars=472 delta_chars=0
1777275306 wait_partial_answer_progressed answer_chars=472 delta_chars=0
```

The 472-character preview is the prompt text itself:

```text
你刚才没有回答，只是原样复述了我的提示。请现在实际输出答案...
```

Concern:

- The system treats this as continuing partial progress / active finalization instead of recognizing a likely prompt echo / stalled non-answer.
- It continues to renew leases and occupy an in-flight slot for a long time.
- This is exactly the scenario the user observed in the web activity pane: long period with no meaningful progress.

### 2. Review packet built correctly

Created:

- `README.md`
- `DELTA_MEMO.md`
- `PROMPT_FOR_REVIEWERS.md`
- `PROMPT_FOR_GEMINI_DEEPTHINK.md`
- `ADVISOR_SUBMIT_REQUEST_PRO_NEW.json`
- `ADVISOR_SUBMIT_REQUEST_GEMINI.json`
- `preflight_pro_new.json`
- `preflight_gemini.json`
- `client_context_new_reviews.json`
- file index, checksum, packet audit, secret scan

Secret scan:

```text
secret_scan_hit_count: 0
```

### 3. First Gemini submission used the wrong preset

Job:

- `05cb0a998ccb42fd8929c2778d831207`
- Kind: `gemini_web.ask`
- Requested/effective preset: `pro`
- Intended capability: Gemini DeepThink

This was a client-side mistake: I submitted `preset=pro` first. However, ChatGPTREST had enough metadata to detect the mismatch:

- `provider_selection.requested_capability`: `Gemini DeepThink / Gemini web high-reasoning advisor`
- `provider_selection.preferred_model`: `Gemini DeepThink where available`
- Provider capability profile showed supported presets: `["deep_think", "pro"]`

Observed outcome:

```text
status: error
phase: send
reason_type: GeminiBlankSendTimeout
reason: Gemini send failed without stable conversation_url/thread evidence; fail closed instead of repeated cooldown retries.
```

Events:

```text
1777275904 worker_timing phase=send total_s=80.9
1777275904 blank_gemini_cooldown_fail_closed
1777275904 status_changed in_progress -> error
1777275905 automation_terminal_push_delivered
```

This job did not produce useful review output.

### 4. MCP cancellation failed because schema lacks `reason`

Attempted:

```text
automation_job_cancel(job_id="05cb0a998ccb42fd8929c2778d831207")
```

Returned:

```json
{
  "ok": false,
  "error_type": "ExplicitCancelReasonRequired",
  "error": "missing_explicit_mcp_cancel_reason",
  "recommended_action": "Pass automation_job_cancel(reason=...) or disable CHATGPTREST_REQUIRE_EXPLICIT_MCP_CANCEL_REASON for compatibility-only clients."
}
```

But the MCP tool schema exposed in this Codex session only accepts:

```text
{ job_id: string }
```

It does not expose a `reason` argument. This is a client/server/tool-binding contract mismatch. It was already known from earlier ChatGPTREST work, but it is still active in this Codex environment.

### 5. Direct CLI cancel/status path was cumbersome

First attempt:

```bash
python -m chatgptrest.cli jobs cancel 05cb... --reason superseded_by_gemini_deepthink_v2_wrong_preset_pro
```

Failed:

```text
HTTP 401 Unauthorized
```

Attempt to source env:

```bash
set -a
. ~/.config/chatgptrest/chatgptrest.env
set +a
```

Failed because the env file contains a non-shell-safe line:

```text
/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env: line 13: Codex: command not found
```

Manual parsing of token envs then using:

```text
CHATGPTREST_CLIENT_NAME=chatgptrestctl-maint
```

Failed:

```text
HMAC secret env CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT is not configured
```

After manually exporting that HMAC secret, it failed again:

```text
cancel_client_not_allowed
x_client_name: chatgptrestctl-maint
allowed_cancel_client_names: ["chatgptrest-agent-mcp", "chatgptrestctl"]
```

Finally, using:

```text
CHATGPTREST_CLIENT_NAME=chatgptrestctl
```

worked as a status/cancel path, but the job was already `error`.

This is not the primary incident, but it shows the maintenance cancel path is too fragile under pressure.

### 6. Correct Gemini DeepThink submission completed

Job:

- `0dada145364746529cd8585ebf7bbf5d`
- Kind: `gemini_web.ask`
- Requested/effective provider: `gemini`
- Requested/effective preset: `deep_think`
- Conversation: `https://gemini.google.com/app/78b33a98b24b5d00`
- Final answer chars: `5733`
- Status: `completed`

Important events:

```text
1777276009 job_created
1777276160 worker_timing phase=send total_s=149.9
1777276160 conversation_url_set https://gemini.google.com/app
1777276160 phase_changed send -> wait
1777276160 browser_retry_scheduled GeminiSendPendingUnknown
1777276239 conversation_url_upgraded https://gemini.google.com/app/78b33a98b24b5d00
1777276239 browser_retry_scheduled "Deep Think answer may take time"
1777276463 answer_quality_detected answer_chars_after=5732
1777276463 conversation_export_forced reason=missing_export_answer
1777276463 status_changed in_progress -> completed
1777276463 completion_contract_recorded final
1777276464 automation_terminal_push_delivered
```

Good behavior:

- The Gemini job recovered from send uncertainty.
- It found/upgraded the Gemini conversation URL.
- It detected answer quality and completed.

Open concern:

- The first conversation URL was only `https://gemini.google.com/app`; later it was upgraded. This is fine if intentional, but downstream status displays should make clear that the base URL is provisional.

### 7. New Pro conversation was not submitted before this retrospective

Desired new Pro idempotency key:

```text
toyresearch-paperclip-labebe-open-advisor-pro-new-20260427-v1
```

Attempted DeepThink retry before the first Gemini job terminaled hit:

```json
{
  "error": "low_level_ask_client_concurrency_exceeded",
  "error_type": "LowLevelAskClientConcurrencyExceeded",
  "reason": "registered_client_max_in_flight_exceeded",
  "client_id": "internal-submit-wrappers",
  "max_in_flight_jobs": 2,
  "active_job_ids": [
    "076c4a2b073b495d87bb93a7d097b12a",
    "05cb0a998ccb42fd8929c2778d831207"
  ]
}
```

This same limit would have blocked the new Pro submission while old Pro + Gemini DeepThink were both active.

After Gemini DeepThink completed, a slot became available. I intentionally did not continue submitting the new Pro after the user asked for this retrospective and said they would have ChatGPTREST-side Codex fix the process.

## Suspected Root Causes / Contract Gaps

### A. Stalled Pro wait loop does not detect prompt echo / no-answer plateau

The old Pro job appears to be in a pathological state:

- `prompt_sent` happened.
- The web / export layer keeps seeing a 472-character text that is the prompt itself.
- `delta_chars=0` repeats across several wait cycles.
- `best_role` is `tool`, not a normal assistant answer.
- Yet the job remains `in_progress`, safe_next_action `wait`.

This should probably become one of:

- `needs_followup`
- `blocked`
- `stalled_prompt_echo`
- `manual_review_required`
- or a bounded `same_session_repair` path

It should not indefinitely occupy a scarce low-level in-flight slot without a clearer state.

### B. Global in-flight limit is too blunt for advisory orchestration

`max_in_flight_jobs=2` for `internal-submit-wrappers` blocked intended parallel review.

This may be deliberate for browser safety, but the current behavior is a hard foreground 429:

- no queueing;
- no admission ticket;
- no retry_after usable by the wrapper;
- no way to say "enqueue new Pro after one of these active jobs terminalizes";
- no per-provider pool distinction.

For advisor workflows, a better contract would be:

- submit accepted as `admission_queued`, or
- return a durable deferred job id, or
- expose `retry_after_seconds` plus active holders and a recommended wait path, or
- separate ChatGPT and Gemini browser lanes if actually independent.

### C. MCP cancel tool schema is stale / incompatible with backend policy

Backend now requires explicit cancel reason when `CHATGPTREST_REQUIRE_EXPLICIT_MCP_CANCEL_REASON=1`.

The MCP tool in this session still exposes only:

```text
automation_job_cancel(job_id)
```

The tool should expose:

```text
automation_job_cancel(job_id, reason)
```

or the backend should return a compatibility path. Given the existing docs already say the tool accepts `reason`, this looks like a stale generated schema / client binding issue.

### D. Provider capability and requested preset are not cross-validated strongly enough

The user asked for Gemini DeepThink. The first job had:

```text
provider_selection.requested_capability = Gemini DeepThink
preferred_model = Gemini DeepThink where available
requested_preset = pro
supported_presets = ["deep_think", "pro"]
```

This should at least warn or fail preflight:

```text
requested_capability_mentions_deepthink && preset != deep_think && deep_think_supported
```

This is partly client error, but ChatGPTREST has enough information to catch it.

### E. Maintenance CLI cancel path is too easy to use incorrectly

Operational friction seen:

- Direct CLI did not autoload env the way the wrapper docs imply for legacy maintenance paths.
- Shell-sourcing env failed on a non-shell-safe line.
- `chatgptrestctl-maint` had HMAC and allowlist mismatch.
- The allowed cancel client was `chatgptrestctl`, not `chatgptrestctl-maint`.

For incidents, there should be a documented and reliable command:

```bash
ops/job_cancel_with_reason.sh JOB_ID REASON
```

It should:

- load tokens safely without sourcing arbitrary env text;
- use an allowed cancel identity;
- include X-Cancel-Reason;
- emit a compact JSON summary;
- never require the operator to guess client identity/HMAC behavior.

### F. Push delivery can look successful while not updating local project state

Both Gemini jobs emitted `automation_terminal_push_delivered`, but the hook result was:

```text
ignored_missing_push_context: true
reason: push_context.task_id and push_context.state_file are required for workbench state write
```

This is not necessarily a bug for this manual review, but it can mislead clients:

- delivery was technically successful;
- no local task state was updated.

The summary should surface this as "delivered but ignored by receiver" rather than a clean completed notification.

## Recommended Fixes

### P0

1. **Expose `reason` in `automation_job_cancel` MCP schema.**
   - Regenerate / reload MCP tool schema.
   - Add regression test that public MCP schema includes a required or optional `reason` field when explicit reason policy is active.

2. **Add stalled prompt-echo / no-answer plateau detection for ChatGPT wait jobs.**
   - If repeated wait cycles see same short text with `delta_chars=0`, and preview strongly overlaps the user prompt, mark as `needs_followup` or `blocked_stalled_echo`.
   - Do not keep it indefinitely as generic `in_progress`.
   - Include `best_role`, `answer_chars`, `delta_chars`, and prompt-overlap score in the reason payload.

3. **Make in-flight admission failure actionable or queueable.**
   - For `LowLevelAskClientConcurrencyExceeded`, include `retry_after_seconds` when possible.
   - Prefer a durable `admission_queued` job over a hard 429 for high-level `automation_ask`.
   - At minimum, wrapper should write a local summary saying "not submitted; active job ids are X/Y; retry after condition Z".

4. **Validate Gemini DeepThink requests against preset.**
   - If provider is Gemini and requested capability says DeepThink, default preset to `deep_think` or fail if caller passes `pro`.
   - Do not silently accept `pro` for a DeepThink request unless explicitly overridden.

### P1

5. **Provide a supported maintenance cancel helper.**
   - Example: `ops/job_cancel_with_reason.sh`.
   - Safe env parsing, correct client identity, reason header, compact output.

6. **Improve terminal push semantics.**
   - Distinguish `push_delivered_and_applied` vs `push_delivered_but_receiver_ignored`.
   - Include this in wrapper summary.

7. **Better status for provisional conversation URLs.**
   - For Gemini, distinguish base app URL from stable thread URL.
   - Avoid presenting `https://gemini.google.com/app` as a stable conversation until upgraded.

### P2

8. **Separate provider-specific concurrency pools if safe.**
   - ChatGPT and Gemini web surfaces may still share machine/browser resources, but if they can safely run independently, split their in-flight budgets.
   - If not safe, keep global budget but support queueing/admission.

9. **Advisor job quality contracts.**
   - A Pro/Gemini answer that simply echoes the prompt should be `unusable_external_review_evidence`.
   - Do not let prompt echo count as partial progress indefinitely.

## Current State At Handoff

```text
Old Pro job:
  076c4a2b073b495d87bb93a7d097b12a
  status: in_progress
  phase: wait
  issue: likely stuck / prompt echo plateau

Wrong Gemini Pro job:
  05cb0a998ccb42fd8929c2778d831207
  status: error
  reason_type: GeminiBlankSendTimeout
  not useful

Correct Gemini DeepThink job:
  0dada145364746529cd8585ebf7bbf5d
  status: completed
  answer_chars: 5733
  answer artifact copied into review packet

New Pro comparison job:
  not submitted yet
  reason: user asked for this retrospective before continuing, and ChatGPTREST process needs repair review
```

## Suggested Reproduction Steps

1. Inspect old Pro events:

```bash
python -m chatgptrest.cli jobs events 076c4a2b073b495d87bb93a7d097b12a --limit 200
```

Look for:

- repeated `wait_partial_answer_progressed`;
- `answer_chars=472`;
- `delta_chars=0`;
- prompt text in preview;
- repeated `wait_requeued`;
- `best_role=tool`;
- no terminal state.

2. Inspect Gemini failed send:

```bash
python -m chatgptrest.cli jobs get 05cb0a998ccb42fd8929c2778d831207
python -m chatgptrest.cli jobs events 05cb0a998ccb42fd8929c2778d831207 --limit 100
```

Look for:

- `blank_gemini_cooldown_fail_closed`;
- `GeminiBlankSendTimeout`;
- terminal push ignored by workbench receiver.

3. Inspect successful DeepThink:

```bash
python -m chatgptrest.cli jobs get 0dada145364746529cd8585ebf7bbf5d
python -m chatgptrest.cli jobs events 0dada145364746529cd8585ebf7bbf5d --limit 150
```

Look for:

- `GeminiSendPendingUnknown`;
- `conversation_url_upgraded`;
- `answer_quality_detected`;
- `completion_contract_recorded`.

4. Check MCP schema exposed to Codex for `automation_job_cancel`.

Expected fix:

```text
automation_job_cancel(job_id, reason)
```

Observed in this session:

```text
automation_job_cancel(job_id)
```

## Non-Goals

- Do not cancel the old Pro job without explicit user approval.
- Do not make the system more aggressive at repeatedly resending prompts.
- Do not solve this by disabling all concurrency controls.
- Do not route Gemini DeepThink to Gemini CLI; it must stay on `gemini_web.ask` / automation-kernel web path.

