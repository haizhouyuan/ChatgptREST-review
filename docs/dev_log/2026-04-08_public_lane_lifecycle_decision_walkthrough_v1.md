# Public Lane Lifecycle Decision Walkthrough v1

Date: 2026-04-08
Repo: ChatgptREST
Topic: public MCP lane lifecycle wording alignment

## What changed

This walkthrough records the repository-wide wording alignment after the red-team followup.

Updated surfaces:

- `ops/registries/surface_policy.yaml`
- `AGENTS.md`
- `docs/contract_v1.md`
- `docs/runbook.md`
- `skills-src/chatgptrest-call/SKILL.md`

Added decision record:

- `docs/reviews/2026-04-08_public_lane_lifecycle_decision_v1.md`

## Why

The repo had already implemented:

- contract-aware `advisor_agent_*`
- a narrow `coding_agent_*` lane
- `coding-agent-v1` wrapper default

But some guidance still drifted toward the older story that public advisor tools were the default surface for coding agents.

That drift was no longer acceptable because the platform now needs a stable lifecycle statement:

- `coding_agent_*` is the mature coding-agent default lane
- `advisor_agent_*` remains the broad public advisor / compatibility lane

## Exact policy outcome

1. `coding_agent_*`
   - default for Codex / Claude Code / Antigravity
   - canonical narrow contract
   - canonical answer retrieval through `coding_agent_answer`

2. `advisor_agent_*`
   - retained
   - not deprecated by this change
   - used only when the broader advisor contract is explicitly needed

## Why this matters

Without this wording alignment, the repo would keep advertising two contradictory defaults:

- code/runtime saying `coding-agent-v1`
- docs/runbook/bootstrap policy still hinting `advisor_agent_*`

That contradiction would keep reintroducing operator drift and client confusion.

## Notes

This change is documentation and registry alignment only.

It does not:

- remove `advisor_agent_*`
- rename MCP tools
- change runtime contracts by itself

The next follow-on work remains:

- live Deep Research finality gate
- `scope_project` pre-backfill audit
- promotion root-cause diagnosis
