# Premium Agent Ingress And Execution Cabin Blueprint Walkthrough v1

## What I did

Captured the architecture decision that came out of the discussion:

- `public agent facade` should not be framed as a fast, cheap chat ingress
- it should be treated as a premium, high-opportunity-cost, pre-contracted ask surface
- `cc-sessiond` should be treated as an execution cabin for slow-path, heavily orchestrated work

## Why this doc was needed

The prior conversation established a sharper product distinction:

- asking premium Web-automation-backed models is expensive in time and opportunity cost
- therefore the system should optimize for question quality and task structuring before execution
- prompt engineering should be server-side
- every high-cost ask should be followed by a quality / fit / route review
- `cc-sessiond` should evolve toward a reusable execution plane, not remain only a Claude Code coding helper

That reasoning had not yet been written down as a single system blueprint.

## Existing modules anchored in the blueprint

I verified and referenced the current reusable pieces:

- requirement / funnel path
  - `chatgptrest/workflows/funnel.py`
  - `chatgptrest/pipeline.py`
  - `chatgptrest/advisor/graph.py`
  - `chatgptrest/contracts/schemas.py`
- dispatch / project-card handoff
  - `chatgptrest/advisor/dispatch.py`
- answer-quality / post-ask review
  - `chatgptrest/advisor/qa_inspector.py`
  - `chatgptrest/core/thinking_qa.py`
- EvoMap
  - `chatgptrest/workflows/evomap.py`
  - `chatgptrest/evomap/*`
- execution cabin planning/history
  - `docs/2026-03-17_cc_sessiond_full_implementation_blueprint_v1.md`
  - `docs/2026-03-17_claude_agent_sdk_session_manager_assessment_v1.md`

## Output

Created:

- [2026-03-17_premium_agent_ingress_and_execution_cabin_blueprint_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-17_premium_agent_ingress_and_execution_cabin_blueprint_v1.md)

## Notes

- This change is documentation-only.
- I did not touch the unrelated dirty finbot/systemd changes already present in the worktree.
- No product code was modified, so no runtime regression test was needed for this documentation slice.
