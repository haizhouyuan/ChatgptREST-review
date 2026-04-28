# Marketplace Full Candidate Expansion Report

Date: 2026-04-28

## Scope

After the sample method was validated, the Amazon search-candidate lane was expanded from a small sample to 55 non-regional / non-EU Labebe DTC SKUs.

This expansion is still a candidate and evidence-building lane. It is not a final Amazon marketplace truth layer, because SKU-to-ASIN promotion still requires PDP, image, variation and claim gates.

## Full Search Candidate Run

Output:

- `live_crawl_20260428/amazon_search_candidates_full_v1.csv`
- `live_crawl_20260428/amazon_search_candidates_full_v1.json`
- `qa/marketplace_probe/amazon_search_candidates_full_v1/`

Result:

- 55 SKUs searched.
- 419 candidate rows captured.
- 0 captcha-like search pages observed in the run.
- 38 unique top ASINs.
- 8 top results are high-confidence PDP queue candidates.
- 18 top results are variant-cluster PDP queue candidates.
- 29 top results appear to be competitor/generic category results and must not be treated as Labebe facts.

Important method lesson:

Search pages are only discovery. They can return regional prices, competitor products, and wrong SKU matches. Search-page price, rating and review count are not fact fields.

## Candidate Summary

Output:

- `live_crawl_20260428/amazon_search_candidate_summary_v1.csv`
- `live_crawl_20260428/amazon_search_candidate_duplicate_asins_v1.csv`
- `live_crawl_20260428/amazon_search_candidate_summary_v1.md`

The summary intentionally chooses the rank-1 search result per SKU before scoring. Earlier scoring-first logic caused a false match, such as Llama being pulled toward Mammoth because of token overlap. Rank-first plus gate-first is the safer method.

## PDP Probe Expansion

Output:

- `live_crawl_20260428/amazon_pdp_probe_facts_v1.csv`
- `live_crawl_20260428/amazon_pdp_probe_sku_candidates_v1.csv`
- `live_crawl_20260428/amazon_pdp_probe_index_v1.md`

Result:

- 15 ASIN PDP JSON files indexed.
- 28 ASIN-to-SKU candidate rows joined from the candidate summary.
- 10 PDP captures are usable fact samples.
- 4 PDP captures are weak because they lack marketplace social proof or seller fields.
- 1 PDP capture is blank/incomplete and must be retried or replaced with a provider source.

Usable PDP fact samples now include:

| ASIN | Candidate Product Family | Probe Result |
|---|---|---|
| `B072LXVM36` | Pink Unicorn Plush Rocker | usable PDP sample |
| `B07MFXJ28Y` | Llama Plush Rocker | usable PDP sample |
| `B071774PWC` | Crocodile Plush Rocker | usable PDP sample, but Highlander search also falsely hit it |
| `B0BVR63LRR` | White Swan Plush Rocker | usable PDP sample |
| `B0D6YX3XG1` | Baby Push Walker variant cluster | usable PDP sample, variant gate required |
| `B0F8PZ7KZQ` | Baby Push Walker / Doll Stroller variant cluster | usable PDP sample, variant gate required |
| `B0DSVJB5QH` | Fox Plush Rocker | usable PDP sample |
| `B0FH1KX7XQ` | Cream / Kitchen variant cluster | usable PDP sample, variant gate required |
| `B0FSQ48N93` | Blue Squirrel Plush Rocker | usable PDP sample |
| `B087P9SXZQ` | Doll Stroller / Push Walker candidate | usable PDP sample, but DTC visual conflict remains |

Weak PDP samples:

- `B07Z3DXVQT` Mammoth / Yak cluster: no rating/review captured in PDP probe.
- `B0DJ6XM7GK` Sheep Rocker: no rating/review captured in PDP probe.
- `B0FLD8TWWN` Princess Vanity: no rating/review captured in PDP probe.
- `B0FMRDDRZK` Learning Tower cluster: no rating/review captured in PDP probe.
- `B0DSZXRZZ1` Wooden Rocking Horse: blank/incomplete capture.

## DTC-vs-Amazon Visual Gate

Output:

- `live_crawl_20260428/amazon_dtc_visual_gate_v1.csv`
- `live_crawl_20260428/amazon_dtc_visual_gate_v1.md`
- `live_crawl_20260428/image_identity_expanded_v1/amazon_dtc_visual_gate_contact_sheet_v1.jpg`
- `live_crawl_20260428/amazon_dtc_visual_human_review_v1.csv`
- `live_crawl_20260428/amazon_dtc_visual_human_review_v1.md`

Result:

- 28 ASIN-to-SKU candidate rows were compared with DTC primary images and Amazon PDP main images.
- 1 row reached `visual_probable_same_product`.
- 10 rows reached `visual_needs_human_review_title_promising`.
- 5 rows reached `visual_needs_human_review`.
- 11 rows were blocked because the PDP probe was weak or incomplete.
- 1 row was blocked as a search false positive.

Important method lesson:

The automated visual score is deliberately conservative. Amazon PDP images often use child-in-scene photography, international storefront banners, or variant-cluster product images, while the DTC site often uses packshots. That means low hash/color similarity should not automatically reject a pair; it should place the pair into a human or stronger VLM review queue. Search false positives, however, must remain blocked.

Notable gate outcomes:

| SKU | ASIN | Status | Implication |
|---|---|---|---|
| `fox-plush-rocker` | `B0DSVJB5QH` | `visual_probable_same_product` | Strongest automatic visual/title match in this run. |
| `highlander-cattle-plush-rocker` | `B071774PWC` | `blocked_search_false_positive` | Search returned Crocodile, not Highlander. Keep as negative training evidence. |
| `pink-unicorn-plush-rocker` | `B072LXVM36` | `visual_needs_human_review_title_promising` | Likely same product family by contact sheet, but still needs human approval before public reuse. |
| `llama-plush-rocker` | `B07MFXJ28Y` | `visual_needs_human_review_title_promising` | Likely same product family by title and contact sheet. |
| `cream-wooden-play-kitchen-set-with-storage` | `B0FH1KX7XQ` | `visual_needs_human_review_title_promising` | Close kitchen variant; keep variant gate attached. |
| Learning tower SKUs | `B0FMRDDRZK` | `blocked_weak_pdp_probe` | Retry or provider data needed before marketplace claims. |

## Human Visual Review

The contact sheet was reviewed manually after the machine gate.

Result:

- 7 rows are human-confirmed same-product candidates and can move into the identity whitelist stage.
- 4 rows are useful variant-cluster candidates but not exact SKU proof.
- 7 rows are blocked as wrong product or wrong variant negative training examples.
- 10 rows require PDP retry or provider extraction before promotion.

The review was then converted into execution lanes:

- `live_crawl_20260428/amazon_identity_lanes_v1.csv`
- `live_crawl_20260428/amazon_identity_lanes_v1.md`
- `live_crawl_20260428/amazon_review_voc_seed_v1.csv`

The current review/VOC seed contains only the seven identity-whitelist candidates. Review crawling remains limited to an authorized pipeline.

Runtime readiness check:

- `APIFY_TOKEN` / `APIFY_API_TOKEN` is not set in the current shell.
- Direct browser review-page crawl previously redirected to Amazon sign-in.
- Therefore review/VOC extraction is prepared but not executed.
- Readiness note: `live_crawl_20260428/amazon_review_crawl_readiness_v1.md`

Identity-whitelist candidates from this pass:

- `crocodile-plush-rocker` -> `B071774PWC`
- `pink-unicorn-plush-rocker` -> `B072LXVM36`
- `llama-plush-rocker` -> `B07MFXJ28Y`
- `white-swan-plush-rocker` -> `B0BVR63LRR`
- `fox-plush-rocker` -> `B0DSVJB5QH`
- `cream-wooden-play-kitchen-set-with-storage` -> `B0FH1KX7XQ`
- `blue-squirrel-plush-rocker` -> `B0FSQ48N93`

## Product / Website Implication

The product matrix is now materialized:

- `live_crawl_20260428/labebe_product_strategy_matrix_v1.csv`
- `live_crawl_20260428/labebe_product_strategy_matrix_v1.md`

The current product-world split:

- First Steps & Activity: 17
- Giftable Rockers: 13
- Montessori Home & Study: 13
- Pretend Play Worlds: 10
- Playroom Reset: 7

The product strategy matrix confirms:

- Plush Rockers have the strongest Amazon signal density and should remain a key hero/gift world.
- Play Kitchen has a verified Amazon sample, but multiple DTC kitchen SKUs point to one ASIN and require image/variant gate.
- Push Walkers are a real DTC family, but Amazon mapping is variant-clustered and cannot be collapsed into one SKU.
- Learning Tower has DTC strategic value, but the Amazon PDP evidence is weak in this run and needs retry/provider support before using marketplace claims.
- Storage/furniture and easel products are more likely to return competitor/generic search results, so they need image search or provider APIs before marketplace conclusions.

## Next Scaling Rule

Do not run broad Amazon review/VOC crawling yet.

The safe next batch is:

1. Run human/VLM review over `amazon_dtc_visual_gate_contact_sheet_v1.jpg`.
2. Promote only visually confirmed SKU-to-ASIN pairs.
3. Keep variant clusters separate from single-SKU matches.
4. Run claim gates for newly promoted pairs.
5. Run review extraction only for promoted ASINs through an authorized review pipeline.
6. Keep search-candidate false positives as negative training examples for the future skill.
