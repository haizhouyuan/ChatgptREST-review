You are Claude Code working on ChatgptREST.

Repo:
- /vol1/1000/worktrees/chatgptrest-premium-ingress-20260318

Branch:
- feat/premium-ingress-blueprint-implementation

Mission:
- Complete the remaining premium ingress blueprint work. The current branch is not done.

Read these first, in order:
- /vol1/1000/worktrees/chatgptrest-premium-ingress-20260318/AGENTS.md
- /vol1/1000/projects/ChatgptREST/docs/2026-03-17_premium_agent_ingress_and_execution_cabin_blueprint_v1.md
- /vol1/1000/worktrees/chatgptrest-premium-ingress-20260318/docs/dev_log/2026-03-18_premium_ingress_blueprint_gap_review_v1.md
- /vol1/1000/worktrees/chatgptrest-premium-ingress-20260318/docs/dev_log/2026-03-18_premium_ingress_blueprint_cc_sessiond_task_spec_v2.md

Do not assume the previous implementation completed the blueprint. It did not.

You must finish these remaining gaps:

1. Wire `chatgptrest/advisor/prompt_builder.py` into the real `/v3/agent/turn` execution path so contract-driven prompt assembly actually affects the submitted request.
2. Add a real clarify gate for materially incomplete premium asks, instead of always executing.
3. Persist post-ask review signals into the existing EvoMap or QA feedback path.
4. Add a proper walkthrough doc with `_v1.md` suffix.

Hard requirements:
- Use GitNexus before editing symbols.
- Commit every meaningful slice.
- Do not touch unrelated dirty files.
- Preserve backward compatibility for callers that only send `message`.
- Add and run focused tests that prove prompt-builder execution, clarify gating, and EvoMap writeback semantics.
- Run closeout before finishing.

Minimum tests to run:
- /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py tests/test_agent_mcp.py tests/test_openclaw_cognitive_plugins.py tests/test_bi14_fault_handling.py
- /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_ask_contract.py tests/test_prompt_builder.py tests/test_post_review.py

When finished, return JSON only with this shape:
{
  "status": "succeeded" | "blocked" | "failed",
  "branch": "feat/premium-ingress-blueprint-implementation",
  "summary": "short summary",
  "commits": ["sha subject", "..."],
  "tests": [
    {"command": "pytest ...", "status": "passed|failed|not_run", "details": "short note"}
  ],
  "walkthrough_path": "absolute path or empty string",
  "changed_files": ["path", "..."],
  "residual_risks": ["...", "..."],
  "notes": ["...", "..."]
}
