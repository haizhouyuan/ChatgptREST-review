# Labebe PDP Source Probe v1

Observed at: `2026-04-27T20:08:07.139355+00:00`

## Summary

This run captures official Labebe PDP text for the 8-SKU decision sample. It is a source-capture layer only; it does not approve public copy claims.

| SKU | Text chars | Keyword hit groups | Source status | Screenshot |
|---|---:|---|---|---|
| `pink-unicorn-plush-rocker` | 8513 | dimensions, materials, safety, age, assembly, care, shipping | captured_official_pdp_text | `/vol1/1000/projects/toyresearch/qa/labebe_pdp_source_probe_v1/pink-unicorn-plush-rocker.png` |
| `cream-wooden-play-kitchen-set-with-storage` | 6612 | dimensions, materials, safety, age, assembly, care, shipping | captured_official_pdp_text | `/vol1/1000/projects/toyresearch/qa/labebe_pdp_source_probe_v1/cream-wooden-play-kitchen-set-with-storage.png` |
| `foldable-learning-tower-montessori-kitchen-tower-log-color` | 4354 | dimensions, materials, safety, age, assembly, care, shipping | captured_official_pdp_text | `/vol1/1000/projects/toyresearch/qa/labebe_pdp_source_probe_v1/foldable-learning-tower-montessori-kitchen-tower-log-color.png` |
| `children-s-writing-desk-and-chair-set-with-hutch---cork-board-for-study---art` | 3719 | dimensions, materials, safety, age, assembly, care, shipping | captured_official_pdp_text | `/vol1/1000/projects/toyresearch/qa/labebe_pdp_source_probe_v1/children-s-writing-desk-and-chair-set-with-hutch---cork-board-for-study---art.png` |
| `kids-toy-storage-organizer-bookshelf-with-bins` | 6241 | dimensions, materials, safety, age, assembly, care, shipping | captured_official_pdp_text | `/vol1/1000/projects/toyresearch/qa/labebe_pdp_source_probe_v1/kids-toy-storage-organizer-bookshelf-with-bins.png` |
| `natural-wood-montessori-shelf-with-storage-boxes` | 6024 | dimensions, materials, safety, age, assembly, care, shipping | captured_official_pdp_text | `/vol1/1000/projects/toyresearch/qa/labebe_pdp_source_probe_v1/natural-wood-montessori-shelf-with-storage-boxes.png` |
| `wooden-mud-kitchen-outdoor-play-kitchen-with-planter-box-sink` | 5104 | dimensions, materials, safety, age, assembly, care, shipping | captured_official_pdp_text | `/vol1/1000/projects/toyresearch/qa/labebe_pdp_source_probe_v1/wooden-mud-kitchen-outdoor-play-kitchen-with-planter-box-sink.png` |
| `activity-cube-baby-push-walker` | 4464 | dimensions, materials, safety, age, assembly, care, shipping | captured_official_pdp_text | `/vol1/1000/projects/toyresearch/qa/labebe_pdp_source_probe_v1/activity-cube-baby-push-walker.png` |

## Claim Gate Guidance

- Treat keyword hits as review leads, not claim approvals.
- Only promote exact, product-specific statements after a human reads the raw PDP text.
- If a field is not present in the raw PDP text, keep the prototype wording generic or hide the field.
- Safety, certification, material, weight capacity, and age claims need exact source text and manual approval.

## Outputs

- CSV: `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/pdp_source_probe_v1/labebe_pdp_source_probe_v1.csv`
- Context JSONL: `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/pdp_source_probe_v1/labebe_pdp_source_contexts_v1.jsonl`
- Claim review queue: `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/pdp_source_probe_v1/labebe_pdp_source_claim_review_queue_v1.csv`
- Raw text folder: `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/pdp_source_probe_v1/raw_text`
- Screenshots: `/vol1/1000/projects/toyresearch/qa/labebe_pdp_source_probe_v1`
