# 2026-04-09 Wake-Up Packet Quality Contract v1

## Purpose

This contract defines how packet quality is evaluated for production-readiness gating.

It sits above the packet shape contract.

The packet shape contract answers:

- what fields exist
- how precedence works

This contract answers:

- how to measure whether a packet is good enough for canary use
- which degraded signals are real regressions vs declared external gaps
- what evidence must be archived at PR-2 closeout

## Canonical evaluator

Operator entrypoint:

```bash
cd /vol1/1000/projects/ChatgptREST

./.venv/bin/python ops/run_wakeup_packet_batch_harness.py \
  --output-root artifacts/monitor/wakeup_packet_batch_harness \
  --strict
```

Single-packet debug entrypoint:

```bash
cd /vol1/1000/projects/ChatgptREST

./.venv/bin/python ops/run_wakeup_packet_harness.py \
  --query "请概括当前行星滚柱丝杠项目的权威事实、待推进动作和下一步。" \
  --project-id prs \
  --trace-id trace-pr2-packet-prs
```

## Default canary cohort

Until the user explicitly overrides it, the canary packet cohort is:

- `shortmobility`
- `prs`

Default query set:

- two recurring prompts for `shortmobility`
- two recurring prompts for `prs`

The batch harness owns the canonical case list.

## Rubric dimensions

Automatic rubric dimensions:

- `l0_authority_accuracy`
- `l1_open_loop_usefulness`
- `l2_retrieval_relevance`
- `l3_next_step_usefulness`
- `provenance_complete`
- `project_match`
- `adjusted_degraded`

The batch harness converts these into `auto_usefulness_score` on a `1.0-5.0` scale.

This score is a canary gate, not a product claim of perfect packet quality.

## Declared external gaps

The following degraded sources are currently treated as declared external gaps for PR-2 gating:

- `personal_graph_empty`
- `memory_identity_missing`
- `captured_memory_identity_missing`
- `work_memory_identity_partial`

They remain visible in raw packet receipts.

They are excluded only from the PR-2 degraded-ratio threshold because they do not indicate packet compiler regression by themselves.

## Default thresholds

Until explicitly overridden, the canonical thresholds are:

- success rate `>= 0.95`
- adjusted degraded ratio `<= 0.20`
- median auto usefulness score `>= 4.0`

Raw degraded ratio is still archived and must not be hidden.

It is simply not the same metric as adjusted degraded ratio.

## Archived evidence

PR-2 closeout evidence must include:

- single-packet artifact for a real canary project
- batch harness summary JSON
- batch harness summary Markdown
- packet review sample Markdown
- focused regression suite output

## Manual review

The batch harness emits `packet_review_sample.md` for bounded secondary review.

Manual review is still useful for:

- false-positive packet scores
- wrong-project bleed that heuristics missed
- packet prose that is technically complete but operator-unhelpful

## Non-goals

This contract does not claim:

- that recall quality is solved
- that promotion quality is solved
- that raw degraded signals should be zero
- that packets are byte-identical across runs
