# 2026-04-09 Project Authority Anchor Contract v1

## Purpose

This contract defines the minimum governed shape of a live project authority anchor stored as `_project_context.md`.

The goal is not to turn the file into a bloated cache.

The goal is to make sure the file is:

- machine-parseable
- fresh enough for packet compilation
- explicit enough to outrank lower-priority recall safely

## Canonical file location

- planning repo project anchor: `<project-dir>/_project_context.md`

## Required frontmatter fields

These fields must exist on every production-grade anchor:

- `project`
- `alias`
- `project_id`
- `planning_base`
- `owner`
- `last_reviewed_at`
- `authority_docs`
- `frozen_facts`
- `style_rules`

## Required body sections

These sections must exist in the markdown body:

- `## 当前权威文档`
- `## 当前阶段`
- one action section from:
  - `## 当前待推进动作`
  - `## 当前待执行修改`
  - `## 当前待办`
  - `## 下一步`

## Runtime precedence

The anchor remains the top substrate layer:

```text
authority anchor > project memory > EvoMap knowledge > runtime heuristics
```

This means:

- lower-priority memory, KB, or graph recall may supplement the anchor
- lower-priority recall may not silently override anchor facts
- crystallized learning remains advisory and lower priority than the anchor

## Freshness rule

- `last_reviewed_at` is the freshness field used by governance checks
- `updated` may still exist for editorial history, but it is not the canonical governance field
- stale detection defaults to the repo runtime threshold unless an operator intentionally overrides it in the harness

## Soft size guardrail

The anchor body is allowed to be human-readable, but it should not grow into a document dump.

Current soft warning threshold:

- `project_context` body > `6000` chars => warning, not hard failure

## Lint semantics

Lint result levels:

- `pass`: no errors, no warnings
- `warn`: no errors, but freshness or document-quality warnings exist
- `fail`: required field or required section is missing

Typical hard failures:

- missing `project_id`
- missing `owner`
- missing explicit `last_reviewed_at`
- missing `authority_docs`
- missing `frozen_facts`
- missing `style_rules`
- missing required body sections

Typical warnings:

- stale anchor
- missing authority docs on disk
- stale authority docs
- oversized body

## Operator entrypoint

The canonical operator harness is:

```bash
cd /vol1/1000/projects/ChatgptREST
python3 ops/run_project_context_harness.py \
  --project-id shortmobility \
  --project-id prs \
  --output-dir artifacts/monitor/project_context_harness/<stamp> \
  --strict
```

## Scope note

This contract governs the authority-anchor file shape only.

It does not by itself guarantee:

- packet quality
- recall quality
- promotion quality
- production rollout safety

Those are covered by later production-readiness phases.
