# 2026-04-09 Project Context Harness And Anchor Governance Walkthrough v1

Date: 2026-04-09

## Why this package exists

The earlier authority-anchor work made `_project_context.md` parseable and visible at runtime, but it still had an obvious production-readiness gap:

- the live anchors could be parseable without being governed
- schema drift could remain silent until packet quality degraded
- there was no strict canary harness for anchor quality

This package closes PR-1 from the production-readiness roadmap.

## Landed changes

### 1. Authority-anchor lint and inspection

Updated:

- `chatgptrest/governance/authority_anchor.py`

New public inspection surface:

- `inspect_authority_anchor_path(...)`

It now checks:

- required frontmatter fields
- required body sections
- explicit `last_reviewed_at`
- authority-doc freshness and existence
- soft body-size guardrail

### 2. Project-context harness

Added:

- `ops/run_project_context_harness.py`

This is the strict operator entrypoint for canary anchors.

It supports:

- selecting explicit `project_id` targets
- strict nonzero exit on lint fail or missing project id
- archived JSON and Markdown evidence output

### 3. Canonical contract

Added:

- `docs/contracts/2026-04-09_project_authority_anchor_contract_v1.md`

This freezes:

- required fields
- required body sections
- freshness semantics
- soft body-size guardrail
- lint result levels

### 4. Live anchor cleanup

Updated the two current live planning anchors:

- `/vol1/1000/projects/planning/两轮车车身业务/_project_context.md`
- `/vol1/1000/projects/planning/行星滚柱丝杠/_project_context.md`

Both now have:

- explicit `project_id`
- explicit `owner`
- explicit `last_reviewed_at`

## Verification

Syntax:

```bash
python3 -m py_compile \
  chatgptrest/governance/authority_anchor.py \
  ops/run_project_context_harness.py \
  tests/test_authority_anchor.py \
  tests/test_run_project_context_harness.py
```

Focused tests:

```bash
./.venv/bin/pytest -q \
  tests/test_authority_anchor.py \
  tests/test_run_project_context_harness.py \
  tests/test_context_service_work_memory.py \
  tests/test_cognitive_api.py
```

Result:

- `18 passed`

## Real canary evidence

Strict harness run:

```bash
python3 ops/run_project_context_harness.py \
  --project-id shortmobility \
  --project-id prs \
  --output-dir artifacts/monitor/project_context_harness/20260409T050124Z \
  --strict
```

Artifacts:

- `artifacts/monitor/project_context_harness/20260409T050124Z/project_context_harness.json`
- `artifacts/monitor/project_context_harness/20260409T050124Z/project_context_harness.md`

Observed result:

- anchor count: `2`
- lint pass / warn / fail: `2 / 0 / 0`
- missing project ids: `0`
- stale anchors: `0`

Fresh governance scan after anchor cleanup:

- `artifacts/monitor/authority_governance_scan_20260409_pr1/authority_governance_scan.md`

Observed result:

- missing docs: `0`
- schema gaps: `0`
- stale anchors: `0`

## Why this matters

After this package:

- the authority anchor is no longer just parseable; it is lintable
- canary projects can be gated on anchor quality before packet quality is judged
- the prior `missing_owner` gap is no longer silent and is now closed on the two live anchors

## Residual risk

- the current canary set is still only `shortmobility` and `prs`
- user sign-off on the final production project roster is still a separate manual gate from the production roadmap
- anchor quality still depends on future human maintenance discipline even though the harness now makes drift visible
