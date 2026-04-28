# WP-A Product Data QA Worker Prompt

You are a delegated worker in `/vol1/1000/projects/toyresearch`.

You are not alone in the codebase. Do not revert or modify files outside your assigned write scope.

Assigned write scope:

```text
/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/product_data_qa/
```

Task:

Inspect existing Labebe independent-site crawl data and scripts. Produce a draft Product Master v0 and data QA artifacts. Do not run full external crawls. Do not invent product fields. Unknowns must be explicit.

Read first:

- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/01_MASTER_IMPLEMENTATION_PLAN.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/04_DELEGATION_AND_PARALLELIZATION_PLAN.md`
- `/vol1/1000/projects/toyresearch/scrape_labebe.py`
- `/vol1/1000/projects/toyresearch/data/labebe/`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_product_intel_and_design/`

Required outputs:

- `product_data_inventory.md`
- `product_master_v0_draft.csv`
- `current_data_qa_draft.md`
- `slug_image_join_report_draft.csv`
- `dirty_title_parse_report_draft.csv`
- `do_not_use_fields_draft.md`
- `handoff.md`
- `evidence_manifest.json`

Acceptance:

- identify all known product source files;
- explain whether 46 products can be uniquely identified;
- detect title/slug/image/PDP join risks;
- list fields unsafe for copy or claims;
- record commands used.

Forbidden:

- do not call Pro/Gemini;
- do not overwrite source data;
- do not silently repair data without reporting;
- do not mark final sprint issue done.

