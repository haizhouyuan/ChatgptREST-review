# Runtime QA Templates Handoff

Worker: Codex main controller
Date: 2026-04-27
Updated: 2026-04-28

## Summary

Created Browser Harness P0 and visual QA templates. These are support artifacts
only and do not create a new Browser/Vision platform.

2026-04-28 update: the P0 harness now includes executable CDP capture and a
matrix runner. It remains a QA/evidence utility, not an autonomous browser
agent.

## Outputs

- `browser_harness_p0_contract.md`
- `browser_qa_report_template.md`
- `design_review_report_template.md`
- `visual_ai_slop_checklist.md`
- `evidence_manifest.json`
- `browser_harness_capture.mjs`
- `browser_harness_run_matrix.mjs`
- `browser_harness_smoke_matrix.json`
- `qa/browser-harness-p0-smoke-20260428/browser_harness_matrix_report.md`

## What The Main Controller Can Trust

- Scope is constrained to QA/evidence.
- Templates explicitly check AI-template/generic design risk.
- The executable harness can capture screenshots, sidecar metrics JSON, visible
  text/CTA inventory, horizontal overflow, likely blank state, console/log
  entries, network failures, and bounded JS action flows.
- The smoke matrix passed 5/5 on DTC desktop/mobile, Pink Unicorn PDP, and Boss
  Gallery desktop/mobile.

## Known Limitations

- Vision-provider judgment is still a planned extension; current P0 uses DOM,
  browser metrics, screenshots, and deterministic CDP capture.
- Favicon 404 entries are recorded but ignored as non-blocking by default.
- The harness does not manage authenticated sessions or production accounts.
- The harness does not decide design direction or edit code.

## Recommended Next Step

Use `browser_harness_run_matrix.mjs` for repeatable route/view QA, then attach
the generated screenshots and `*.metrics.json` sidecars to the relevant evidence
manifest.
