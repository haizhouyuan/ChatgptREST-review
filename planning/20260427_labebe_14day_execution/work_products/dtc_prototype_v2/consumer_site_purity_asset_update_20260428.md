# Consumer Site Purity and Asset Chain Update

**Date:** 2026-04-28  
**Scope:** `labebe-gemini-demo` consumer DTC prototype.  
**Decision:** The website is now treated as a pure Labebe replacement commerce site. Paperclip, AI Growth Studio, Boss Gallery, and Pro-context artifacts belong outside the consumer website.

## What Changed

1. Removed unused internal-demo source files from the DTC app:
   - `src/routes/AIGrowthDemo.tsx`
   - `src/routes/BossDemo.tsx`
   - `src/routes/DesignLibrary.tsx`
   - `src/data/designResearch.ts`
2. Removed stale Pro-context public assets from:
   - `labebe-gemini-demo/public/pro-context`
   - `labebe-gemini-demo/dist/pro-context`
3. Rebuilt the site after cleanup.
4. Re-ran string scan against `src`, `public`, and `dist`; no Paperclip / AI Growth / Boss / Pro-context strings remain.
5. Re-downloaded nine live-probe catalog images into:
   - `data/labebe/live_probe_images_20260428/`
6. Replaced current public product images for the live-probe-backed SKUs so all 26 consumer-site product images now have a local source chain:
   - 17 exact copies from `data/labebe/images`
   - 9 exact copies from `data/labebe/live_probe_images_20260428`

## Latest Browser QA

| View | Evidence | Result |
| --- | --- | --- |
| Homepage desktop | `qa/labebe-commerce-v2/home-clean-consumer-desktop-v1.png` / `.json` | `horizontalOverflow=false` |
| Homepage mobile | `qa/labebe-commerce-v2/home-clean-consumer-mobile-v1.png` / `.json` | `horizontalOverflow=false` |
| Crocodile PDP desktop | `qa/labebe-commerce-v2/crocodile-pdp-clean-consumer-desktop-v1.png` / `.json` | `horizontalOverflow=false` |

## Asset Audit

New audit files:

- `work_products/media_asset_probe/current_site_asset_usage_audit_v2.md`
- `work_products/media_asset_probe/current_site_asset_usage_audit_v2.csv`
- `work_products/media_asset_probe/current_site_asset_usage_audit_v2_manifest.json`
- `work_products/media_asset_probe/build_current_site_asset_usage_audit.mjs`

Current audit result:

- Product image files in current consumer public bundle: 26
- Product images referenced by current site product data: 26
- Consumer bundle video files: 0
- Assets blocked until origin verification: 0
- Production stance: conditional until Labebe confirms brand/legal usage rights for catalog images.

## Guardrail

The DTC prototype may use product and shopper-facing commerce ideas only. Any future Paperclip, AI, Pro, claim-gate, or internal automation demo must live in a separate presentation surface or static output folder, not in this consumer site.
