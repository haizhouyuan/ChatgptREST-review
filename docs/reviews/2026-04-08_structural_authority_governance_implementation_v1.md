# Structural Authority Governance Implementation V1

Date: 2026-04-08

Implements:

- Work Package 3 from [Refined Next-Stage Full Execution Plan V2](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v2.md)

## Scope

This change turns authority precedence from a prompt convention into a structural runtime contract.

It does four things:

1. adds a first-class authority-anchor parser and governance model
2. injects authority into runtime context assembly as a dedicated source
3. exposes stale/missing/conflict visibility in `/v2/context/resolve`
4. adds a rerunnable authority-governance scan for operator use and later release gates

## Code surface

- [authority_anchor.py](/vol1/1000/projects/ChatgptREST/chatgptrest/governance/authority_anchor.py)
- [context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py)
- [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
- [prompt_builder.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/prompt_builder.py)
- [run_authority_governance_scan.py](/vol1/1000/projects/ChatgptREST/ops/run_authority_governance_scan.py)

## Runtime contract changes

### 1. First-class authority source

`ContextAssembler` now understands `authority` as a real source with:

- highest source priority
- dedicated protected budget (`authority_anchor`)
- protected trimming behavior
- explicit `## Authority Anchor` rendering

### 2. Project-scoped authority injection

`ContextResolver` now auto-loads an authority anchor when `project_id` is present.

Authority is no longer dependent on:

- string-only `available_inputs`
- prompt-order accidents
- lower-layer recall ordering

### 3. Governance metadata

`/v2/context/resolve` metadata now exposes:

- `authority_governance.present`
- `authority_governance.anchor_path`
- `authority_governance.owner`
- `authority_governance.last_reviewed_at`
- `authority_governance.stale_status`
- `authority_governance.missing_docs`
- `authority_governance.schema_gaps`
- `authority_governance.current_phase_framing`
- `authority_governance.pinned_authority_inputs`
- `authority_governance.conflicts`

Conflict preview is intentionally heuristic. It is operator visibility, not automatic truth rewriting.

### 4. Prompt-builder hardening

`prompt_builder` now explicitly renders dictionary-shaped authority inputs instead of only recognizing a string convention.

This preserves the priority contract when the upstream layer passes structured `available_inputs`.

## Governance scan

New operator script:

```bash
python3 ops/run_authority_governance_scan.py \
  --output-dir artifacts/monitor/authority_governance_scan_<tag>
```

Outputs:

- `authority_governance_scan.json`
- `authority_governance_scan.md`

Current live evidence from this implementation step:

- [authority_governance_scan.md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/authority_governance_scan_20260408_dline/authority_governance_scan.md)

## Acceptance coverage

Added coverage for:

1. authority precedence before active context and lower layers
2. conflict preview surfacing
3. stale + missing-doc degraded status
4. authority survival under token pressure
5. API metadata projection
6. prompt-builder rendering of dict authority inputs

## Acceptance result

Verified with:

```bash
python3 -m py_compile \
  chatgptrest/governance/authority_anchor.py \
  chatgptrest/kernel/context_assembler.py \
  chatgptrest/cognitive/context_service.py \
  chatgptrest/advisor/prompt_builder.py \
  ops/run_authority_governance_scan.py \
  tests/test_context_service_work_memory.py \
  tests/test_prompt_builder.py \
  tests/test_cognitive_api.py

./.venv/bin/pytest -q \
  tests/test_context_service_work_memory.py \
  tests/test_prompt_builder.py \
  tests/test_cognitive_api.py
```

Gate result for Work Package 3:

- authority source is structural, not advisory only
- authority precedence is visible in prompt previews
- stale/missing/schema-partial status is detectable
- replay/fixture tests prove authority survives conflict and trimming pressure

## Remaining gap intentionally left for later package

This change does not yet convert authority governance into the single release gate pack. That is handled in the next work package.
