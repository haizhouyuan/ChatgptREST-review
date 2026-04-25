# Claim Lineage Matrix

Generated: 2026-04-26
Status: boss-demo front-stage evidence
Purpose: show that the system can generate market drafts while blocking unsupported claims.

## Allowed Draft Claims

| Asset sentence | Source | Label | Status | Owner | Action |
| --- | --- | --- | --- | --- | --- |
| Designed for compact kitchen routines. | RS-001 | demo_sample | Draft allowed | Data Truth Guard | Keep demo label |
| Explores a fold-flat helper-tower concept. | LAB-4 | demo_policy | Draft allowed | Design Strategy | Keep review-ready wording |
| Visible lock-state detail is part of the concept direction. | RS-003 / LAB-6 | demo_sample | Draft allowed | Design Director | Review mechanism before safety wording |
| Cleanable step geometry is a design exploration. | RS-002 / LAB-7 | demo_sample | Draft allowed | DFM/Safety | Require physical cleaning review |
| Draft assets are local and not launched. | LAB-8 | verified_fact | Allowed | Demo Producer | Keep local-only boundary |

## Blocked Claims

| Tempting sentence | Source | Label | Status | Owner | Required action |
| --- | --- | --- | --- | --- | --- |
| Safer for toddlers. | none | forbidden | Blocked | DFM/Safety | Remove until test evidence and safety review exist |
| Certified compliant. | none | forbidden | Blocked | Human safety reviewer | Never use without certification source |
| Proven market demand. | none | forbidden | Blocked | Data Truth Guard | Replace with demo-sample wording |
| Lower cost than competitors. | none | forbidden | Blocked | Finance / Sourcing | Require BOM and quote evidence |
| Available now. | none | forbidden | Blocked | Launch owner | Do not publish or collect real waitlist |

## Live Demo Block

Input temptation:

```text
Can we say this is certified safe and proven in market?
```

System response:

```text
Blocked.
Reason:
- no certification source
- demo samples cannot prove demand
- human safety review required
- no production launch approval
```

This is the strongest wow moment: the AI team does not just write copy; it knows when not to write copy.
