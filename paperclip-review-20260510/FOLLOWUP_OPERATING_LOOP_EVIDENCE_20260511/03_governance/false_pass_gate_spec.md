# Governance False-Pass Gate Spec

Generated: 2026-05-11
Controller: codex_parent

## Purpose

This gate prevents Paperclip company work from treating weak evidence as a real
operating-loop pass.

## Reject Conditions

The gate must reject any claim that relies on:

- endpoint-only readiness;
- fixture-only readiness;
- controller-only evidence without agent-owned run/comment/readback;
- investment advice disguised as a research memo;
- target-price-as-advice or target price recommendation;
- production watchlist, trade signal, broker action or automatic trading;
- quarantined provider enablement for MiniMax, DeepSeek, Tavily or Brave;
- local LLM production routing or authority-memory promotion.

## Acceptable Conditions

The gate may accept:

- agent-owned run evidence with succeeded run, agent-authored comment,
  createdByRunId binding, artifact path and status readback;
- candidate connector records that explicitly do not claim verified workflow;
- research-only Finbot cases with primary evidence, risk QA and human review
  questions, as long as they avoid advice/trading/watchlist language;
- local LLM benchmark evidence marked research-only and no-production-route.

## Required Output

Validation result path:

`/vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-11_codex_parent_8h_operating_program/03_governance/false_pass_gate_result.json`
