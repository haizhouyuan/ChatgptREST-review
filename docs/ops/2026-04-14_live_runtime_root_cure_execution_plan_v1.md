# 2026-04-14 Live Runtime Root-Cure Execution Plan v1

## Scope

This plan extends the earlier self-heal governance and export-reconciliation work. The remaining root-cure target is the live/runtime instability tail for `chatgpt_web.ask` and `gemini_web.ask`, especially the cases that were previously only contained by public-session projection instead of being eliminated earlier in worker/runtime behavior.

## Confirmed Residual Families

- `chatgpt_web.ask send-phase` with no thread evidence:
  - `verification_pending` / Cloudflare / Turnstile
  - `SSE stream timeout` / `stream ended without a json-rpc response`
  - prompt-surface drift around `Add files and more` / upload menu affordances
- `chatgpt_web.ask` input contract drift:
  - `input.file_paths` existed at enqueue time but no longer exist by the time the provider tries to send
- `gemini_web.ask` already had partial root-cure:
  - `GeminiBlankSendTimeout`
  - `GeminiConversationThreadMismatch`
  - `GeminiDriveAttachUnavailable`
- `chatgpt_web.ask wait/export` lag was already addressed via issue `#211`, so it is no longer the primary live/runtime root-cause family.

## Root-Cause Statement

The remaining defect was not just UI drift. It was truth drift across three layers:

1. Public session already knew some send-phase failures should be `same_session_repair`.
2. Worker still kept retrying those same failures until `MaxAttemptsExceeded`.
3. Repair/autofix governance still lacked a shared error-family contract for the ChatGPT send-phase manual-repair tail.

This produced a false sense of containment: the user-facing session looked safer, but the underlying runtime still wasted attempts and still produced noisy terminal families.

## Execution Goals

1. Unify same-session-repair classification so worker, public session, and repair gate use the same criteria.
2. Fail-close ChatGPT send-phase manual-repair families before they burn through cooldown loops.
3. Fail-close missing live attachments before the browser/driver path starts.
4. Verify the public MCP surface is still healthy and that `claudeminmax` can be selected through a real MCP scenario.

## Planned Changes

### Shared classification

- Add a shared core module for send-phase same-session-repair heuristics.
- Migrate public-session projection to that shared module.
- Extend repair gate to block Codex/SRE/autofix for these fail-closed families.

### Worker fail-close

- Add a ChatGPT worker fail-close path for explicit same-session-repair send families without thread evidence.
- Preserve ordinary generic `UiTransientError` retries unless they also match a concrete marker family.
- Keep Gemini blank-send behavior unchanged except for the shared-classification refactor.

### Attachment contract

- Add execution-time `input.file_paths` existence validation in the ChatGPT executor.
- Emit `AttachmentFileNotFound` before any UI action when files disappeared after enqueue.
- Project that family as `needs_input`, not as runtime remediation.

### Validation

- Narrow regression:
  - repair gate
  - worker fail-close
  - attachment preflight
  - public agent attachment guidance
- Broad regression:
  - worker / maint-daemon / public-session suites already covering retry budget and same-session-repair semantics
- Live validation:
  - public MCP health + transport validation
  - explicit `requested_executor=claudeminmax` advisor-agent scenario through the MCP wrapper

## Rollout Standard

Root-cure is only considered credible if all of the following hold:

- worker no longer converts these explicit ChatGPT send families into `MaxAttemptsExceeded`
- repair gate denies Codex/SRE/autofix for the new fail-closed families
- missing live attachments stop before browser interaction
- public MCP remains healthy after rollout
- at least one real MCP scenario explicitly selects `claudeminmax` and completes
