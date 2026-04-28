# WP-D Design Reference Mapping Worker Prompt

You are a delegated worker in `/vol1/1000/projects/toyresearch`.

You are not alone in the codebase. Do not revert or modify files outside your assigned write scope.

Assigned write scope:

```text
/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/design_reference_mapping/
```

Task:

Convert existing design reference research into business-problem patterns for Labebe. This is not a moodboard task. Each pattern must map to shopper mission, category role, PDP module, conversion mechanism, asset need or rejection condition.

Read first:

- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/01_MASTER_IMPLEMENTATION_PLAN.md`
- `/vol1/1000/projects/toyresearch/labebe_design_reference_pack/`
- `/vol1/1000/projects/toyresearch/research/20260425_website_design_dtc/`
- `/vol1/1000/projects/toyresearch/research/20260425_design_dtc_research_v2/`

Required outputs:

- `reference_pattern_mapping_draft.md`
- `commerce_pattern_library_draft.md`
- `rejected_generic_patterns.md`
- `handoff.md`
- `evidence_manifest.json`

Acceptance:

- every reference pattern states what Labebe business problem it solves;
- include what not to copy;
- include how the pattern could affect homepage, nav, collection, PDP or bundle flow;
- include rejection conditions for generic/templated design.

Forbidden:

- do not call Pro/Gemini;
- do not list pretty sites without mapping;
- do not design final UI;
- do not edit prototype code.

