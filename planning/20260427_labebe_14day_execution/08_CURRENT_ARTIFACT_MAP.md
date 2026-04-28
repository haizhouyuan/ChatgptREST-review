# Current Artifact Map

Date: 2026-04-27
Status: Read-only inventory snapshot while waiting for final Pro confirmation

## 1. Data Sources Already Present

### Labebe DTC Crawl

Path:

```text
data/labebe/
```

Observed files:

- `labebe_products.csv`
- `labebe_products_with_images.csv`
- `all_product_images.json`
- `images/`

Observed counts:

- 460 local product image files in `data/labebe/images/`.
- `all_product_images.json` exists and is the likely image URL/source map.
- top repeated image groups include outdoor garden potting bench, midnight kitchen, art table, toy organizer, plush rockers, Montessori shelves and learning towers.

Risk:

- duplicate/near-duplicate product titles and image groups exist;
- file count does not by itself prove clean product identity;
- this must go through Product Master v0 and data QA before design use.

### Amazon / Marketplace Sample

Path:

```text
data/amazon_reviews_US_B087P9SXZQ.csv
fetch_amazon_reviews_apify.py
```

Risk:

- ASIN `B087P9SXZQ` must not be treated as mapped to a Labebe SKU until identity scoring is done;
- reviews must not become VOC before marketplace/language/source checks.

### Kimi Website Upload Pack

Path:

```text
kimi_web_upload_website_pack/
```

Observed:

- 27 files within depth 2;
- includes DOCX briefs, XLSX product/asset tables, product contact sheet, storyboard images, reference images and a MiniMax demo MP4.

Use:

- useful as historical brief/material source;
- not authoritative enough for final claims without source ledger.

### Design Reference Pack

Path:

```text
labebe_design_reference_pack/
```

Observed:

- 23 non-git files within depth 3;
- includes strategy, same-category references, world-class web references, page patterns, motion guidelines, DESIGN/AGENTS docs and Kimi redesign prompt.

Use:

- input for `reference_pattern_mapping.md`;
- must be converted from moodboard/reference notes into Labebe business-problem mappings.

### Design / DTC Research

Paths:

```text
research/20260425_website_design_dtc/
research/20260425_design_dtc_research_v2/
```

Use:

- source registry, framework, benchmark and Pro answer material;
- should be mined for design patterns and independent-site growth mechanics.

### Paperclip / Boss Gallery Baseline

Path:

```text
paperclip_runtime_duel/outputs/labebe_wow/
```

Observed:

- 16 files within depth 2;
- includes `index.html`, `boss_video.html`, `labebe_ai_application_wow.mp4`, contact sheet, screenshots and product image assets.

Use:

- valid baseline for Boss Gallery only;
- not a DTC website source.

### QA Screenshot History

Path:

```text
qa/
```

Observed top-level QA folders include:

- `labebe-pure-commerce-v1`
- `labebe-clean-redesign`
- `labebe-redesign-v3` through `v6`
- `labebe-v2` through `v7-pro-fixes`
- `radical-observatory-*`
- `product-theater-v11`
- `fnos*`
- `kimi_site`

Use:

- evidence of previous visual attempts and failure modes;
- input for rejected direction log and visual QA standards;
- not evidence of current plan quality.

## 2. Runtime / Agent Entrypoints

Observed commands:

- `claude`
- `claudeminmax`
- `kimi`
- `kimicode`
- `hcom`

Existing Paperclip runtime duel contains:

- `adapter-kimi-cli/index.mjs`
- `tools/run_lane.mjs`
- Kimi lane AGENTS file;
- Claude-Kimi lane AGENTS file;
- evidence JSON and rendered outputs.

Use:

- useful as execution precedent;
- do not reuse runtime duel as the visible Boss Gallery deliverable without scope review;
- future delegated tasks should use isolated write scopes under this execution directory.

## 3. Immediate Implication

There is enough local material to start `LAB-002` through `LAB-006` sample work after Pro confirmation, without waiting for more external research.

The main unknown is not whether material exists. The main unknown is whether the material can be converted into a trustworthy Commerce Decision Layer without contaminating design with dirty product identity, unsupported claims or weak Amazon mappings.

