# Amazon DTC Visual Gate v1

## Boundary

This is a visual triage artifact. It does not independently approve a marketplace match for public copy. Use it to decide which ASINs deserve human review, retry, provider extraction, or claim gating.

## Counts

- Candidate visual rows: 28
- blocked_search_false_positive: 1
- blocked_weak_pdp_probe: 11
- visual_needs_human_review: 5
- visual_needs_human_review_title_promising: 10
- visual_probable_same_product: 1

## Files

- `amazon_dtc_visual_gate_v1.csv`
- `image_identity_expanded_v1/amazon_dtc_visual_gate_contact_sheet_v1.jpg`

## Key Decisions

This gate is intentionally conservative. DTC packshots and Amazon PDP images often differ because Amazon uses child-in-scene imagery, international storefront banners, or variant-cluster hero images. Low hash/color similarity therefore does not automatically mean "not the same product"; it means the pair needs human or stronger VLM review before promotion.

The current automatic result:

| Status | Meaning | Count |
|---|---:|---:|
| `visual_probable_same_product` | Strong automated image/title signal; still needs human approval before public use | 1 |
| `visual_needs_human_review_title_promising` | Title strongly matches but image similarity is weak or scene-dependent | 10 |
| `visual_needs_human_review` | PDP is usable, but image/title signal is not enough for automatic promotion | 5 |
| `blocked_weak_pdp_probe` | PDP evidence lacks social proof/seller fields or was incomplete | 11 |
| `blocked_search_false_positive` | Search result points to the wrong product family | 1 |

## Notable Rows

| SKU | ASIN | Gate | Note |
|---|---|---|---|
| `fox-plush-rocker` | `B0DSVJB5QH` | `visual_probable_same_product` | The automated hash/title signal is strongest in this batch. |
| `highlander-cattle-plush-rocker` | `B071774PWC` | `blocked_search_false_positive` | Search returned a Crocodile rocker. This is the clearest negative training example. |
| `pink-unicorn-plush-rocker` | `B072LXVM36` | `visual_needs_human_review_title_promising` | Contact sheet shows likely same product family, but Amazon image includes a child scene, so automated image similarity is lower. |
| `llama-plush-rocker` | `B07MFXJ28Y` | `visual_needs_human_review_title_promising` | Likely same product family by title and visual inspection; keep human approval attached. |
| `cream-wooden-play-kitchen-set-with-storage` | `B0FH1KX7XQ` | `visual_needs_human_review_title_promising` | Amazon image appears to be a close kitchen variant; variant gate required. |
| `B0D6YX3XG1` / `B0F8PZ7KZQ` push-walker cluster | multiple DTC push walkers | mixed review statuses | Amazon listings are variant clusters and cannot be collapsed into a single DTC SKU. |
| Learning tower cluster | `B0FMRDDRZK` | `blocked_weak_pdp_probe` | PDP evidence did not capture usable marketplace social proof in this run. |

## Method Lesson

Use this lane as a queue builder, not as final proof:

1. Search page creates an ASIN candidate.
2. PDP probe captures canonical title, seller, rating, review count, price, bullets, and screenshots.
3. Visual gate creates a DTC-vs-Amazon contact sheet and conservative machine status.
4. Human/VLM review promotes only confirmed SKU-to-ASIN pairs.
5. Claim gate decides which listing facts can be reused internally and which claims remain blocked.
6. Review/VOC crawling starts only after identity promotion and authorized review access.
