# Labebe Masterplan Execution Pack

Generated: 2026-04-27
Owner: Codex main controller

## One-Line Outcome

The project is now split correctly:

- **Labebe consumer website**: a pure DTC replacement site focused on product,
  room, age, gift and purchase decisions.
- **Paperclip / AI Boss Gallery**: a separate internal demo surface showing AI
  application outcomes, channel assets and Claim Gate controls.

This fixes the major previous mistake: mixing AI workflow into the public
consumer site.

## Current Working URLs

| Surface | URL | Purpose |
| --- | --- | --- |
| Labebe DTC Prototype v2 | `http://100.124.54.52:8790/` | Pure consumer website replacement prototype. |
| DTC PDP sample | `http://100.124.54.52:8790/product/pink-unicorn-plush-rocker` | Product detail page behavior and mobile order. |
| DTC Collection sample | `http://100.124.54.52:8790/collections/playroom-reset` | Collection page structure. |
| Boss Gallery v0 | `http://100.124.54.52:8778/boss_gallery_v0/index.html` | Internal AI/Paperclip result demo. |

If the DTC URL is down, restart:

```bash
cd /vol1/1000/projects/toyresearch/labebe-gemini-demo
npm run build
setsid python3 /vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/spa_static_server.py \
  --directory /vol1/1000/projects/toyresearch/labebe-gemini-demo/dist \
  --host 0.0.0.0 \
  --port 8790 \
  > /vol1/1000/projects/toyresearch/logs/labebe-commerce-v2-spa-8790.log 2>&1 < /dev/null &
```

## What Was Completed

| Workstream | Status | Key Output |
| --- | --- | --- |
| Pro-confirmed master plan | Complete | `01_MASTER_IMPLEMENTATION_PLAN.md` |
| Product data QA | Review-ready | 46-product master from local DTC scrape, unsafe fields identified. |
| Public media probe | Review-ready | 460 catalog JPGs, 9 videos, usage caveats. |
| Design reference mapping | Review-ready | Reference patterns mapped to business problems, generic patterns rejected. |
| Commerce Decision Layer | Review-ready | SKU roles, shopper missions, claim permissions, navigation/PDP strategy. |
| Marketplace identity sample | Review-ready | ASIN identity-first candidate matrix; no unsupported Amazon claims accepted. |
| DTC Prototype v2 | Review-ready | Rebuilt React/Vite Labebe site with desktop/mobile QA. |
| Boss Gallery v0 | Review-ready | Separate internal AI/Paperclip gallery with Demo A-F and Claim Gate. |
| Browser QA tooling | Review-ready | CDP screenshot tool with real mobile metrics and overflow checks. |

## Current Strategic Conclusions

1. Labebe should not be designed as a generic toy grid.
2. The strongest DTC architecture is room/age/gift/play-mission first.
3. Product truth must come before visual polish: price and visible review counts
   are usable; ratings, certifications, Amazon performance, materials, age
   guarantees and customer quotes remain blocked unless sourced.
4. The website and AI demo are two different products:
   - website = sell better;
   - Boss Gallery = prove AI can create business assets with controls.
5. Amazon work should stay identity-first. A broad crawl before ASIN matching is
   likely to create false evidence.

## Key Files

| File | Why It Matters |
| --- | --- |
| `work_products/commerce_decision_layer/sample_selection_rationale.md` | Why the first 8 SKUs were selected. |
| `work_products/commerce_decision_layer/claim_permission_matrix.csv` | What can and cannot be said. |
| `work_products/dtc_prototype_v2/design_decision_record.md` | Why the site was redesigned this way. |
| `work_products/dtc_prototype_v2/browser_qa_report.md` | Build, route and screenshot QA evidence. |
| `work_products/boss_gallery_v0/design_record.md` | Why AI demo lives outside the consumer site. |
| `work_products/marketplace_identity_sample/amazon_identity_sample.md` | Marketplace crawl constraints and next method. |

## QA Evidence

| Surface | Screenshot |
| --- | --- |
| DTC Home desktop | `qa/labebe-commerce-v2/home-desktop-cdp-v2.png` |
| DTC Home mobile | `qa/labebe-commerce-v2/home-mobile-cdp-v2.png` |
| DTC PDP desktop | `qa/labebe-commerce-v2/pdp-desktop-cdp.png` |
| DTC PDP mobile | `qa/labebe-commerce-v2/pdp-mobile-cdp-v2.png` |
| DTC Collection desktop | `qa/labebe-commerce-v2/collection-desktop-cdp.png` |
| Boss Gallery desktop | `qa/labebe-commerce-v2/boss-gallery-desktop-cdp-v2.png` |
| Boss Gallery mobile | `qa/labebe-commerce-v2/boss-gallery-mobile-cdp.png` |

All CDP-tested pages reported `horizontalOverflow: false`.

## What Is Still Not Done

2026-04-28 update: several items from the first closeout have moved to done for
prototype scope. The current remaining work is narrower:

- production checkout/backend remains out of scope; the cart now has prototype
  add/update/remove/subtotal and checkout-review handoff behavior;
- PDP source capture is done for 8 sample SKUs, but the extracted claim queue
  still needs human approval before public copy use;
- controlled Amazon ASIN identity has a validated sample lane and 7
  identity-whitelist candidates, but no full marketplace crawl or public Amazon
  sales/rating/review proof is approved;
- rights-cleared lifestyle/video asset production remains a production/legal
  gate;
- DTC and Boss Gallery desktop/mobile walkthrough videos are now rendered and
  served;
- shared Browser Harness implementation remains a reusable QA/vision service
  task, not a blocker for the current prototype package;
- Paperclip issue/evidence IDs are now connected to existing Paperclip issues
  for every Boss Gallery demo card; this is evidence binding only and does not
  approve publication.

## Recommended Next Narrow Sprint

1. Run authorized review/VOC extraction for the seven identity-whitelist Amazon
   rows once provider/login access exists.
2. Decide whether the next DTC pass is production hardening or award-level visual
   exploration.
4. Record the boss walkthrough video for the DTC site and the Boss Gallery.
5. Implement Browser Harness P0 as QA support only, not a new decision engine.
