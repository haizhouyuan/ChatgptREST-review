# Browser Harness P0 Implementation Plan

Created: 2026-04-27

## Scope

Browser Harness is a shared execution and evidence layer for:

- Labebe DTC website QA;
- Paperclip/Boss Gallery visual QA;
- future ChatGPTREST/Web UI state evidence;
- mobile/desktop screenshots;
- limited deterministic click-flow capture.

It is not a new brain, not a new autonomous agent, and not a replacement for Paperclip or ChatGPTREST.

## Current Local Implementation

Implemented sprint-local scripts:

```text
planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/capture_cdp_screenshot.mjs
planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/browser_harness_capture.mjs
planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/browser_harness_run_matrix.mjs
planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/browser_harness_service.mjs
planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/spa_static_server.py
```

Current capabilities:

- serve Vite SPA routes through fallback static server;
- open Chrome headless through CDP;
- set desktop/mobile metrics;
- capture viewport screenshots;
- return URL, title, scroll dimensions, horizontal overflow status;
- run a bounded action script before capture;
- extract visible text and button/link inventory for evidence.
- capture console/log entries, exceptions, and network failures;
- write `*.metrics.json` sidecars next to screenshots;
- run a route/view matrix from JSON and produce Markdown/JSON reports.
- expose a localhost HTTP service wrapper for downstream Paperclip /
  ChatGPTREST integration, with `GET /health`, `GET /schema`, `POST /capture`,
  and `POST /matrix`.

Validated surfaces:

- Labebe DTC home desktop/mobile;
- Labebe PDP desktop;
- Labebe collection mobile;
- Labebe cart drawer mobile click flow;
- Boss Gallery desktop/mobile in earlier QA.

## P0 Contract

Minimum Browser Harness command set:

| Capability | Status | Notes |
|---|---|---|
| `open` | covered inside capture scripts | Navigation via CDP `Page.navigate` |
| `state` | partial | Returns URL/title/text/buttons/scroll/overflow |
| `screenshot` | implemented | PNG viewport capture |
| `click/action` | partial | Bounded JS action script, not freeform agent clicking |
| `mobile metrics` | implemented | CDP device override |
| `console errors` | implemented | Captures `Runtime.consoleAPICalled`, exceptions, `Log.entryAdded`; ignores favicon 404 as non-blocking |
| `accessibility tree` | future | Add `Accessibility.getFullAXTree` if needed |
| `vision inspect` | future | Call local/API vision model with fixed schema |
| `evidence manifest` | partial | Matrix runner writes JSON/Markdown reports; project manifest still updated manually |
| `service API` | implemented local P0 | `browser_harness_service.mjs`, localhost by default, optional `BROWSER_HARNESS_TOKEN` |

## Why This Architecture

The previous ChatGPTREST incidents and website QA misses show that DOM/export-only evidence is not enough. Browser work needs:

- screenshot;
- DOM/text state;
- action inventory;
- route and viewport metrics;
- console state;
- visual judgment;
- durable artifact paths.

But visual models should judge state, not directly execute actions. Deterministic CDP/Playwright commands should click, type, wait, capture, and export.

## Immediate Next Implementation Steps

1. Add accessibility-tree extraction when a concrete selector/UX problem needs it.
2. Add a vision provider interface later:
   ```text
   disabled | local | api
   ```
3. Add optional full-page screenshot acceptance rules beyond the current capture
   mode flag.
4. Keep all browser auth/session work outside this sprint unless a concrete
   blocker appears.

## Service-Mode Smoke

Command:

```bash
BROWSER_HARNESS_PORT=8791 \
node planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/browser_harness_service.mjs
```

Validated:

- `GET /health`
- `GET /schema`
- `POST /capture`
- `POST /matrix`

Evidence:

- `qa/browser-harness-service-smoke-20260428/browser_harness_service_smoke_report.md`
- `qa/browser-harness-service-smoke-20260428/health.json`
- `qa/browser-harness-service-smoke-20260428/schema.json`
- `qa/browser-harness-service-smoke-20260428/capture.json`
- `qa/browser-harness-service-smoke-20260428/matrix.json`
- `qa/browser-harness-service-smoke-20260428/service-home-mobile.png`
- `qa/browser-harness-service-smoke-20260428/service-home-mobile.metrics.json`
- `qa/browser-harness-service-smoke-20260428/matrix-output/browser_harness_matrix_report.md`
- `qa/browser-harness-service-smoke-20260428/matrix-output/browser_harness_matrix_report.json`

Capture result: DTC homepage mobile viewport, `horizontalOverflow=false`,
`likelyBlank=false`, `hasConsoleErrors=false`, `incompleteImages=0`.

Matrix result: one-row DTC homepage desktop matrix, `1 / 1` pass.

## 2026-04-28 Smoke

Command:

```bash
node planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/browser_harness_run_matrix.mjs \
  planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/browser_harness_smoke_matrix.json \
  qa/browser-harness-p0-smoke-20260428
```

Result:

- 5 / 5 pass.
- DTC homepage desktop/mobile: pass.
- Pink Unicorn PDP desktop: pass.
- Boss Gallery desktop/mobile: pass.
- Favicon 404 is recorded but ignored as non-blocking.

## Stop Rules

- No production account browser actions.
- No broad credential/session capture.
- No uncontrolled VLM clicking.
- No hidden service restart.
- No ChatGPTREST/Gemini Web job creation as part of DTC/Boss QA.

## Acceptance

Browser Harness P0 is sufficient for this masterplan when it can produce:

- desktop and mobile screenshots;
- horizontal overflow result;
- visible text and CTA inventory;
- bounded click-flow evidence for cart/PDP;
- local HTTP capture/matrix wrapper for Paperclip / ChatGPTREST callers;
- evidence paths included in the final masterplan;
- clear next steps for console and vision provider expansion.
