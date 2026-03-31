# 2026-03-10 Issue #113 Gemini Issue-Domain Intake Approval

## Scope

- This document stays strictly inside `issue_domain`.
- It uses GitHub issue `#113` as the intake anchor for Gemini instability evidence.
- It does not propose a new runtime consumer outside `issue_domain`.
- It does not reopen broad Gemini provider architecture planning.
- Goal: reduce `#113` from a mixed symptom bucket into a narrow issue-domain intake package that can be queried, family-grouped, and historically backfilled.

## Intake Anchor

- GitHub issue: `#113`
- Title: `Gemini ask path unstable: DeepThink tool-not-found, stuck wait, or bogus-short 'Gemini 说' completion`
- Related but distinct thread: `#101`

## Real Evidence Snapshot

Audit time: 2026-03-10 CST

### Failure mode A: Deep Think tool unavailable

- job `745d655c2f8c4d2c9486d230f1c70654`
- observed result:
  - `status=error`
  - `error_type=GeminiDeepThinkToolNotFound`
  - `conversation_url=https://gemini.google.com/app`
- local code status:
  - current `master` already contains fallback logic from `deep_think` to `pro`
  - see commit history: `5ec323d`, `0fce6c2`

### Failure mode B: bogus-short terminal completion

- jobs:
  - `bbcc1fdd3ac648ba92acfdee1dd828dc`
  - `5651b246e7354d19b53b65c14a910a63`
- observed artifacts:
  - `answer.md` only contains `Gemini 说`
  - events show `answer_quality_detected`
  - events also show `status_override=null`
  - worker still terminalized these jobs as `completed`
- local code status before this batch:
  - `_gemini_apply_answer_quality_guard()` detected the UI-noise marker
  - but the anchor-only fragment was preserved as non-empty answer text
  - API later labeled it `completed_suspect_short_answer`, but only in view-layer metadata

### Failure mode C: send -> wait with no stable thread URL

- job `10ddd0c3dc274488914bac88c443922f`
- request shape:
  - `kind=gemini_web.ask`
  - `preset=deep_think`
  - `file_paths=25`
- authoritative state observed locally:
  - `status=in_progress`
  - `phase=wait`
  - `conversation_url=NULL`
  - no active lease
  - last recorded events are `phase_changed {send->wait}` and `wait_requeued`
- local code status:
  - current `master` already contains:
    - send-lane hold until stable Gemini thread URL
    - `WaitNoThreadUrlTimeout`
    - `WaitNoProgressTimeout`
  - see current worker behavior and commits `71a040b`, `777d67b`

### Counterexample

- job `d6ed8c981d294ba18241d83a27552ed6`
- observed result:
  - `status=completed`
  - `phase=wait`
  - `answer_chars=3044`
  - valid Gemini thread URL present

This confirms `#113` is not a total provider outage; it is a mixed recurrent issue family.

## Findings

### 1. `#113` is not one issue family

The GitHub issue body combines three operationally different families:

- `deep_think` selector / capability failure before productive answer generation
- anchor-only bogus completion after apparent success
- no-thread wait orphan / legacy wait-state drift

Treating them as one family makes historical queries noisy and weakens fix verification.

### 2. Failure mode B was the still-live bug on current `master`

The unresolved path was the anchor-only bogus completion:

- the answer-quality guard saw the Gemini UI anchor
- the sanitize step inferred `ui_noise_empty_after_sanitize`
- but still returned the original `Gemini 说` text
- so the executor did not downgrade the job

This batch fixed that narrow path by:

- returning empty cleaned text when sanitize leaves no body
- treating `ui_noise_empty_after_sanitize` as `GeminiAnswerContaminated`
- adding regression tests for both helper-level and executor-level behavior

Implementation commit:

- `6b64aaa` `fix(gemini): fail closed on anchor-only ui noise`

### 3. Failure modes A and C already have current-code mitigations

For intake purposes, A and C should be recorded as historical evidence plus family context, not as justification for reopening the whole Gemini stack in one batch.

- A already maps to current fallback logic and tests.
- C already maps to current send-lane and wait-timeout guards.

The remaining value is historical backfill:

- link old jobs
- link fix commits
- preserve the mixed symptom story without keeping the issue semantically broad

### 4. Current curated families are close, but not precise enough for B

Existing `issue_family_registry.json` already has:

- `gemini_followup_thread_handoff`
- `gemini_wait_no_progress`
- `completion_guard_false_downgrade`

But the bogus-short `Gemini 说` completion is neither a wait-no-progress issue nor a min-chars false downgrade. It needs its own provider-specific family identity.

## Proposed Issue-Domain Intake Shape

### New curated family

- `family_id`: `gemini_anchor_only_bogus_completion`
- `family_label`: `Gemini anchor-only bogus completion`

Suggested matcher terms:

- `geminianswercontaminated`
- `gemini 说`
- `ui_noise_empty_after_sanitize`
- `anchor-only`
- `completed_suspect_short_answer`

### Existing families to reuse

- `gemini_followup_thread_handoff`
  - for no-thread / unstable-thread evidence
- `gemini_wait_no_progress`
  - for stable-thread wait starvation or export drift

### Must-have objects

- `Issue`
- `IssueFamily`
- `Job`
- `FixCommit`
- `DocEvidence`
- `Verification`
- `UsageEvidence`

### Must-have fields

- `provider=gemini`
- `kind=gemini_web.ask`
- `preset`
- `job_id`
- `conversation_url`
- `error_type`
- `completion_quality`
- `phase`
- `phase_detail`
- `commit_sha`
- `source_ref`
- `source_locator`
- `excerpt`

### Must-have edges

- `Issue -> belongs_to_family -> IssueFamily`
- `Issue -> uses_job -> Job`
- `Issue -> fixed_by -> FixCommit`
- `Issue -> documented_in -> DocEvidence`
- `Issue -> validated_by -> Verification`
- `Issue -> proven_by_usage -> UsageEvidence`

## Narrow Approved Work Package Requested On #113

I am requesting approval on `#113` for the following narrow `issue_domain` intake batch:

1. register `gemini_anchor_only_bogus_completion` as a curated issue family
2. backfill `#113` evidence from the five cited jobs into the canonical issue plane
3. link historical mitigations for A and C to their fix commits instead of leaving them as live-open ambiguity
4. attach this batch's fix commit `6b64aaa` as the code-side resolution for the still-live anchor-only path
5. add one post-fix usage verification after a real Gemini run confirms the bogus-short completion no longer terminalizes as `completed`

## Explicit Non-Goals

This intake request does not ask to:

- redesign Gemini provider routing
- create a new non-issue-domain canonical consumer
- reopen broad EvoMap / KB / graph architecture
- auto-promote the issue into runtime behavior changes beyond the already-landed narrow fix

## Why This Is The Right EV / Issue-Domain Shape

`#113` now has enough real evidence to be useful historically, but only if it is narrowed.

The right value of the EV / issue-domain intake is:

- preserve the mixed symptom lineage
- separate still-live bug from already-mitigated historical families
- attach real jobs, real commits, and real verification
- make future graph queries answer:
  - what still needed a code fix
  - what was already mitigated
  - which family a new Gemini failure actually belongs to

That is higher-value than keeping `#113` as one broad narrative issue with no canonical family structure.
