# WP-E Runtime Evidence / Browser QA Template Worker Prompt

You are a delegated worker in `/vol1/1000/projects/toyresearch`.

You are not alone in the codebase. Do not revert or modify files outside your assigned write scope.

Assigned write scope:

```text
/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/
```

Task:

Define a Browser Harness P0 contract as QA/evidence support only. Do not propose a new platform or autonomous browser brain. The output should help agents judge whether DTC/Boss Gallery pages are displayable, mobile-safe, visually credible, and evidence-backed.

Read first:

- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/01_MASTER_IMPLEMENTATION_PLAN.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_paperclip_gstack_derived_gate_templates.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_chatgptrest_parallel_review_incident_retrospective.md`
- `/vol1/1000/projects/toyresearch/qa/`

Required outputs:

- `browser_harness_p0_contract.md`
- `browser_qa_report_template.md`
- `design_review_report_template.md`
- `visual_ai_slop_checklist.md`
- `evidence_manifest_template.json`
- `handoff.md`

Acceptance:

- template checks desktop/mobile/tablet, console, links, core route flow, text overflow, visual hierarchy and AI-template feel;
- includes screenshot and red-circle defect evidence requirements;
- explicitly says vision model is judge/locator, not action authority;
- keeps Browser Harness below platform scope.

Forbidden:

- do not call Pro/Gemini;
- do not build a new browser platform;
- do not change ChatGPTREST code;
- do not start browser automation against live ChatGPT.

