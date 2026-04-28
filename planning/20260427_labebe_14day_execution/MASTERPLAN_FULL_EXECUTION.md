# Labebe / Paperclip Masterplan Full Execution

Created: 2026-04-27
Status: execution package ready for user裁决

## 0. North Star

The work is not "make one prettier page." The masterplan has two separated deliverable systems:

1. **Labebe DTC Website Replacement**
   - A pure consumer independent-store prototype for Labebe.
   - No Paperclip, no AI workflow, no internal claim gate, no boss demo navigation.
   - Built around real Labebe product facts, room/age/gift/play shopping paths, PDPs, cart interaction, and mobile/desktop QA.

2. **Paperclip / Boss Gallery AI Business Result Demo**
   - A separate internal executive gallery showing what AI can do for Labebe after product facts and controls exist.
   - Result first, then governance: concepts, channel assets, Claim Gate, evidence drawer.
   - Not part of the consumer site.

The shared foundation is:

- product fact and market identity layer;
- design research and commerce decision layer;
- media/video presentation strategy;
- Browser Harness visual QA;
- skill/runtime governance and maint/Paperclip/Multica/GStack backlog absorption.

## 1. Scope Confirmation

The completed package covers the full range the user asked to include:

| Scope | Status | Primary Artifacts |
|---|---|---|
| Task scope and acceptance freeze | Complete | `work_products/master_scope/MASTER_SCOPE_AND_ACCEPTANCE.md` |
| Existing product/material audit | Complete | `work_products/product_data_qa/`, `work_products/media_asset_probe/` |
| Product fact and market crawl method | Complete sample-gated plan | `work_products/product_market_master/` |
| Amazon/marketplace identity-first method | Complete sample-gated plan | `sample_identity_candidate_v1.csv`, `marketplace_probe/` |
| Design research and references | Complete | `work_products/design_reference_mapping/` |
| Commerce decision layer | Complete | `work_products/commerce_decision_layer/` |
| Pure Labebe DTC website implementation | Complete prototype v2.1 | `labebe-gemini-demo/`, URL on port `8790` |
| Mobile/desktop website QA | Complete | `qa/labebe-commerce-v2/*.png`, `browser_qa_report.md` |
| Paperclip/Boss Gallery separation | Complete v0.1 | `paperclip_runtime_duel/outputs/boss_gallery_v0/index.html` |
| Boss Gallery Demo A-F plan and evidence framing | Complete | `work_products/presentation_strategy/boss_gallery_completion_plan.md` |
| DTC walkthrough video | Complete FFmpeg-rendered video | `paperclip_runtime_duel/outputs/labebe_site_walkthrough/` |
| Existing AI wow video retained | Complete | `paperclip_runtime_duel/outputs/labebe_wow/labebe_ai_application_wow.mp4` |
| Browser Harness P0 | Complete sprint-local implementation | `runtime_qa_templates/browser_harness_capture.mjs` |
| MiniMax skill audit | Complete | `skill_runtime_governance/minimax_skill_placement_audit.md` |
| Skill/MCP/runtime governance | Complete | `skill_runtime_governance/` |
| maint / paperclip / multica backlog absorption | Complete | `backlog_absorption.md`, `paperclip_multica_org_mapping.md`, `maint_update_plan.md` |

## 2. External Advisor Inputs

The plan integrates these advisor/user-review inputs:

- `qa/Labebe运营系统设计.md`
- `pro_packet/final_pro_confirmation_answer.md`
- `pro_requests/20260426_radical_design_brainstorm/pro_answer.md`
- `sdd.md`
- `my - 红队审核与建议.md`
- Paperclip wow review docs under `pro_requests/20260425_paperclip_labebe_demo_config_review/`

Applied decisions:

- Pro-style external review is useful as a consultant, but no longer blocks local execution.
- The consumer website must be pure DTC and must not contain Paperclip or AI demo surfaces.
- Paperclip/Boss Gallery should show business outcomes and Claim Gate separately.
- Marketplace crawling must be identity-first; no broad Amazon claims before ASIN/entity match.
- Multica/GStack are pattern sources, not active sprint platforms.

## 3. Product Fact And Market Layer

### Current Truth

Existing local DTC scrape base:

- `data/labebe/labebe_products.csv`
- `data/labebe/labebe_products_with_images.csv`
- `data/labebe/all_product_images.json`
- `data/labebe/images/`

QA and normalized drafts:

- `work_products/product_data_qa/product_master_v0_draft.csv`
- `dirty_title_parse_report_draft.csv`
- `slug_image_join_report_draft.csv`

New masterplan outputs:

- `work_products/product_market_master/PRODUCT_FACT_AND_MARKET_CRAWL_MASTERPLAN.md`
- `field_mapping_v1.md`
- `product_master_v1_sample.csv`
- `sample_identity_candidate_v1.csv`
- `crawl_run_ledger.md`

### Decision

Do not claim Amazon sales/rank/reviews at portfolio level yet. The correct gate is:

```text
DTC product master -> identity sample -> accepted/probable ASINs -> marketplace reviews/sales proxy crawl -> claim gate
```

### Acceptance

Every SKU must eventually answer:

- What is the product and source URL?
- What is the current visible price and observation date?
- Which image/video assets belong to it?
- Which claims are allowed, blocked, or unknown?
- Does it have accepted marketplace identity?

## 4. DTC Website Implementation

Implementation path:

```text
labebe-gemini-demo/
```

Major implemented changes:

- room-first hero product theater;
- Shop by Room / Shop by Age / Gifts / Play Worlds / Storage navigation;
- guided finder by age, room, occasion;
- room planner;
- collection pages;
- PDPs with price, review count when supported, age/room/gift badges, tabs, modules, bundles;
- real local cart state and cart drawer;
- add-to-cart from PDP;
- quantity/update/remove/subtotal;
- mobile and desktop responsive QA.

Important files:

- `src/App.tsx`
- `src/context/CartContext.tsx`
- `src/context/cartContextValue.ts`
- `src/context/useCart.ts`
- `src/components/CartDrawer.tsx`
- `src/components/Navigation.tsx`
- `src/routes/Home.tsx`
- `src/routes/ProductPage.tsx`
- `src/routes/CollectionPage.tsx`
- `src/data/products.ts`
- `src/data/collections.ts`
- `src/index.css`

Live URLs:

- DTC site, current external URL: `https://yogas2.tail594315.ts.net:10000/`
- PDP: `https://yogas2.tail594315.ts.net:10000/product/pink-unicorn-plush-rocker`
- Collection: `https://yogas2.tail594315.ts.net:10000/collections/playroom-reset`
- Legacy raw DDNS path: `http://fnos.dandanbaba.xyz:8790/` may fail through router/DDNS/proxy; use the Tailscale Funnel URL for external review.

Server:

```bash
python3 planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/spa_static_server.py \
  --directory /vol1/1000/projects/toyresearch/labebe-gemini-demo/dist \
  --host 0.0.0.0 \
  --port 8790
```

Current running PID observed earlier:

```text
3920603
```

## 5. DTC QA

Build command:

```bash
cd labebe-gemini-demo && npm run build
```

Result: passed.

Browser Harness screenshots and metrics:

| Surface | Screenshot | Result |
|---|---|---|
| Home desktop | `qa/labebe-commerce-v2/home-desktop-cdp-v3.png` | no horizontal overflow |
| Home mobile | `qa/labebe-commerce-v2/home-mobile-cdp-v3.png` | no horizontal overflow |
| PDP desktop | `qa/labebe-commerce-v2/pdp-desktop-cdp-v2.png` | no horizontal overflow |
| Collection mobile | `qa/labebe-commerce-v2/collection-mobile-cdp-v1.png` | no horizontal overflow |
| Cart drawer mobile | `qa/labebe-commerce-v2/cart-drawer-mobile-cdp-v2.png` | no horizontal overflow, add-to-cart verified |

QA docs:

- `work_products/dtc_prototype_v2/browser_qa_report.md`
- `work_products/dtc_prototype_v2/design_decision_record.md`
- `work_products/dtc_prototype_v2/route_map.md`

Known limit:

- Checkout is a prototype CTA, not a payment/shipping backend.
- PDP material/dimension/care/safety details need source capture before production claims.

## 6. Paperclip / Boss Gallery

Output:

- `paperclip_runtime_duel/outputs/boss_gallery_v0/index.html`

Live URLs:

- `http://fnos.dandanbaba.xyz:8778/boss_gallery_v0/index.html`
- `http://100.124.54.52:8778/boss_gallery_v0/index.html`

Implemented:

- internal-only surface separate from DTC;
- result-first hero with existing AI wow video;
- Demo A-F cards;
- evidence IDs and gate states for each demo;
- detail contracts for VOC-to-concept and one-SKU-to-channel matrix;
- Claim Gate;
- evidence drawer;
- desktop/mobile QA.

QA:

- `qa/labebe-commerce-v2/boss-gallery-desktop-cdp-v3.png`
- `qa/labebe-commerce-v2/boss-gallery-mobile-cdp-v2.png`
- both reported no horizontal overflow.

Known limit:

- Static internal gallery, not a live Paperclip control plane.
- AI assets are prototype exploration until claim/media/brand review.

## 7. Videos And Presentation

### DTC walkthrough

Rendered without MiniMax quota:

- `paperclip_runtime_duel/outputs/labebe_site_walkthrough/labebe_dtc_site_walkthrough.mp4`
- poster: `labebe_dtc_site_walkthrough_poster.jpg`
- contact sheet: `labebe_dtc_site_walkthrough_contact_sheet.jpg`

Verified:

- H.264, 1920x1080, duration about 23.97s.
- HTTP 200 at `http://fnos.dandanbaba.xyz:8778/labebe_site_walkthrough/labebe_dtc_site_walkthrough.mp4`

### Existing AI wow video

- `paperclip_runtime_duel/outputs/labebe_wow/labebe_ai_application_wow.mp4`
- `http://fnos.dandanbaba.xyz:8778/labebe_wow/labebe_ai_application_wow.mp4`

Presentation docs:

- `work_products/presentation_strategy/site_walkthrough_video_plan.md`
- `boss_gallery_completion_plan.md`
- `visual_qa_acceptance.md`
- `evidence_manifest.json`

## 8. Browser Harness P0

Implemented locally:

- `runtime_qa_templates/capture_cdp_screenshot.mjs`
- `runtime_qa_templates/browser_harness_capture.mjs`
- `runtime_qa_templates/spa_static_server.py`

Current capability:

- static SPA server with route fallback;
- CDP desktop/mobile screenshot;
- horizontal overflow metrics;
- visible text and button/link inventory;
- bounded JS click-flow before screenshot;
- no uncontrolled VLM clicking.

Planning docs:

- `runtime_qa_templates/browser_harness_p0_contract.md`
- `skill_runtime_governance/browser_harness_p0_implementation_plan.md`
- `skill_runtime_governance/mcp_cli_skill_decision_matrix.md`

## 9. Skill / MCP / Runtime Governance

Outputs:

- `work_products/skill_runtime_governance/backlog_absorption.md`
- `paperclip_multica_org_mapping.md`
- `maint_update_plan.md`
- `skill_governance_design.md`
- `mcp_cli_skill_decision_matrix.md`
- `minimax_skill_placement_audit.md`
- `browser_harness_p0_implementation_plan.md`
- `evidence_manifest.json`
- `handoff.md`

Decisions:

- MiniMax multimodal skill already exists at:
  `/vol1/1000/home-yuanhaizhou/.codex-shared/skills/minimax-skills/skills/minimax-multimodal-toolkit/SKILL.md`
- Do not create duplicate MiniMax skill.
- Do not mutate maint/global skill homes unless a specific runtime cannot see it.
- GStack is method/checklist source only.
- Multica is read-only archive/pattern library.
- Browser Harness is evidence layer only.

## 10. Final Acceptance

This package is ready for user裁决 because it contains:

- clear two-surface architecture: DTC and Boss Gallery separated;
- working DTC website prototype with product routes and cart drawer;
- working Boss Gallery internal surface;
- product fact/market crawl masterplan with sample tables and gate ledger;
- video output for DTC walkthrough and existing AI wow video;
- Browser Harness P0 scripts and QA screenshots;
- skill/runtime governance docs with MiniMax placement audit;
- master evidence manifests and handoffs.

It is not claiming:

- production ecommerce checkout;
- full Amazon sales/review/rank crawl;
- verified safety/certification/material claims beyond current source;
- legal clearance for all media;
- live Paperclip control-plane integration;
- production-ready AI-generated product concepts.

Those are explicitly gated next steps.

## 11. Next Execution Queue

If the user approves this direction, the next real build sprint should be:

1. Run sample parser repair and marketplace identity browser sample.
2. Expand DTC product master to all 46 SKUs with `v1` field confidence.
3. Replace remaining catalog-only imagery with rights-cleared lifestyle/video assets.
4. Add console/accessibility capture to Browser Harness.
5. Generate narrated DTC and Boss Gallery videos with MiniMax only after quota and voice plan are accepted.
6. Connect Boss Gallery demo cards to real Paperclip issue/evidence IDs if Paperclip becomes active control plane.
