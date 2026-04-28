# Boss Gallery v0 — Design Record

Generated: 2026-04-27

## Decision

AI/Paperclip demonstrations are kept separate from the Labebe consumer DTC
website. The Boss Gallery is an internal presentation surface that shows AI
application outcomes and control gates.

## Inputs

- Existing result-first Paperclip/Labebe wow demo under
  `paperclip_runtime_duel/outputs/labebe_wow/`.
- Pro-recommended Demo A-F tracks from prior review.
- Commerce Decision Layer and Claim Gate constraints from this execution plan.

## Output

Static internal gallery:

`paperclip_runtime_duel/outputs/boss_gallery_v0/index.html`

Latest v0.1 update:

- Demo A-F cards now include evidence IDs and gate states.
- Added detail contract section for `BG-B` and `BG-F`.
- Added evidence drawer with video, storyboard, poster, screenshot and strategy paths.
- Re-ran desktop/mobile CDP screenshots with no horizontal overflow.

Latest v0.2 update:

- Added Paperclip import-ready issue map for all six demo tracks.
- Added Boss Gallery claim ledger for blocked, allowed-with-source and
  synthetic-label claims.
- Copied the issue map and claim ledger into the static Boss Gallery output
  folder and linked them from the evidence drawer.
- Re-ran Browser Harness P0 smoke after the page update; DTC/Boss representative
  routes passed 5/5.
- Re-rendered desktop/mobile Boss Gallery walkthrough videos after adding the
  evidence map section.

Latest v0.3 update:

- Bound the six Boss Gallery demo rows to existing Paperclip issues:
  - Demo A -> `LAB-2`
  - Demo B -> `LAB-3`
  - Demo C -> `LAB-4`
  - Demo D -> `LAB-5`
  - Demo E -> `LAB-7`
  - Demo F -> `LAB-8`
- Wrote `boss_gallery_evidence` documents to those six Paperclip issues.
- Wrote `boss_gallery_index` to `LAB-9` and added a summary comment.
- Updated the CSV `live_paperclip_issue` field with actual Paperclip identifiers
  and UUIDs.
- Updated the static evidence drawer copy from "import-ready" to "bound to
  existing issues".

## Purpose

- Give decision makers a place to see AI capability without contaminating the
  public consumer site.
- Show "wow result" first, then show controls.
- Keep every impressive claim tied to human review and evidence status.

## Demo Tracks Represented

- Demo A: Design Opportunity Radar
- Demo B: VOC to New Concept
- Demo C: Sketch to Concept
- Demo D: Custom Toy Kitchen Builder
- Demo E: Design Director + DFM/Safety Preflight
- Demo F: Concept-to-Market Asset Matrix

## Claim Gate

The page explicitly blocks certification, demand, cost, availability, production
CAD, fake ratings, fake reviews, and fake awards.

## QA Evidence

- `qa/labebe-commerce-v2/boss-gallery-desktop-cdp-v3.png`
- `qa/labebe-commerce-v2/boss-gallery-mobile-cdp-v2.png`
- `qa/browser-harness-p0-smoke-20260428/browser_harness_matrix_report.md`

Both CDP captures reported `horizontalOverflow=false`.
