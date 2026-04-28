# Current Consumer Site Asset Usage Audit v2

**Date:** 2026-04-28  
**Scope:** `labebe-gemini-demo/public`, `labebe-gemini-demo/dist`, and current product data references.  
**Purpose:** Keep the Labebe consumer website separate from Paperclip / AI demo assets and make asset rights posture explicit.

## Summary

| Metric | Count |
| --- | ---: |
| Product image files in current consumer public bundle | 26 |
| Product images referenced by current site product data | 26 |
| Extra product images available but not currently referenced | 0 |
| Exact local copies of `data/labebe/images` catalog files | 17 |
| Exact local copies of `data/labebe/live_probe_images_20260428` files | 9 |
| Backed by live catalog probe URL but not exact local hash copy | 0 |
| Assets blocked until origin verification | 0 |
| Video files inside current consumer public/dist bundle | 0 |

## Findings

1. The current consumer site no longer exposes Paperclip, Boss Gallery, AI Growth Studio, or Pro context routes/assets.
2. The consumer bundle contains product images only; no MP4/WebM/MOV files are shipped with the Labebe DTC site.
3. The active design uses catalog product photography as the visual source of truth. Seventeen files are exact copies from the older canonical image folder; nine files are exact copies from the 2026-04-28 live-probe image folder.
4. Extra product images remain in the public bundle because they are real catalog candidates for collection expansion. They are not currently displayed unless the product data references them.

## Usage Policy

| Asset class | Current DTC stance | Notes |
| --- | --- | --- |
| Exact catalog product image copies | Conditional | Acceptable for prototype and internal review; production needs brand permission / terms confirmation. |
| Live-probe catalog exact copies | Conditional | Acceptable for prototype; promote into the canonical data folder after review. |
| Live-probe catalog URL images | Conditional | URL-backed only; re-download into the canonical data folder before production handoff. |
| Unknown local images | Blocked | Do not use until origin and rights are verified. |
| MiniMax / AI-generated video | Blocked from consumer site | Internal presentation only unless synthetic labeling and brand/legal approval are added. |
| Paperclip / Boss Gallery videos | Blocked from consumer site | Presentation artifacts, not shopper-facing media. |
| QA screenshots and contact sheets | Internal only | Evidence artifacts, not consumer assets. |

## Production Clearance Queue

The audit has been converted into a production approval handoff:

- `production_asset_clearance_queue_v1.md`
- `production_asset_clearance_queue_v1.csv`

The queue contains all 26 active consumer-site product images. Every row is
marked `pending_brand_legal_review`; no asset is asserted as production-approved
by this audit. Reviewers must choose one of:

- `approve_for_dtc`
- `internal_only`
- `replace_before_launch`

## Current Consumer-Site Guardrail

The site must stay a pure Labebe replacement commerce experience:

- No Paperclip route.
- No AI Growth route.
- No Boss Demo route.
- No Pro context folder in `public` or `dist`.
- No synthetic or unknown-origin lifestyle image on consumer pages unless explicitly reviewed.
- No video in consumer bundle until footage provenance and rights are clear.

## Files

- CSV audit: `current_site_asset_usage_audit_v2.csv`
- Build source checked: `labebe-gemini-demo/src/data/products.ts`
- Product image source directory: `data/labebe/images`
