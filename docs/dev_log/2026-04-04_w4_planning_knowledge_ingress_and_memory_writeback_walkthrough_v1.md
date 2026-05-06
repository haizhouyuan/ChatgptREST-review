# W4 Walkthrough v1

## Why

`W4` was blocked by a split brain:

- planning checkpoint/handoff already had `stable_facts / pending_actions / memory_writeback_candidates`
- work memory already had `active_project / decision_ledger / handoff / post_call_triage`
- but `agent_v3` planning turns did not actually ingest those stable facts into the canonical prompt path
- and completed planning turns did not emit a governed writeback receipt

## What I changed

1. Added a planning knowledge-ingress helper in `routes_agent_v3.py`
   - reads active work memory for the current planning identity
   - reads planning runtime-pack hits plus bundle freshness/readiness
   - appends concise notes into `task_intake.available_inputs`
   - stores the structured receipt in `task_intake.context.planning_knowledge_ingress`

2. Projected the same receipt into `control_plane.knowledge_ingress`

3. Added a planning work-memory writeback helper
   - only acts for completed planning turns
   - writes narrow `active_project` / `decision_ledger` captures
   - respects explicit `memory_writeback_candidates` when present
   - emits the receipt to `control_plane.memory_writeback` and `effects.planning_memory_writeback`

4. Extended runtime-pack search metadata
   - bundle generation time
   - bundle age in hours
   - freshness state
   - readiness/check/scope fields

5. Added tests for
   - knowledge-ingress prompt injection
   - planning writeback receipt construction
   - route-level projection of knowledge-ingress and memory-writeback
   - runtime-pack bundle freshness/readiness metadata

## Design boundary

I deliberately did not change:

- planning runtime-pack hit ranking
- runtime visibility gate semantics
- planning checkpoint persistence model for writeback receipts
- existing `handoff/post_call_triage` auto-capture behavior

That kept the risky part additive while still making `W4` real on the northbound surface.
