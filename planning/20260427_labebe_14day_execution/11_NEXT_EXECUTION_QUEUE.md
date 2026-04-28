# Next Execution Queue

Date: 2026-04-28
Status: Updated after continuation execution wave

## Completed In This Execution Wave

### 1. Promote Product Master

Input:

- `work_products/product_data_qa/product_master_v0_draft.csv`
- `work_products/product_data_qa/current_data_qa_draft.md`
- `work_products/product_data_qa/do_not_use_fields_draft.md`

Output:

- `work_products/commerce_decision_layer/inputs/product_master_v0.csv`
- `work_products/commerce_decision_layer/inputs/current_data_qa.md`
- `work_products/commerce_decision_layer/inputs/do_not_use_fields.md`

Controller decision:

- use `product_url` as primary key;
- keep `slug` as display/navigation key;
- record one slug normalization exception.

Status: complete.

### 2. Select 6-8 Sample SKUs

Default sample set:

1. Pink Unicorn Plush Rocker.
2. Cream Wooden Play Kitchen Set with Storage.
3. Foldable Learning Tower Montessori Kitchen Tower Log Color.
4. Children / Kids Desk near-duplicate cluster sample.
5. Kids Toy Storage Organizer Bookshelf with Bins.
6. Natural Wood Montessori Shelf with Storage Boxes.
7. Wooden Mud Kitchen Outdoor Play Kitchen.
8. ASIN `B087P9SXZQ` mapping check target, only if identity can be linked to a candidate SKU; otherwise mark as no-match sample.

Output:

- `sample_selection_rationale.md`

Status: complete. The final 8-SKU sample is documented in
`work_products/commerce_decision_layer/sample_selection_rationale.md`.

### 3. Commerce Decision Layer Inputs

Inputs:

- WP-A product master/data QA.
- WP-C media manifest.
- WP-D pattern mapping.
- Marketplace method prep.

Outputs:

- `category_portfolio_map.md`
- `shopper_mission_map.md`
- `hero_candidate_matrix.csv`
- `sku_role_matrix.csv`
- `asset_readiness_matrix.csv`
- `claim_permission_matrix.csv`
- `reference_pattern_mapping.md`
- `rejected_direction_log.md`

Status: complete. See `work_products/commerce_decision_layer/`.

### 4. DTC Prototype v2

Status: review-ready.

Outputs:

- `labebe-gemini-demo/`
- `work_products/dtc_prototype_v2/`
- `qa/labebe-commerce-v2/home-desktop-cdp-v2.png`
- `qa/labebe-commerce-v2/home-mobile-cdp-v2.png`
- `qa/labebe-commerce-v2/pdp-desktop-cdp.png`
- `qa/labebe-commerce-v2/pdp-mobile-cdp-v2.png`
- `qa/labebe-commerce-v2/collection-desktop-cdp.png`

### 5. Boss Gallery v0

Status: review-ready.

Output:

- `paperclip_runtime_duel/outputs/boss_gallery_v0/index.html`
- `work_products/boss_gallery_v0/`

### 6. Executive Decision Pack

Status: review-ready.

Output:

- `work_products/executive_pack/EXECUTIVE_DECISION_PACK.md`

## Completed After The First Queue

These items were listed as remaining in the 2026-04-27 queue and have now moved
to done or to an explicit hard gate.

| Item | Current status | Evidence |
|---|---|---|
| Cart drawer and checkout behavior | Done for prototype scope. Cart supports add/update/remove/subtotal and a non-dead `Review checkout` handoff state. No payment/tax/shipping simulation is claimed. | `labebe-gemini-demo/src/components/CartDrawer.tsx`; `qa/labebe-commerce-v2/cart-*`; `CONTINUATION_UPDATE_20260428.md` |
| PDP source capture | Done for the 8-SKU source sample. Raw PDP text, screenshots, keyword contexts and a 333-row manual claim-review queue were generated. | `work_products/product_market_master/live_crawl_20260428/pdp_source_probe_v1/` |
| Controlled Amazon canonical ASIN pass | Done for a sample/triage boundary, not a full crawl. Expanded search found 419 rows; 15 PDP probes were indexed; human visual review yielded 7 identity-whitelist candidate rows. | `amazon_identity_lanes_v1.md`; `amazon_dtc_visual_human_review_v1.md`; `amazon_review_voc_seed_v1.csv` |
| Rights-cleared lifestyle/video asset production | Split. Consumer site now has explicit product-image source chain for every referenced product image; production legal/brand clearance remains outside automation scope. No videos are bundled in the consumer site. | `current_site_asset_usage_audit_v2.md`; `consumer_site_purity_asset_update_20260428.md` |
| Production asset clearance queue | Done as a handoff queue, not as approval. All 26 active consumer-site product images are listed with source evidence and default `pending_brand_legal_review` status; production-approved count remains 0 until brand/legal/ecommerce reviewers decide. | `production_asset_clearance_queue_v1.md`; `production_asset_clearance_queue_v1.csv` |
| 60-90 second DTC walkthrough | Done. Desktop and mobile walkthroughs were rendered and served. | `paperclip_runtime_duel/outputs/labebe_site_walkthrough/` |
| Boss Gallery walkthrough recording | Done. Desktop and mobile walkthroughs were rendered and served. | `paperclip_runtime_duel/outputs/boss_gallery_v0/labebe_boss_gallery_walkthrough*.mp4` |
| Browser Harness P0 as QA support | Done as local repeatable QA scripts/checks for this sprint, not as a shared production service. | QA JSON/screenshots; `render_dtc_walkthrough.mjs`; `render_boss_gallery_walkthrough.mjs`; `visual_qa_acceptance.md` |
| Shared Browser Harness P0 | Done as a thin reusable local harness. It captures screenshots, `*.metrics.json`, visible text/CTA inventory, overflow, blank state, console/log entries and matrix reports. | `work_products/runtime_qa_templates/browser_harness_capture.mjs`; `browser_harness_run_matrix.mjs`; `qa/browser-harness-p0-smoke-20260428/` |
| Paperclip issue/evidence binding for Boss Gallery | Done. The six Boss Gallery demo rows are bound to existing Paperclip issues LAB-2, LAB-3, LAB-4, LAB-5, LAB-7 and LAB-8; LAB-9 has the shared `boss_gallery_index` document and a summary comment. | `work_products/boss_gallery_v0/boss_gallery_issue_evidence_map.csv`; `boss_gallery_paperclip_binding_report.md`; Paperclip documents `boss_gallery_evidence` / `boss_gallery_index` |
| Browser Harness service wrapper | Done as a localhost P0 service wrapper. It exposes `GET /health`, `GET /schema`, `POST /capture`, and `POST /matrix`, reusing the deterministic capture/matrix scripts and optional `BROWSER_HARNESS_TOKEN`. Service smoke passed for health/schema/capture/matrix; DTC mobile capture had no overflow, no blank state, no console errors, and no incomplete images; one-row desktop matrix passed 1/1. | `work_products/runtime_qa_templates/browser_harness_service.mjs`; `qa/browser-harness-service-smoke-20260428/browser_harness_service_smoke_report.md` |
| Marketplace enrichment backlog | Done as a worker-ready batch plan. All 60 DTC SKU rows are assigned to explicit enrichment batches: 7 identity-whitelist review/VOC rows, 4 variant-cluster rows, 10 PDP/provider retry rows, 27 no-identity discovery rows, 7 negative-training rows, and 5 regional-scope rows. | `marketplace_enrichment_backlog_v1.csv`; `marketplace_enrichment_batch_plan_v1.md`; `marketplace_enrichment_worker_batches_v1.json` |

## Remaining Next Queue

These are the only remaining items that should continue after this package.
They are intentionally narrow and should not reopen the design direction unless
new evidence contradicts the current product matrix.

| Priority | Item | Why it remains | Next action |
|---|---|---|---|
| P0 Gate | Authorized Amazon review/VOC extraction | Direct browser review pages redirect to sign-in and the current shell has no `APIFY_TOKEN` / `APIFY_API_TOKEN`. The project-local runner, dry-run plan, and VOC summarizer smoke now exist. | Use `amazon_authorized_review_voc_runner.py --execute` only after credentials are available; then run `build_review_voc_summary.py` on the resulting review CSVs. |
| P0 Gate | Production media/legal approval | Local prototype image source chain and clearance queue are explicit, but production reuse requires Labebe brand/legal approval. | Review `production_asset_clearance_queue_v1.csv` and mark each asset `approve_for_dtc`, `internal_only`, or `replace_before_launch`. |
| P1 | Full marketplace enrichment execution | Current Amazon work now has a full 60-row worker backlog, but not all batches have been executed to final marketplace truth. | Execute `marketplace_enrichment_worker_batches_v1.json` batch by batch. Keep search facts discovery-only and run review extraction only for identity-whitelist rows after credentials are available. |
| P2 | Production commerce backend | Prototype cart handoff is intentionally not a real checkout. | Only scope if the user asks to move from demo prototype to production commerce build. |

## Do Not Reopen Without New Evidence

- Do not put Paperclip, Boss Gallery, AI Growth Studio, or Pro-context material
  back into the consumer DTC website.
- Do not treat the 7 identity-whitelist Amazon rows as public sales/rating proof.
- Do not add fake ratings, fake reviews, fake certifications, fake production CAD,
  fake safety approvals, or fake market-demand claims.
- Do not start new Pro/Gemini review loops. Use completed external advice and
  local evidence unless a new concrete contradiction appears.

## Delegation Guidance

No more Pro/Gemini tasks.

Allowed next delegation:

- one Kimi/Claude worker for authorized review/VOC extraction after credentials
  are present;
- one Kimi/Claude worker for full marketplace identity expansion after the
  7-row seed path is verified;
- one Kimi/Claude worker for shared Browser Harness P0 implementation.

Main controller keeps:

- sample SKU and claim-gate final decisions;
- Commerce Decision Layer integration;
- all consumer DTC direction decisions;
- final approval that internal AI/Paperclip assets remain separated from the
  consumer site.
