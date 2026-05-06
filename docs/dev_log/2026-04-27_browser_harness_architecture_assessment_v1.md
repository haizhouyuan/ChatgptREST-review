# Browser Harness Architecture Assessment

Date: 2026-04-27

## Executive Decision

ChatGPTREST should adopt the Browser Harness direction, but only as a shared, auditable browser execution and evidence layer. It should not become another autonomous browser agent, and it should not expose Browser Use, Chrome DevTools MCP, Playwright, OpenCLI, or CLI-Anything directly to coding agents as new top-level tools.

The correct boundary is:

```text
ChatGPTREST / Paperclip / Codex
  control plane: jobs, permissions, idempotency, provider selection, evidence contracts, approvals

Browser Harness
  execution and observation plane: browser actions, screen state, screenshots, DOM/snapshot, console/network capture, visual checks, evidence bundles

Browser Use / Playwright / Chrome DevTools MCP / OpenCLI
  backend adapters, selected by policy; not public agent entrypoints
```

The first version should be contract-first and read-mostly. It should convert current scattered browser observations into stable `ScreenState`, `CompletionState`, `VisualQualityReview`, and `BrowserEvidenceBundle` records.

## Sources Reviewed

External sources:

- Browser Use CLI reference: `https://www.mintlify.com/browser-use/browser-use/guides/cli`
  - Confirms a persistent CLI session-server model, low-latency command execution, `state`, `screenshot`, `click`, `type`, `wait`, `eval`, local/remote browser modes, profiles, sessions, and `--mcp`.
- Browser Use MCP server docs: `https://docs.browser-use.com/open-source/customize/integrations/mcp-server`
  - Confirms local MCP exposure for `browser_navigate`, `browser_click`, `browser_type`, `browser_get_state`, scroll, tab/content/session tools, plus a last-resort autonomous agent tool.
  - Explicitly warns that the MCP server has access to the browser and file system, should only be connected to trusted clients, and should be sandboxed for untrusted automation.
- Chrome DevTools MCP blog: `https://developer.chrome.com/blog/chrome-devtools-mcp`
  - Positions Chrome DevTools MCP as live Chrome debugging for AI agents, especially for verifying UI behavior, network/console diagnostics, and performance work.
- Chrome DevTools MCP GitHub: `https://github.com/ChromeDevTools/chrome-devtools-mcp`
  - Lists input, navigation, emulation, performance, network, debugging, screenshot/snapshot, extension, and memory tools.
  - Documents configuration to connect to a running debuggable Chrome and options like slim mode, network header redaction, and usage-statistics opt-out.

Local ChatGPTREST evidence:

- `ops/maint_daemon.py`
  - Existing `ui_canary` calls provider `self_check`, optionally calls `capture_ui`, writes incidents and snapshots, and records CDP version.
  - Current live state is weak: `chatgptrest-maint-daemon.service` is failed since 2026-04-22, and `artifacts/monitor/ui_canary/latest.json` is stale. Latest snapshot files are from 2026-04-25.
- `ops/viewer_watchdog.py`
  - Checks process/port/noVNC HTTP health and can restart viewer components, but does not inspect pixels, page state, black-screen content, layout quality, or screenshots.
- `chatgptrest/ops_shared/provider.py`
  - Provider mapping already knows `self_check`, `capture_ui`, `refresh`, `regenerate`, `blocked_status`, and `rate_limit_status` for ChatGPT and Gemini.
- `chatgptrest/executors/repair.py`
  - Can call provider `self_check` and `capture_ui` during repair checks, but its output is still a repair-specific report, not a normalized browser evidence object.
- `chatgpt_web_mcp/playwright/evidence.py` and provider capture implementations
  - Already produce screenshots, HTML, and provider-specific UI references.
  - Recent artifact example: `artifacts/jobs/77f85d8aad654320ab1696b56ed79a4b/chatgpt_ui_snapshots/manifest.json` has screenshots of page, model selector, thinking pill, and tool menus.
- `chatgptrest/worker/worker.py`
  - Wait logic now detects prompt echo and stale active-finalization progress, but it still relies primarily on export/event text. It lacks a normalized visual assertion that the page is actually thinking, blocked, blank, or showing a real assistant answer.
- Toyresearch incident retrospective:
  - `/vol1/1000/projects/toyresearch/planning/20260427_chatgptrest_parallel_review_incident_retrospective.md`
  - Shows the precise failure class: old Pro job repeatedly observed a 472-character prompt echo, stayed `in_progress`, and occupied a scarce in-flight slot.

## Independent Judgment

The user diagnosis is correct: several recent incidents were not only rate-limit or wait-loop problems. They were observability-boundary problems.

ChatGPTREST had text export, events, worker state, and partial UI capture, but it did not have a reliable shared answer to:

- What is on the screen now?
- Is the model actually thinking, or did the UI stop progressing?
- Is the visible text a prompt echo, stale answer, partial answer, or final answer?
- Is the page blocked by Cloudflare, verification, frontend cooldown, login, blank screen, or an inactive composer?
- If a job is stuck, what visual and DOM evidence proves it?

That missing layer caused humans and agents to infer too much from indirect signals. The right fix is not more aggressive polling, more rescue prompts, or raw Browser Use exposure. The right fix is a small Browser Harness contract that every runtime path can use.

## What To Adopt

Adopt these ideas:

1. **Contract-first Browser Harness.**
   - Define stable interfaces before selecting backends.
   - Use backend adapters only behind policy.

2. **Shared evidence objects.**
   - Use one evidence bundle schema for ChatGPTREST, Paperclip, website QA, and incident reports.
   - Avoid separate ad hoc `repair_report`, `ui_canary_probe`, provider manifest, and visual QA formats drifting apart.

3. **Vision-as-judge, not executor.**
   - A visual model may classify a screenshot and propose targets.
   - It must not directly click, type, refresh, send, upload, or cancel.
   - Deterministic action code remains the only actor.

4. **Browser Use as backend adapter, not public tool surface.**
   - Useful for fast persistent browser sessions and generic browser commands.
   - Risky if connected directly to Codex/Paperclip because it can expose browser and filesystem control.

5. **Chrome DevTools MCP as diagnostic adapter.**
   - Best for console, network, performance trace, DOM snapshot, screenshots, and CDP debugging.
   - Not sufficient as a visual quality or completion-state judge by itself.

6. **Paperclip reuse.**
   - The same Browser Harness should serve website and Boss Demo QA: desktop/mobile screenshots, overflow checks, image loading, first viewport, interaction readiness, visual quality, and evidence annotations.

## What To Reject

Reject these implementation paths:

- Do not add Browser Use MCP as a direct default MCP server for all agents.
- Do not let a visual model issue direct browser actions.
- Do not treat screenshot archival as QA.
- Do not broaden access to the shared authenticated Chrome profile.
- Do not replace ChatGPTREST job/idempotency/rate-limit logic with a browser-agent loop.
- Do not increase prompt/export polling frequency to compensate for missing state classification.
- Do not auto-enable remote/cloud browser modes for production credentials.
- Do not put OpenCLI or CLI-Anything directly into production until they pass quarantine, adapter, and permission review.

## Proposed Contract Surface

The Browser Harness should expose a small northbound contract:

```text
open_page
get_state
take_screenshot
click
type
wait
eval
export_evidence
inspect_screen_state
judge_completion_state
review_visual_quality
```

Action methods are policy-restricted. Observer methods are safer and should be the P0 default.

### ScreenState

Fields:

```text
provider
url
title
timestamp
composer_ready
thinking_visible
login_required
verification_pending
frontend_cooldown
cloudflare_or_turnstile
black_screen
blank_or_broken_layout
network_error_visible
modal_or_overlay_present
model_label
confidence
signals
evidence_refs
```

### CompletionState

Fields:

```text
job_id
conversation_url
final
still_thinking
prompt_echo
stale_answer
partial_answer
blocked
answer_chars_visible
answer_chars_exported
delta_chars
role_source
prompt_overlap_score
last_meaningful_progress_at
recommended_next_action
reason
evidence_refs
```

### VisualQualityReview

Fields:

```text
target_url
viewport
desktop_ok
mobile_ok
first_viewport_ok
text_overflow
layout_overlap
image_missing
button_clickable
loading_or_blank_area
ai_slop_score
boss_demo_ready
issues
annotated_screenshot_refs
```

### BrowserEvidenceBundle

Fields:

```text
bundle_id
job_id
provider
created_at
scope
redaction_level
screenshots
dom_snapshot
accessibility_snapshot
console_messages
network_summary
performance_trace_ref
export_ref
screen_state_ref
completion_state_ref
visual_quality_review_ref
action_log
policy_decisions
```

## ChatGPTREST Integration Plan

P0 should be additive and low-risk:

1. **Create schemas first.**
   - Add versioned JSON schemas under `docs/contracts/browser_harness/`.
   - Do not alter worker behavior until schemas and fixtures are reviewed.

2. **Add a local `browser_harness` package as an adapter layer.**
   - Adapter A: wrap existing Playwright/CDP and provider `capture_ui` outputs.
   - Adapter B: wrap Chrome DevTools MCP for console/network/performance/snapshot.
   - Adapter C: optional Browser Use adapter behind env guard and quarantine.

3. **Normalize existing evidence.**
   - Convert `chatgpt_web_capture_ui` / `gemini_web_capture_ui` manifests to `BrowserEvidenceBundle`.
   - Convert `ui_canary` probe summaries to `ScreenState`.
   - Convert wait partial/progress/prompt echo events to `CompletionState`.

4. **Use Browser Harness only on anomaly triggers at first.**
   - Prompt echo plateau.
   - Wait no-progress timeout pending.
   - Repeated `browser_retry_scheduled`.
   - Export says in-progress but no delta.
   - Cloudflare/verification/frontend cooldown suspected.
   - Missing export while browser page may show final content.

5. **Emit explicit events.**
   - `browser_screen_state_observed`
   - `browser_completion_state_observed`
   - `browser_evidence_bundle_created`
   - `browser_visual_quality_reviewed`
   - `browser_harness_action_blocked_by_policy`

6. **Keep actions deterministic.**
   - P0 allows observation and evidence export.
   - P0 may allow refresh only under current existing repair policy.
   - P0 must not introduce new send/click/type authority.

## How This Would Have Helped The Pro Incident

For job `076c4a2b073b495d87bb93a7d097b12a`, the harness should have produced:

```text
ScreenState:
  thinking_visible: false or low confidence
  composer_ready: true/false
  frontend_cooldown: false/true if modal visible
  verification_pending: false/true if challenge visible

CompletionState:
  prompt_echo: true
  stale_answer: true if visible/exported text is previous prompt
  partial_answer: false
  delta_chars: 0
  recommended_next_action: mark_needs_followup_or_manual_review

EvidenceBundle:
  screenshot of conversation
  DOM or accessibility snapshot
  exported conversation hash
  event timeline
```

That would have changed the incident from "wait and hope" to "bounded stuck state with visual proof." It also would have freed the in-flight slot earlier or produced a clear `needs_followup` state.

## Paperclip / Labebe Integration

Paperclip should consume the same Browser Harness results as a gate, not build its own browser loop.

P0 Paperclip gate:

```text
paperclip_visual_qa_gate:
  input:
    target_url
    expected_viewports
    scenario_name
  output:
    BrowserEvidenceBundle
    VisualQualityReview
  fail_conditions:
    page blank
    black screen
    missing hero/product images
    text overflow
    obvious overlap
    mobile first viewport unusable
    boss_demo_ready=false for demo routes
```

For Labebe website work, this prevents "it loads" from being accepted as "it is good." The gate should capture desktop and mobile screenshots and require judgment about visual credibility, product visibility, and executive-demo readiness.

## Current ChatGPTREST Gaps

1. `ui_canary` is conceptually right but operationally stale right now.
   - `chatgptrest-maint-daemon.service` is failed since 2026-04-22.
   - `artifacts/monitor/ui_canary/latest.json` reports stale data, with latest snapshots from 2026-04-25.
   - This explains part of the recent blind spot.

2. `viewer_watchdog` checks transport health, not visual content.
   - It can say noVNC is reachable.
   - It cannot say whether Chrome is black, blank, on a cooldown modal, or visually broken.

3. `capture_ui` creates useful artifacts but not authoritative state.
   - It stores screenshots and manifests.
   - It does not currently output `ScreenState` or `CompletionState`.

4. Worker wait logic is improving but still text-first.
   - Recent prompt-echo fixes reduce one failure mode.
   - A visual observer is still needed to distinguish true thinking from stagnant UI or prompt echo.

5. There is no common visual QA contract for client demos.
   - Website/Paperclip reviews can still confuse screenshot existence with design acceptance.

## P0 Deliverables

Create a small project named `browser-harness-p0` with these deliverables:

- `docs/contracts/browser_harness/browser_harness_contract.schema.json`
- `docs/contracts/browser_harness/screen_state.schema.json`
- `docs/contracts/browser_harness/completion_state.schema.json`
- `docs/contracts/browser_harness/visual_quality_review.schema.json`
- `docs/contracts/browser_harness/evidence_bundle.schema.json`
- `docs/dev_log/YYYY-MM-DD_browser_harness_p0_walkthrough_v1.md`
- `artifacts/browser_harness/examples/chatgpt_prompt_echo/`
- `artifacts/browser_harness/examples/gemini_deepthink/`
- `artifacts/browser_harness/examples/labebe_desktop_mobile/`

Acceptance:

1. ChatGPT/Gemini read-only smoke:
   - Opens current page or existing conversation.
   - Produces `ScreenState`, `CompletionState`, and `BrowserEvidenceBundle`.
   - Sends no prompts.

2. Prompt-echo fixture:
   - Detects prompt echo as `prompt_echo=true`.
   - Does not classify it as progress.

3. Frontend blocked fixture:
   - Detects cooldown / verification / Cloudflare-like states when visible.
   - Preserves screenshots and DOM evidence.

4. Paperclip/Labebe visual smoke:
   - Captures desktop and mobile.
   - Produces `VisualQualityReview`.
   - Flags text overflow, missing images, blank screens, broken layout, and not boss-demo-ready.

5. Safety gate:
   - Vision output is advisory.
   - Any proposed action must be separately approved by deterministic policy.

## Rollout Order

1. Document schemas and examples.
2. Implement read-only adapter around existing `capture_ui` and `self_check`.
3. Add offline fixture tests for prompt echo, blank screen, cooldown modal, and layout overflow.
4. Wire anomaly-triggered evidence bundle creation into worker wait path, initially behind env flag.
5. Convert `maint_daemon` `ui_canary` to emit `ScreenState`.
6. Add Paperclip visual gate consumer after ChatGPTREST evidence path is stable.
7. Evaluate Browser Use CLI/MCP and Chrome DevTools MCP as adapters after the local Playwright/CDP contract is proven.

## Immediate Operational Notes

- Do not restart `chatgptrest-maint-daemon.service` blindly. Its current unit includes auto-pause, repair, Codex SRE analyze, and capture behavior, so it may affect live client use. The safe next step is to define a read-only canary mode or explicitly review its drop-ins before re-enabling.
- Do not submit more Pro smoke jobs to test this. Use existing conversations, screenshots, fixtures, and offline captures.
- If a client must keep using ChatGPTREST before P0 is built, prefer durable background jobs and avoid depending on "activity pane looks active" as proof.

## Final Recommendation

Adopt Browser Harness as a P0 AI Runtime Governance capability.

Do it as:

```text
shared eyes + evidence + bounded recovery
```

Not as:

```text
new browser brain with direct action authority
```

The first useful version is small: deterministic browser observation, normalized state classification, screenshots/DOM/console evidence, and visual quality review. It should make ChatGPTREST less blind during Pro/Gemini incidents and give Paperclip a real visual QA gate for websites and demos.
