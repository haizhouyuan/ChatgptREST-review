# 2026-04-09 Wake-Up Packet Quality Evaluation And Batch Harness Walkthrough v1

Date: 2026-04-09

## Why this package exists

The earlier wake-up packet work proved that packet compilation existed and could ride the `/v3/agent/turn` hot path.

That was not yet enough for production readiness.

The missing pieces were:

- packet quality was still mostly judged by reading one artifact manually
- truncation and omission were implicit rather than explicit
- there was no deterministic comparison surface for repeated canary runs
- the roadmap thresholds were not encoded into an operator harness

This package closes PR-2 from the production-readiness roadmap.

## Landed changes

### 1. Packet quality receipt

Updated:

- `chatgptrest/cognitive/wakeup_packet.py`

The packet now carries `quality_receipt` with:

- layer order
- coverage ratio
- truncation and omission receipts
- provenance counts
- token budget ratio
- `comparison_digest`

This does not change packet precedence or prompt meaning.

It only makes quality and clipping behavior observable.

### 2. Harness output upgraded

Updated:

- `ops/run_wakeup_packet_harness.py`

The single-packet harness now renders packet markdown with the quality receipt visible.

### 3. Batch packet-quality harness

Added:

- `ops/run_wakeup_packet_batch_harness.py`

This is the canonical PR-2 evaluator.

It:

- compiles a canary case set
- scores packets against the packet-quality rubric
- archives `batch_summary.json`
- archives `batch_summary.md`
- emits `packet_review_sample.md` for bounded secondary review

### 4. Canonical docs

Added or updated:

- `docs/contracts/2026-04-09_wakeup_packet_contract_v1.md`
- `docs/contracts/2026-04-09_wakeup_packet_quality_contract_v1.md`
- `docs/runbook.md`

## Verification

Syntax:

```bash
python3 -m py_compile \
  chatgptrest/cognitive/wakeup_packet.py \
  ops/run_wakeup_packet_harness.py \
  ops/run_wakeup_packet_batch_harness.py \
  tests/test_wakeup_packet.py \
  tests/test_run_wakeup_packet_harness.py \
  tests/test_run_wakeup_packet_batch_harness.py
```

Focused suite:

```bash
./.venv/bin/pytest -q \
  tests/test_wakeup_packet.py \
  tests/test_run_wakeup_packet_harness.py \
  tests/test_run_wakeup_packet_batch_harness.py \
  tests/test_task_intake.py \
  tests/test_prompt_builder.py \
  tests/test_routes_agent_v3.py
```

Observed result:

- focused suite passed

## Real canary evidence

Single packet:

```bash
./.venv/bin/python ops/run_wakeup_packet_harness.py \
  --query "请概括当前行星滚柱丝杠项目的权威事实、待推进动作和下一步。" \
  --project-id prs \
  --trace-id trace-pr2-packet-prs \
  --output-root artifacts/monitor/wakeup_packet_harness
```

Artifacts:

- `artifacts/monitor/wakeup_packet_harness/20260409T051657Z/wakeup_packet.json`
- `artifacts/monitor/wakeup_packet_harness/20260409T051657Z/wakeup_packet.md`

Observed receipt:

- raw `degraded=true`
- `degraded_sources`:
  - `personal_graph_empty`
  - `memory_identity_missing`
  - `captured_memory_identity_missing`
  - `work_memory_identity_partial`
- `layer_ids`: `L0/L1/L2/L3`
- `quality_receipt.truncation_count=2`
- `quality_receipt.omission_count=1`
- `quality_receipt.comparison_digest=a6e4cb487824fc17`

Batch packet-quality canary:

```bash
./.venv/bin/python ops/run_wakeup_packet_batch_harness.py \
  --output-root artifacts/monitor/wakeup_packet_batch_harness \
  --strict
```

Artifacts:

- `artifacts/monitor/wakeup_packet_batch_harness/20260409T051846Z/batch_summary.json`
- `artifacts/monitor/wakeup_packet_batch_harness/20260409T051846Z/batch_summary.md`
- `artifacts/monitor/wakeup_packet_batch_harness/20260409T051846Z/packet_review_sample.md`

Observed result:

- success rate: `1.0`
- raw degraded ratio: `1.0`
- adjusted degraded ratio: `0.0`
- median auto usefulness score: `4.6`

This means:

- the packet compiler is healthy for the current canary cohort
- the remaining raw degraded signal is currently explained by declared external gaps, not by packet-compiler regression

## Threshold interpretation

The production-readiness roadmap explicitly allowed degraded-ratio judgment after excluding declared external gaps.

The batch harness now encodes that rule directly.

It still archives raw degraded ratio because hiding it would be dishonest.

## Residual risk

- `shortmobility` still has thin L2 retrieval compared with `prs`; this is a PR-3 problem, not a PR-2 compiler failure
- the packet-quality harness is only as representative as the canary case set
- no user override was supplied for packet threshold or cohort, so PR-2 currently uses the roadmap defaults and the existing canary projects `shortmobility` and `prs`
