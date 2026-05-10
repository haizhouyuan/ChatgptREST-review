# 05 Finbot Research OS v1 Architecture

Generated: `2026-05-09T00:00:00+08:00`

Finbot Research OS v1 is a supervised research operating system. Its center is ledger governance, not a multi-agent demo, trading runtime, or dashboard shell. TradingAgents contributes role separation and escalation patterns; Fincept contributes terminal/workbench ergonomics. Neither is the authority model.

## Operating Layers

1. `InvestorPolicy`: boundary, scope, excluded actions, attention budget, market coverage and review cadence.
2. `SourceAlphaLedger`: source accounts, tiers, claim-ready status, trust notes and noise budget.
3. `DataAuthority`: point-in-time rules, authority tiers, freshness and raw artifact requirements.
4. `ContentItemLedger`: article/video/report/transcript items and provenance.
5. `ClaimLedger`: atomic claims with source span, status and required checks.
6. `EvidenceLedger`: raw artifacts, checksums, source route, available_at and claim bindings.
7. `EntityResolutionLedger`: company/ticker/security mapping with confidence and known bad mappings.
8. `OpportunityCaseLedger`: research case object, not recommendation object.
9. `SignalWindowLedger`: research review windows only; no trade signal.
10. `ThesisLedger`: variant view, contradiction set, kill/park/reopen criteria.
11. `RiskQALedger`: no-advice/no-trading/entity/authority drift checks.
12. `HumanReviewQueue`: user and agent follow-up questions.
13. `DecisionLedger` / `NonDecisionLedger`: records what was decided or not decided; does not execute financial decisions.
14. `PortfolioGuard`: research-only guardrail for concentration, conflict and scope checks.
15. `ReviewGate` / `AuditGate`: freezes what can move forward and what must remain blocked.

## Flow

Source intake -> ContentItem -> Claim -> EvidenceGap/EvidenceItem -> Entity Resolution -> Research Case -> Risk QA -> Human Review -> Planning Follow-up.
