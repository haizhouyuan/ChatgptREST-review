# WP-B Marketplace / Amazon Method Probe Worker Prompt

You are a delegated worker in `/vol1/1000/projects/toyresearch`.

You are not alone in the codebase. Do not revert or modify files outside your assigned write scope.

Assigned write scope:

```text
/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/marketplace_probe/
```

Task:

Compare feasible Amazon / marketplace data methods and draft an ASIN identity workflow. Use only tiny samples. Do not perform full review crawling. No Amazon VOC may be used unless ASIN identity confidence is established.

Read first:

- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/01_MASTER_IMPLEMENTATION_PLAN.md`
- `/vol1/1000/projects/toyresearch/fetch_amazon_reviews_apify.py`
- `/vol1/1000/projects/toyresearch/data/amazon_reviews_US_B087P9SXZQ.csv`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_product_intel_and_design/`

Required outputs:

- `tool_method_comparison_amazon.md`
- `source_access_matrix_amazon.csv`
- `asin_identity_workflow.md`
- `asin_candidates_sample_draft.csv`
- `amazon_source_limitations_draft.md`
- `method_failures.md`
- `handoff.md`
- `evidence_manifest.json`

Acceptance:

- distinguish no-key, manual, existing-script, API/key-required paths;
- propose ASIN identity scoring fields and statuses;
- use `B087P9SXZQ` only as a sample to verify mapping, not as assumed truth;
- record limits and failures.

Forbidden:

- do not call Pro/Gemini;
- do not claim sales ranking or demand unless source supports it;
- do not treat reviews as VOC before ASIN confidence;
- do not start full crawl.

