# 30 Semantic Reconciliation Digest

Generated: `2026-05-09T15:11:02+08:00`

## Coverage

The prior coverage report is now reconciled into semantic actions, not only file counts.

- Unique indexed paths reconciled: `5916`.
- No-advice / boundary hits: `1564`.
- Primary evidence requirement hits: `3080`.
- Ledger-first hits: `3793`.
- Runtime / MCP / connector governance hits: `5866`.
- Planning follow-up hits: `5838`.
- MVP-not-enough / blocked-state hits: `3334`.

## Frozen Design Constraints

- `SC-001` design_constraint: Finbot output remains research-only: no investment advice, target price, production watchlist, broker action, position sizing, or trade signal.
- `SC-002` required_fix: Tier A requires claim-level primary/authority evidence and at least one explicit risk/contradiction; KOL-only cases stay High-interest unverified or lower.
- `SC-003` required_fix: Live evidence must bind accepted comments to succeeded agent runs; cancelled/failed runs remain discarded historical evidence.
- `SC-004` design_constraint: Capability promotion requires workflow_verified proof; endpoint_alive and tool_callable are lower proof levels.
- `SC-005` governance_boundary: Controller & Runtime Company is runtime/adapter lab only; Skill/MCP/Runtime/Memory policy is owned by Governance Company.
- `SC-006` required_fix: Historical Pro/advisor objections are operating inputs, not final authority; every cited objection must map to a ledger, backlog, policy, or rejection register.

## Asset Routing

- Pro/advisor/critical-review answers become `design_constraints_or_objections` and cannot act as final judge.
- Finbot runs and ledgers become reusable system inputs unless marked obsolete or evidence-missing.
- Runtime/MCP/Skill/Memory files become Governance policy inputs.
- Missing paths remain explicit blockers, not assumed capabilities.

Full row-level reconciliation is in `30_semantic_reconciliation_register.json`.
