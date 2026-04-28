# Delegation And Parallelization Plan

Date: 2026-04-27
Status: Final v2 after Pro confirmation

## 1. Available Local Agent Entrypoints

Observed on this machine:

| Tool | Path / command | Intended use |
| --- | --- | --- |
| Claude Code | `/home/yuanhaizhou/.nvm/versions/node/v22.22.0/bin/claude` | Coding/research worker where Claude Code CLI is appropriate |
| Claude Code Runner skill | `claudecode-agent-runner` | Async Claude jobs with logs/status/result artifacts |
| Claude + MiniMax route | `/home/yuanhaizhou/.local/bin/claudeminmax` | Claude Code compatibility route backed by MiniMax, useful for implementation/review where configured |
| Kimi CLI | `kimi` | Native Kimi coding/research lane |
| Kimi Code | `/home/yuanhaizhou/.local/bin/kimicode` | Kimi coding lane |
| hcom | `/home/yuanhaizhou/.local/bin/hcom` | Multi-agent coordination if interactive/team orchestration is needed |
| Paperclip runtime duel | `paperclip_runtime_duel/tools/run_lane.mjs` | Existing Kimi / Claude-Kimi Paperclip lanes; currently better as reference unless we set new issues |

## 2. Delegation Timing

The final Pro confirmation has been read. Delegation is allowed only for bounded evidence/mapping tasks with isolated write scopes.

Allowed before Pro returns:

- prepare prompts;
- inspect tool entrypoints;
- define write scopes;
- create output directories;
- create evidence manifests.

Not allowed during this sprint unless main controller explicitly changes the plan:

- change DTC prototype implementation before `LAB-007`;
- start full crawls;
- mark sprint-level Paperclip issues done;
- ask Pro/Gemini again;
- let any worker edit outside assigned paths;
- let workers make final Commerce Decision Layer or prototype decisions.

## 3. Work Packages

### WP-A: Product Data QA

Preferred worker: Claude Code Kimi / Claude Code.

Purpose:

- inspect existing Labebe crawl outputs and scripts;
- produce a trustworthy path to `product_master_v0.csv`;
- identify dirty fields and join risks.

Write scope:

```text
planning/20260427_labebe_14day_execution/work_products/product_data_qa/
```

Inputs:

- `scrape_labebe.py`
- `data/labebe/`
- existing product CSV/JSON/images;
- `planning/20260427_labebe_product_intel_and_design/*`

Required outputs:

- `product_data_inventory.md`
- `product_master_v0_draft.csv`
- `current_data_qa_draft.md`
- `slug_image_join_report_draft.csv`
- `dirty_title_parse_report_draft.csv`
- `do_not_use_fields_draft.md`
- `handoff.md`
- `evidence_manifest.json`

Stop conditions:

- product files cannot be found;
- data schema is ambiguous enough that unique product identification is unsafe;
- worker would need to overwrite existing source data.

### WP-B: Marketplace / Amazon Method Probe

Preferred worker: main Codex first, Claude Code only after product sample is clear.

Purpose:

- compare feasible Amazon data methods;
- test ASIN identity workflow on a tiny sample;
- prevent VOC pollution.

Write scope:

```text
planning/20260427_labebe_14day_execution/work_products/marketplace_probe/
```

Inputs:

- `fetch_amazon_reviews_apify.py`
- `data/amazon_reviews_US_B087P9SXZQ.csv`
- selected sample SKUs from existing local notes where available.

Required outputs:

- `tool_method_comparison_amazon.md`
- `source_access_matrix_amazon.csv`
- `asin_identity_workflow.md`
- `asin_candidates_sample_draft.csv`
- `amazon_source_limitations_draft.md`
- `method_failures.md`
- `handoff.md`
- `evidence_manifest.json`

Stop conditions:

- no safe no-key/manual sample path exists;
- ASIN identity cannot be scored;
- worker starts scraping reviews before identity confidence.

### WP-C: Public Media Asset Probe

Preferred worker: Kimi Code.

Purpose:

- discover public brand image/video/ad asset paths;
- draft safe media manifest and scene index;
- avoid unsupported asset-use claims.

Write scope:

```text
planning/20260427_labebe_14day_execution/work_products/media_asset_probe/
```

Inputs:

- local downloaded product images;
- brand website crawl output;
- existing `kimi_web_upload_website_pack/`;
- existing `paperclip_runtime_duel/outputs/labebe_wow/`.

Required outputs:

- `initial_media_probe.md`
- `brand_video_assets_draft.csv`
- `downloaded_media_manifest_draft.csv`
- `video_scene_index_draft.csv`
- `asset_rights_and_usage_notes_draft.md`
- `handoff.md`
- `evidence_manifest.json`

Stop conditions:

- asset source URL is unclear;
- asset usage caveat cannot be stated;
- worker attempts to treat public capture as legal clearance.

### WP-D: Design Reference Mapping

Preferred worker: Kimi Code.

Purpose:

- convert existing reference pack into business-problem patterns;
- avoid generic moodboard thinking.

Write scope:

```text
planning/20260427_labebe_14day_execution/work_products/design_reference_mapping/
```

Inputs:

- `labebe_design_reference_pack/`
- `research/20260425_website_design_dtc/`
- `research/20260425_design_dtc_research_v2/`
- prior Pro feedback files.

Required outputs:

- `reference_pattern_mapping_draft.md`
- `commerce_pattern_library_draft.md`
- `rejected_generic_patterns.md`
- `handoff.md`
- `evidence_manifest.json`

Stop conditions:

- output is only a list of pretty sites;
- pattern does not map to a Labebe shopper mission, category role, PDP module or conversion problem.

### WP-E: Runtime Evidence / Browser QA Template

Preferred worker: local Codex.

Purpose:

- define Browser Harness P0 as QA/evidence support only;
- prevent platform sprawl.

Write scope:

```text
planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/
```

Inputs:

- GStack intake research;
- ChatGPTREST Browser Harness analysis;
- existing QA screenshot directories;
- `planning/20260427_paperclip_gstack_derived_gate_templates.md`.

Required outputs:

- `browser_harness_p0_contract.md`
- `browser_qa_report_template.md`
- `design_review_report_template.md`
- `visual_ai_slop_checklist.md`
- `evidence_manifest_template.json`
- `handoff.md`

Stop conditions:

- worker proposes autonomous browser agent as primary actor;
- QA template lacks visual critique;
- template only checks HTTP 200 / screenshot existence.

## 4. Integration Rules

- Main controller assigns exact write scope.
- Worker must not edit source-of-truth master plan unless explicitly asked.
- Worker must not call ChatGPTREST / Pro / Gemini.
- Worker must not start long external crawls without a method probe artifact.
- Worker must include known limitations.
- Worker handoff must name what the main controller should trust, what to inspect, and what not to use yet.

## 5. Quality Gate For Worker Results

A delegated result is accepted only when:

- required outputs exist;
- evidence manifest maps outputs to source files or commands;
- no forbidden scope was touched;
- limitations are explicit;
- result can be merged into `Labebe Commerce Decision Layer` or runtime kernel without extra interpretation.

## 6. Execution After Pro

After the Pro confirmation:

1. Revise `01_MASTER_IMPLEMENTATION_PLAN.md` into v2. Done.
2. Update this delegation plan. Done.
3. Launch only WP-A, WP-C and WP-D first because their write scopes are disjoint and evidence-oriented.
4. Main controller continues `PCL-001`, `LAB-001`, WP-B review preparation and integration docs while workers run.
5. Do not start prototype or Boss Gallery implementation until worker outputs are reviewed and `LAB-007` exists.
