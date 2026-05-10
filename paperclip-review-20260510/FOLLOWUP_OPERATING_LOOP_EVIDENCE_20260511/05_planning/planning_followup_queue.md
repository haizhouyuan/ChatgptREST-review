# Planning Follow-Up Queue

Generated: 2026-05-11T00:34:15+08:00  
Controller: codex_parent

Boundary: This queue converts Finbot research outputs into supervised research
actions only. It does not authorize investment advice, target-price advice,
trade signals, broker actions, automatic trading, position sizing or a
production watchlist.

## User Decisions

| ID | Decision | Input | Required Outcome |
| --- | --- | --- | --- |
| `PLA-FIN-001` | Choose whether PLTR remains in the next research sprint. | `OA-12-03-pltr-source-system-gaps-to-enable-next` is parked because source binding is summary-level. | `continue_research` or `park`; no buy/sell/hold decision. |
| `PLA-FIN-002` | Choose whether ANET/China supply-chain angle is worth primary-source validation. | `OA-12-02-anet-policy-driven-china-supply-chains` is parked due to candidate source routes. | `continue_research` or `retire_theme`. |
| `PLA-FIN-003` | Choose whether PANW platform consolidation remains a high-interest theme. | `OA-11-03-panw-security-platform-consolidation` lacks trace-bound primary issuer evidence. | `continue_research` or `park`. |

## Evidence Gaps

| ID | Case | Evidence Gap | Owner |
| --- | --- | --- | --- |
| `PLA-GAP-001` | PLTR | Bind `EV-12-PLTR` to exact primary filing or authority artifact path, source timestamp and trace point. | Finbot Research |
| `PLA-GAP-002` | ANET | Add authority source for the policy/supply-chain claim and at least one counter-source. | Finbot Research |
| `PLA-GAP-003` | PANW | Add issuer filing/transcript trace and refutation route. | Finbot Research |
| `PLA-GAP-004` | PLTR / OA-X139 | Do not reuse mismatched `EV-05-CROX`; create new ticker-aligned evidence or keep rejected. | Finbot Research |
| `PLA-GAP-005` | RDDT / OA-X140 | Do not reuse mismatched `EV-05-ELF`; create new ticker-aligned evidence or keep rejected. | Finbot Research |

## Agent Follow-Up Actions

| ID | Action | Done Criteria |
| --- | --- | --- |
| `PLA-ACT-001` | Expand Finbot hard review to 10 cases and require exact five-tuples. | `04_finbot/finbot_hard_review_matrix_v2.json` exists and validates. |
| `PLA-ACT-002` | Promote only cases with primary/authority evidence, counter-evidence and human-review action. | `04_finbot/finbot_high_quality_candidate_register.md` names at least 5 high-quality candidates or explains why not. |
| `PLA-ACT-003` | Keep rejected cases out of top opportunity surfaces unless rebuilt with new aligned evidence. | Rejected register references `OA-X139` and `OA-X140` as non-reusable by score alone. |

## Current Status

Status: `ready_for_agent_readback`.

This queue is concrete enough for Planning to validate: each row is a user
decision, evidence gap or agent follow-up action.
