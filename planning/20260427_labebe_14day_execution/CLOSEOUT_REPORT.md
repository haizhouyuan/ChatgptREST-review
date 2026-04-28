# Closeout Report

Created: 2026-04-28

## Scope Closed

This closeout covers the integrated Labebe/Paperclip execution package:

- Pure Labebe DTC replacement website prototype.
- Browser-verified desktop/mobile QA evidence.
- Product fact and marketplace crawl masterplan with identity-first sample method.
- Worker-ready 60-SKU marketplace enrichment backlog with explicit claim gates.
- Design research, commerce decision layer, and reference mapping.
- Internal Paperclip Boss Gallery v0.
- Existing AI application wow demo preserved as a separate executive demo asset.
- DTC walkthrough video for mobile/desktop presentation.
- Browser Harness P0 executable smoke across DTC and Boss Gallery representative
  routes.
- Skill/MCP/runtime governance plan, MiniMax skill placement audit, and Browser Harness P0 contract.
- Full masterplan, Pro/Gemini synthesis, worker outputs, evidence manifests, and handoff docs.

## Open URLs

| Item | URL |
|---|---|
| Pure DTC website, Tailscale Funnel | `https://yogas2.tail594315.ts.net:10000/` |
| First Steps collection, Tailscale Funnel | `https://yogas2.tail594315.ts.net:10000/collections/first-steps-activity` |
| Pink Unicorn PDP, Tailscale Funnel | `https://yogas2.tail594315.ts.net:10000/product/pink-unicorn-plush-rocker` |
| Playroom collection, Tailscale Funnel | `https://yogas2.tail594315.ts.net:10000/collections/playroom-reset` |
| Legacy DDNS DTC path | `http://fnos.dandanbaba.xyz:8790/` may fail through router/DDNS/proxy; use the Tailscale Funnel URL above for external review |
| Internal Boss Gallery | `http://fnos.dandanbaba.xyz:8778/boss_gallery_v0/index.html` |
| DTC walkthrough video | `http://fnos.dandanbaba.xyz:8778/labebe_site_walkthrough/labebe_dtc_site_walkthrough.mp4` |
| DTC mobile walkthrough video | `http://fnos.dandanbaba.xyz:8778/labebe_site_walkthrough/labebe_dtc_site_walkthrough_mobile.mp4` |
| Boss Gallery walkthrough video | `http://fnos.dandanbaba.xyz:8778/boss_gallery_v0/labebe_boss_gallery_walkthrough.mp4` |
| Boss Gallery mobile walkthrough video | `http://fnos.dandanbaba.xyz:8778/boss_gallery_v0/labebe_boss_gallery_walkthrough_mobile.mp4` |
| Existing AI wow video | `http://fnos.dandanbaba.xyz:8778/labebe_wow/labebe_ai_application_wow.mp4` |
| Browser Harness P0 smoke report | `/vol1/1000/projects/toyresearch/qa/browser-harness-p0-smoke-20260428/browser_harness_matrix_report.md` |
| Marketplace enrichment batch plan | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/marketplace_enrichment_batch_plan_v1.md` |
| Boss Gallery issue/evidence map | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/boss_gallery_v0/boss_gallery_issue_evidence_map.csv` |
| Boss Gallery claim ledger | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/boss_gallery_v0/boss_gallery_claim_ledger.csv` |
| Boss Gallery Paperclip binding report | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/boss_gallery_v0/boss_gallery_paperclip_binding_report.md` |

## Delivery Package

Package path:

`/vol1/1000/projects/toyresearch/planning/20260427_labebe_masterplan_full_delivery_20260428.zip`

Package size: about 41 MB.

SHA-256 is generated after packaging in the sidecar file:

`/vol1/1000/projects/toyresearch/planning/20260427_labebe_masterplan_full_delivery_20260428.zip.sha256`

Continuation package:

`/vol1/1000/projects/toyresearch/planning/20260428_labebe_product_marketplace_dtc_live_update.zip`

Continuation package size: about 85 MB after excluding local `node_modules` and
Vite `.git` metadata from the prototype folder.

Continuation package SHA-256 sidecar:

`/vol1/1000/projects/toyresearch/planning/20260428_labebe_product_marketplace_dtc_live_update.zip.sha256`

Read the `.sha256` sidecar for the current hash; do not hard-code the zip hash
inside package contents because rebuilding the package changes the digest.

The package is intended to include:

- `planning/20260427_labebe_14day_execution/`
- `qa/labebe-commerce-v2/`
- `paperclip_runtime_duel/outputs/boss_gallery_v0/`
- `paperclip_runtime_duel/outputs/labebe_site_walkthrough/`
- `paperclip_runtime_duel/outputs/labebe_wow/`
- Selected `labebe-gemini-demo/` source and build output: `package.json`, `package-lock.json`, `index.html`, `src/`, `public/assets/`, `dist/`

Excluded by design:

- `node_modules/`
- nested `.git/` metadata
- bulky scratch/runtime caches

## Verification Snapshot

| Check | Result |
|---|---|
| React/Vite DTC lint/build | Passed |
| DTC home HTTP | 200 |
| DTC PDP HTTP | 200 |
| First Steps collection HTTP | 200 |
| Boss Gallery HTTP | 200 |
| DTC walkthrough MP4 HTTP | 200 |
| Screenshot QA | desktop/mobile screenshots captured |
| Horizontal overflow checks | false on latest home, PDP, collection, cart drawer, Boss Gallery captures |
| DTC walkthrough video | H.264 1920x1080, about 66.97s |
| DTC mobile walkthrough video | H.264 1080x1920, about 39.97s |
| Boss Gallery walkthrough video | H.264 1920x1080, about 48.97s, HTTP 200 |
| Boss Gallery mobile walkthrough video | H.264 1080x1920, about 44.97s, HTTP 200 |
| Consumer site purity scan | Passed; no AI Growth / Paperclip / Boss / pro-context strings remain in DTC `src`, `public`, or `dist` |
| Current DTC asset audit | Passed; 26 product images have exact local source-chain files and the consumer bundle contains 0 videos |
| Marketplace enrichment backlog | 60 rows generated and assigned to guarded worker batches; JSON/CSV validation passed |
| Evidence manifests | JSON parse passed |
| Delivery package integrity | `unzip -t` passed |
| Continuation package integrity | `unzip -t` passed |
| Public URL recheck | listed website and video URLs returned HTTP 200 in latest spot checks |
| Browser Harness P0 smoke | 5/5 pass across DTC desktop/mobile, Pink Unicorn PDP desktop, Boss Gallery desktop/mobile |
| Boss Gallery Paperclip binding | 6 demo rows bound to existing Paperclip issues; LAB-9 has shared index and summary comment |

## 2026-04-28 Continuation

The continuation work added a live DTC catalog recrawl and a marketplace sample method test. The current live probe found 60 visible Labebe slugs versus the older 46-product local table. The DTC prototype now reflects that finding by adding `First Steps & Activity` as a fifth shopping world and five live push-walker SKUs.

Amazon product-detail Browser Harness probing succeeded for five ASIN samples. Pink Unicorn Plush Rocker -> `B072LXVM36`, Cream Wooden Play Kitchen -> `B0FH1KX7XQ`, Llama Plush Rocker -> `B07MFXJ28Y`, and Fox Plush Rocker -> `B0DSVJB5QH` are accepted as browser-verified marketplace samples with caveats. The `B087P9SXZQ` push-walker/doll-stroller listing is blocked from DTC reuse because the visual identity does not match the current DTC walker family. Amazon review crawling redirected to sign-in, so review/VOC extraction remains behind an authorized-pipeline gate.

The candidate lane was then expanded to 55 DTC SKUs. It captured 419 Amazon search-candidate rows and indexed 15 PDP probes. Ten PDP probes are usable fact samples; the rest are weak/incomplete and should be retried or replaced with a provider source. Search pages remain discovery-only and must not be used for public facts.

An expanded DTC-vs-Amazon visual gate was added after the PDP index. It compared 28 ASIN-to-SKU candidate rows and generated a contact sheet. The gate produced 1 probable same-product row, 10 title-promising rows needing human review, 5 additional human-review rows, 11 weak-PDP blocks, and 1 search-false-positive block. The key operational lesson is that automated image similarity is useful for triage, but Amazon scene images and variant clusters require human or stronger VLM review before SKU-to-ASIN promotion.

A first human visual review then converted the contact sheet into operating lanes: 7 identity-whitelist candidates, 4 variant-cluster candidates, 7 blocked negative examples, and 10 retry/provider rows. This is the current safest batch boundary for review/VOC crawling. A derived review/VOC seed table now includes only the seven identity-whitelist rows and keeps review extraction behind the authorized-pipeline gate.

Runtime readiness was checked for the authorized review path. `APIFY_TOKEN` / `APIFY_API_TOKEN` is not set in the current shell, so review/VOC extraction is prepared but not executed.

The authorized review/VOC path is now project-local and dry-run ready. The new
`amazon_authorized_review_voc_runner.py` produced a seven-row
identity-whitelist crawl plan with no external calls. The new
`build_review_voc_summary.py` was smoke-tested against the existing
`B087P9SXZQ` review sample as format validation only; that old sample remains
blocked as current DTC evidence because earlier contact-sheet review found an
identity conflict.

The 60-row product strategy matrix has also been converted into a marketplace
enrichment backlog. Every DTC SKU now has a next batch: identity-whitelist
review/VOC, variant-cluster mapping, PDP/provider retry, renewed no-identity
discovery, negative-example training, or regional-scope review. This is a
parallel work plan and gate table, not completed Amazon truth. Search facts stay
discovery-only, and real review extraction remains restricted to authorized
identity-whitelist rows.

The product intelligence layer now includes a 60-row product strategy matrix. It classifies each live DTC SKU into product worlds, website roles, Amazon identity lanes, marketplace signal tiers, claim-gate caveats, and next data actions. The derived DTC design brief makes the site direction product-led: Giftable Rockers are the strongest proof-rich hero category, Cream Wooden Play Kitchen is the current Pretend Play anchor, First Steps & Activity is a real DTC family but not yet marketplace-proof, and Montessori/Playroom categories should drive room-solution UX after PDP/spec recrawl.

An 8-SKU PDP source probe now captures official Labebe product-page text, screenshots, keyword contexts, and a 333-row manual claim-review queue. This moves dimensions, materials, safety, age, assembly, care, and shipping language from "unknown" into "source-captured but not yet approved for public copy." The extractor was corrected after the Learning Tower page exposed an `innerText` blind spot; the current method falls back to `textContent` when rendered text is visible but `innerText` is empty.

The DTC prototype now includes a homepage design switcher for three product-backed creative directions: `Gift Theater`, `Room Builder`, and `Play Worlds`. This is intentionally kept inside the consumer website prototype as a leadership comparison device, not as an AI/Paperclip demo. The latest screenshot QA captures Gift desktop/mobile, Room desktop, and Play desktop/mobile with `horizontalOverflow=false`. The first desktop pass was corrected after visual review because the editorial headline treatment collided with product cards; the current version uses a shorter Gift Theater headline and tighter hero typography.

The cart drawer now has an explicit checkout handoff state instead of a dead checkout button. The latest mobile QA adds Pink Unicorn to cart, opens the drawer, clicks `Review checkout`, and verifies the `Cart summary ready` state with `horizontalOverflow=false` and no internal demo wording.

The consumer site has also been cleaned back to a pure DTC replacement. Unused AI Growth, Boss Demo, Design Library, and Pro-context artifacts were removed from the Labebe app source/public/dist bundle. Nine live-probe catalog images were downloaded into `data/labebe/live_probe_images_20260428/` and used to replace same-name public images, so the current site asset chain is now explicit: 17 exact copies from `data/labebe/images`, 9 exact copies from the live-probe folder, 0 videos in the consumer bundle, and 0 assets blocked for origin verification. Production use still requires Labebe brand/legal approval for catalog-image reuse.

The production media/legal gate now has a handoff queue. All 26 active
consumer-site product images are listed in
`production_asset_clearance_queue_v1.csv` with source evidence and default
`pending_brand_legal_review` status. The queue does not approve any asset; it
gives brand/legal/ecommerce reviewers a concrete `approve_for_dtc`,
`internal_only`, or `replace_before_launch` decision field.

The internal Boss Gallery now also has desktop and mobile walkthrough videos rendered from section-level CDP captures. This gives a phone/desktop presentation artifact for the separate Paperclip / AI demo surface without embedding it into the consumer DTC site.

Browser Harness P0 is now executable as a local reusable QA layer. The matrix
runner captures screenshots plus `*.metrics.json` sidecars with route state,
visible text, CTA inventory, overflow, likely blank state, console/log entries
and network failure evidence. The first smoke matrix passed 5/5 across the DTC
site and Boss Gallery. This is not a strategic browser agent and does not manage
authenticated sessions.

Browser Harness now also has a thin localhost service wrapper for downstream
Paperclip / ChatGPTREST callers. It exposes `GET /health`, `GET /schema`, `POST
/capture`, and `POST /matrix`, delegates to the deterministic scripts, and can
require `BROWSER_HARNESS_TOKEN`. The service smoke passed against the DTC mobile
homepage with no overflow, no blank state, no console errors and no incomplete
images; the service matrix endpoint also passed a one-row DTC homepage desktop
matrix.

The Boss Gallery now has Paperclip issue/evidence binding. Demo A-F are mapped
to existing Paperclip issues `LAB-2`, `LAB-3`, `LAB-4`, `LAB-5`, `LAB-7`, and
`LAB-8`; each issue has a `boss_gallery_evidence` document. `LAB-9` has the
shared `boss_gallery_index` document plus a summary comment. The binding is
evidence/document binding only; it does not mark issues done or approve external
publication.

Final packaging after the Paperclip binding update passed `unzip -t`. The
current deliverable package is:

- `planning/20260428_labebe_product_marketplace_dtc_live_update.zip`
- SHA-256 sidecar:
  `planning/20260428_labebe_product_marketplace_dtc_live_update.zip.sha256`

Public runtime checks after packaging returned HTTP 200 for the DTC site, Boss
Gallery, evidence CSVs, Boss Gallery walkthrough video, and DTC desktop/mobile
walkthrough videos.

See:

- `CONTINUATION_UPDATE_20260428.md`
- `work_products/product_market_master/live_crawl_20260428/product_fact_execution_update_20260428.md`
- `work_products/product_market_master/marketplace_sample_execution_report.md`
- `work_products/product_market_master/marketplace_full_candidate_expansion_report.md`
- `work_products/product_market_master/live_crawl_20260428/amazon_dtc_visual_gate_v1.md`
- `work_products/product_market_master/live_crawl_20260428/amazon_dtc_visual_human_review_v1.md`
- `work_products/product_market_master/live_crawl_20260428/amazon_identity_lanes_v1.md`
- `work_products/product_market_master/live_crawl_20260428/amazon_review_voc_seed_v1.csv`
- `work_products/product_market_master/live_crawl_20260428/amazon_review_crawl_readiness_v1.md`
- `work_products/product_market_master/live_crawl_20260428/authorized_review_voc_execution_update_v1.md`
- `work_products/product_market_master/live_crawl_20260428/marketplace_enrichment_batch_plan_v1.md`
- `work_products/product_market_master/live_crawl_20260428/marketplace_enrichment_backlog_v1.csv`
- `work_products/product_market_master/live_crawl_20260428/marketplace_enrichment_worker_batches_v1.json`
- `work_products/product_market_master/live_crawl_20260428/labebe_product_strategy_matrix_v1.md`
- `work_products/product_market_master/live_crawl_20260428/labebe_product_strategy_matrix_v1.csv`
- `work_products/product_market_master/live_crawl_20260428/pdp_source_probe_v1/labebe_pdp_source_probe_report_v1.md`
- `work_products/product_market_master/live_crawl_20260428/pdp_source_probe_v1/labebe_pdp_source_claim_review_queue_v1.csv`
- `work_products/dtc_prototype_v2/live_catalog_design_update.md`
- `work_products/dtc_prototype_v2/product_matrix_to_dtc_design_brief_v1.md`
- `work_products/dtc_prototype_v2/design_switcher_update_20260428.md`
- `work_products/dtc_prototype_v2/consumer_site_purity_asset_update_20260428.md`
- `work_products/media_asset_probe/current_site_asset_usage_audit_v2.md`
- `work_products/media_asset_probe/production_asset_clearance_queue_v1.md`
- `work_products/presentation_strategy/boss_gallery_walkthrough_video_update_20260428.md`
- `work_products/runtime_qa_templates/browser_harness_run_matrix.mjs`
- `work_products/runtime_qa_templates/browser_harness_service.mjs`
- `qa/browser-harness-p0-smoke-20260428/browser_harness_matrix_report.md`
- `qa/browser-harness-service-smoke-20260428/browser_harness_service_smoke_report.md`
- `work_products/boss_gallery_v0/boss_gallery_issue_evidence_map.csv`
- `work_products/boss_gallery_v0/boss_gallery_claim_ledger.csv`
- `work_products/boss_gallery_v0/boss_gallery_paperclip_binding_report.md`

## Important Boundaries

The current package deliberately does not claim:

- full production checkout/backend readiness;
- complete Amazon/marketplace crawl coverage;
- proven Amazon sales estimates;
- verified media rights for external publication;
- unsupported certification, safety, origin, award, or market-demand claims;
- live Paperclip control-plane integration beyond demo output and execution plan.

The correct next execution posture is to use the current DTC prototype, product fact plan, and Boss Gallery as the baseline, then run the identity-first marketplace crawl and media-rights verification before making any stronger commercial claims.

## Runtime Notes

The DTC site is served from `labebe-gemini-demo/dist` on local port `8790`.
It is currently exposed publicly through Tailscale Funnel:

```bash
tailscale funnel --yes --bg --https=10000 8790
```

Public review URL:

```text
https://yogas2.tail594315.ts.net:10000/
```

The Paperclip output server is served from `paperclip_runtime_duel/outputs` on port `8778`.

If either endpoint goes down, restart with:

```bash
python3 /vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/spa_static_server.py --directory /vol1/1000/projects/toyresearch/labebe-gemini-demo/dist --host 0.0.0.0 --port 8790
python3 -m http.server 8778 --bind 0.0.0.0 --directory /vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs
```
