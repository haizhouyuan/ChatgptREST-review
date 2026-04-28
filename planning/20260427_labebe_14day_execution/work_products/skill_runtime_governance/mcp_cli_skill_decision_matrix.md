# MCP / CLI / Skill Decision Matrix

Created: 2026-04-27

## Decision Principle

Use the smallest capability surface that can reliably produce evidence.

```text
Skill = procedural memory and bundled scripts.
CLI = deterministic execution surface.
MCP = interactive tool surface that needs live state or remote service calls.
Browser Harness = controlled execution layer for browser state, screenshots, and visual QA.
Paperclip = issue/evidence/control plane.
```

Do not turn every reusable idea into an MCP. Do not turn every workflow into a skill. Do not give visual models direct execution authority.

## Matrix

| Need | Prefer | Use When | Avoid When |
|---|---|---|---|
| Agent needs domain procedure | Skill | The workflow is reusable and mostly textual, with optional scripts | It requires hidden live state or broad permissions |
| Repeatable local command | CLI/script | The behavior can be validated with inputs/outputs and exit codes | The task needs human-like interpretation every step |
| Live app/service integration | MCP | The agent needs structured calls into an authenticated service | A simple CLI can do the same with less state |
| Browser page operation | Browser Harness over Playwright/CDP/Browser Use | Need screenshot, DOM, accessibility, console, or recoverable UI state | Letting a VLM freely click is tempting but unsafe |
| Visual quality judgment | Vision provider behind schema | Need black-screen, overlap, visual hierarchy, or UX review | Model output is unstructured prose with no screenshot references |
| Long-running multi-agent coordination | Paperclip issue/evidence model | Need owners, artifacts, gates, and resumability | Treating "agent says done" as completion |
| Machine-wide runtime mutation | maint policy path | Concrete blocker, explicit approval, config diff, rollback | Sprint work merely "might need it" |

## Browser Automation Split

Use this split for ChatGPTREST, Paperclip demo, and Labebe website QA:

```text
Control plane:
  Paperclip / ChatGPTREST / Codex planner

Execution layer:
  Browser Harness

Deterministic tools:
  Playwright / CDP / Browser Use CLI where useful

Judgment providers:
  local/API vision model -> structured ScreenState, ElementTarget,
  VisualQualityReview, CompletionState
```

The vision provider should answer "what state is the page in?" and "where is the likely target?" The deterministic action layer should perform clicks, typing, waits, screenshots, exports, and evidence writes.

## Fixed Schemas For Vision

### `ScreenState`

```json
{
  "state": "ready|loading|blocked|login_required|black_screen|error|unknown",
  "confidence": 0.0,
  "evidence": ["short visual reasons"],
  "screenshot_path": "/abs/path.png"
}
```

### `ElementTarget`

```json
{
  "goal": "click checkout",
  "candidates": [
    {"bbox": [0, 0, 100, 40], "text": "Checkout", "confidence": 0.0}
  ],
  "action_safe": true
}
```

### `VisualQualityReview`

```json
{
  "surface": "DTC home mobile",
  "score": 0,
  "pass": false,
  "issues": [
    {"severity": "critical|high|medium|low", "description": "...", "screenshot_path": "..."}
  ]
}
```

### `CompletionState`

```json
{
  "complete": false,
  "reason": "thinking|prompt_echo|partial|final|stale",
  "confidence": 0.0,
  "evidence": ["..."]
}
```

## Runtime Placement For This Sprint

| Capability | Placement | Status |
|---|---|---|
| DTC website browser QA | Local Browser Harness scripts in `runtime_qa_templates/` | Implemented as CDP screenshot/capture scripts |
| Cart/PDP click evidence | Local Browser Harness action script | Implemented with `browser_harness_capture.mjs` |
| Paperclip Boss Gallery visual QA | Same Browser Harness templates | Use screenshots and visual acceptance docs |
| ChatGPTREST Pro/Gemini automation | Existing ChatGPTREST governance only | Do not open new advisory tasks for this sprint |
| MiniMax media generation | Existing MiniMax shared skill and governed credentials | Available, no quota-consuming generation required yet |
| GStack | Method reference only | Do not install/import live runtime |
| Multica | Read-only archive | Do not dispatch or mutate |

## Stop Rules

- If a task needs broad browser auth, secret roots, or production accounts, stop and record a blocker.
- If a vision model suggests a destructive or financial action, ignore it unless deterministic policy allows it.
- If an MCP starts adding load or stale-state risk, prefer a CLI/script snapshot.
- If a skill update would need machine-wide config mutation, defer to maint plan and document exact blocker.

## Acceptance

This matrix is accepted when future agents can decide:

- when to write a skill instead of an MCP;
- when to use Browser Harness instead of direct browser-use autonomy;
- when to keep Paperclip as control plane instead of another runtime;
- when a proposed runtime mutation belongs in maint, not in Toyresearch.
