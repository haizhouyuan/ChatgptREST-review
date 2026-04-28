# Browser Harness P0 Contract

Status: P0 executable
Owner: Codex main controller

## Purpose

Browser Harness P0 is a QA/evidence support layer. It is not a new platform, not a new autonomous browser agent, and not a replacement for Paperclip or ChatGPTREST.

## Allowed Responsibilities

- open a local/Tailscale/public URL;
- capture desktop/tablet/mobile screenshots;
- capture console errors;
- verify HTTP/page load status;
- verify core navigation and route availability;
- detect blank/black screens;
- detect obvious text overflow and incoherent overlap;
- produce evidence bundle paths;
- optionally ask a vision model to judge screenshot quality.

## Forbidden Responsibilities

- autonomous browsing strategy;
- external account operations;
- ChatGPT web automation replacement;
- Pro/Gemini submission;
- deciding design direction;
- editing code;
- publishing;
- claiming a page is boss-ready without human/main-controller acceptance.

## Required Inputs

- URL or local server command.
- Expected routes.
- Viewports.
- Critical user flows.
- Screenshot output directory.
- Claims/visual risk checklist.

## Required Outputs

- `browser_qa_report.md`
- screenshots per route and viewport;
- `*.metrics.json` sidecars with route state, visible text length, CTA inventory,
  scroll/overflow status, likely blank state, console/log entries and network
  failures;
- console log summary;
- link/route check summary;
- visual defect notes;
- evidence manifest.

## Vision Model Role

Allowed:

- judge screenshot quality;
- identify likely overlap/overflow/blank sections;
- point to visual defects;
- produce AI-slop critique.

Forbidden:

- directly controlling browser actions;
- deciding final acceptance;
- making factual claims about products.

## Current P0 Implementation

Implemented files:

- `browser_harness_capture.mjs`
- `browser_harness_run_matrix.mjs`
- `browser_harness_smoke_matrix.json`
- `browser_harness_service.mjs`

Validated smoke output:

- `qa/browser-harness-p0-smoke-20260428/browser_harness_matrix_report.md`
- `qa/browser-harness-service-smoke-20260428/browser_harness_service_smoke_report.md`

Smoke result: 5 / 5 pass across DTC desktop, DTC mobile, Pink Unicorn PDP,
Boss Gallery desktop and Boss Gallery mobile. Acceptance checks included command
success, metrics parsing, no horizontal overflow, nonblank page state and no
blocking console errors.

Service smoke result: pass for `GET /health`, `GET /schema`, `POST /capture`
against the DTC homepage mobile viewport, and `POST /matrix` against a one-row
DTC homepage desktop matrix. Shared use should bind to localhost by default and
set `BROWSER_HARNESS_TOKEN` when another process calls it.

## Service API

The service wrapper is intentionally thin:

```bash
BROWSER_HARNESS_PORT=8791 \
node planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/browser_harness_service.mjs
```

Available endpoints:

- `GET /health`
- `GET /schema`
- `POST /capture`
- `POST /matrix`

Boundary: the service is still QA/evidence support only. It does not manage
authenticated sessions, submit external model jobs, choose design direction,
edit code, or publish.
