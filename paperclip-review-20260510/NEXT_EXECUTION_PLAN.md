# Next Execution Plan

Generated: 2026-05-10T19:16:00+08:00

## Goal

Move from a published review package plus Pro critique to a smaller, stricter Paperclip operating loop that proves real user value. Do not claim production-ready. The target label for the next pass should be a scoped operating-loop pass with explicit blocked items.

## Keep

- Public review package discipline: manifest, secret scan, file sizes, SHA checks, upload record.
- Governance ownership over runtime, memory, Skill/MCP, provider quarantine, and false-pass policy.
- Finbot Engineering as capability lab, not trading or production watchlist machinery.
- Current truth / blocker board / execution matrix as operating evidence primitives.

## Stop

- Bigger package generation as a substitute for behavior.
- DeepResearch when the user asked for normal Pro consultation.
- Fixture-only or endpoint-only readiness claims.
- Any Finbot output that resembles investment advice, target price advice, trade signal, production watchlist, broker action, or automatic trading.

## Rebuild

1. Create one tight Paperclip operating-loop replay across Governance, Planning, Finbot Research, and Finbot Engineering.
2. For each lane, require one live issue or carrier issue with succeeded run evidence, agent-authored comment, artifact path, validator/readback, and closeout state.
3. For Finbot, choose a small number of cases and require claim-level primary/authority evidence before any high tier classification.
4. For Planning, turn Finbot outputs into concrete human decisions and follow-up evidence actions.
5. For Governance, run negative fixtures against false-pass modes and capability readiness overclaims.
6. Publish a short follow-up package focused on behavior evidence, not all historical material.

## Acceptance Gates

- `public_review_package_published`: GitHub branch contains package and upload record.
- `normal_pro_consultation_valid`: Pro consultation route is non-DeepResearch and answer is stored with request and summary.
- `live_issue_evidence_valid`: each in-scope company lane has succeeded run or clearly labeled carrier/blocker reason.
- `finbot_research_only_valid`: no advice, no target price advice, no broker/trading action, no production watchlist or trade signal.
- `capability_readiness_honest`: endpoint-only, fixture-only, or candidate connector cannot be labeled workflow verified.
- `planning_output_actionable`: follow-up queue contains specific user decisions, agent tasks, and evidence gaps.
- `fresh_operator_replayable`: artifact paths and validators allow a fresh operator to inspect and rerun the core checks.

## Non-Goals

- No automatic trading.
- No investment advice.
- No new provider enablement for quarantined providers.
- No native MCP/skill/runtime config mutation unless Governance approves risk and rollback.
- No claim of production-ready from this package alone.
