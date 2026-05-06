You are Claude Code working on ChatgptREST.

Repo / worktree:
- /vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317

Mode:
- Use Claude Code Agent Teams.
- This is a quality-first business integration validation task.
- Do not optimize for low token usage. Optimize for correctness, coverage, evidence, and actionable outcomes.

Primary plan to execute:
- /vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317/docs/2026-03-17_openclaw_openmind_agent_business_integration_test_plan_v1.md

Read first:
- /vol1/1000/projects/ChatgptREST/AGENTS.md
- /vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317/docs/2026-03-17_openclaw_openmind_agent_business_integration_test_plan_v1.md
- /vol1/1000/projects/ChatgptREST/docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v2.md

Mission:
- Execute the full OpenClaw / OpenMind unified agent business integration test plan.
- Collect evidence for BI-01 through BI-14.
- If failures are caused by repo code in this worktree, fix them, add tests when appropriate, rerun the affected suites, and continue the plan.
- If blockers are external or environment-bound, capture exact evidence and stop only after the cause is clearly isolated.

Critical review bar:
- Do not stop at unit tests.
- Verify actual business behavior of the public agent surface.
- Verify the OpenClaw plugin path is converged to the public agent surface.
- Verify clients do not need to manually drop to `/v1/jobs/{job_id}/wait` or `/answer`.
- Every failed business case must end in one of:
  - fixed in repo and re-verified
  - isolated external blocker with concrete evidence

Agent Teams topology:

1. `test-lead`
- Owns the matrix, assignment, evidence ledger, and final integration summary
- Owns final JSON result
- Decides whether a failure should route to a fix lane or be marked as external blocker

2. `http-facade-lane`
- Runs BI-01 to BI-08
- Focus:
  - `/v3/agent/turn`
  - `/v3/agent/session/{session_id}`
  - `/v3/agent/cancel`
  - ChatGPT Pro, Gemini Deep Think, Gemini Deep Research, dual-model consult, Gemini image

3. `mcp-wrapper-lane`
- Runs BI-09 and BI-10
- Focus:
  - public MCP facade
  - `advisor_agent_turn`
  - `advisor_agent_status`
  - `advisor_agent_cancel`
  - `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
  - CLI agent-first behavior and parameter forwarding

4. `openclaw-plugin-lane`
- Runs BI-11 and BI-12
- Focus:
  - `openmind-advisor` plugin
  - OpenClaw rebuild output
  - generated plugin config
  - convergence to `/v3/agent/turn`

5. `auth-fault-report-lane`
- Runs BI-13 and BI-14
- Focus:
  - auth matrix
  - blocked / cooldown / needs_followup / error handling
  - evidence collation
  - residual risk summary

Execution rules:
- The lead lane must keep a live matrix of BI cases, status, evidence path, blocker type, and whether code fixes were required.
- Prefer parallel execution of independent business lanes.
- Do not let support lanes make overlapping code edits without coordination.
- If code fixes are needed, the lead lane decides which lane owns the patch.
- Commit every meaningful fix.
- Keep docs-only evidence commits separate from production code fixes when practical.

Automated gate that must pass before business validation:
- `./.venv/bin/pytest -q tests/test_agent_v3_routes.py`
- `./.venv/bin/pytest -q tests/test_agent_mcp.py`
- `./.venv/bin/pytest -q tests/test_skill_chatgptrest_call.py`
- `./.venv/bin/pytest -q tests/test_openclaw_cognitive_plugins.py`
- `./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py`
- `./.venv/bin/pytest -q tests/test_mcp_advisor_tool.py`
- `./.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py`
- `./.venv/bin/pytest -q tests/test_cli_improvements.py`
- `./.venv/bin/pytest -q tests/test_routes_advisor_v3_security.py`

Business validation requirements:
- Run BI-01 through BI-14 from the referenced test plan.
- Save evidence for every BI case:
  - raw request/response JSON
  - `session_id`, `run_id`, `job_id`, `consultation_id`
  - request/result artifacts
  - events
  - answer preview
  - plugin transcript or rebuild evidence where applicable

Failure handling requirements:
- If a BI case fails because of repo code:
  - identify root cause
  - fix the code
  - add or update regression tests when appropriate
  - rerun affected automated suites
  - rerun the failed BI case
- If a BI case fails because of environment or external provider behavior:
  - do not paper over it
  - save exact evidence
  - explain whether it is deterministic, flaky, auth-bound, or provider-bound

Expected output quality:
- This is a real acceptance run, not a smoke test.
- Final report must make it easy for a reviewer to answer:
  - which BI cases passed
  - which BI cases required fixes
  - which BI cases remain blocked
  - whether the converged public agent surface is acceptable for OpenClaw/OpenMind usage

Required deliverables before finishing:
- one walkthrough doc with `_v1.md`
- one evidence summary doc with BI case ledger
- code commits for any fixes made
- closeout run

When finished, return JSON only with this shape:
{
  "status": "succeeded" | "blocked" | "failed",
  "branch": "feat/public-advisor-agent-facade",
  "summary": "short summary",
  "commits": ["sha subject", "..."],
  "tests": [
    {"command": "pytest ...", "status": "passed|failed|not_run", "details": "short note"}
  ],
  "business_cases": [
    {"id": "BI-01", "status": "passed|failed|blocked", "evidence": "path", "note": "short note"}
  ],
  "walkthrough_path": "absolute path or empty string",
  "evidence_summary_path": "absolute path or empty string",
  "changed_files": ["path", "..."],
  "residual_risks": ["...", "..."],
  "notes": ["...", "..."]
}
