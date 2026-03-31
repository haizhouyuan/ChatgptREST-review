You are Claude Code working on ChatgptREST.

Repo:
- /vol1/1000/projects/ChatgptREST

Mission:
- Upgrade premium ingress so it first understands the ask, then compiles the right prompt, then executes.

Read these first:
- /vol1/1000/projects/ChatgptREST/AGENTS.md
- /vol1/1000/projects/ChatgptREST/docs/2026-03-17_premium_agent_ingress_and_execution_cabin_blueprint_v1.md
- /vol1/1000/projects/ChatgptREST/docs/2026-03-18_premium_agent_ingress_and_execution_cabin_blueprint_v2.md
- /vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-18_premium_ingress_strategist_task_spec_v1.md

Important constraints:
- Do not move ordinary premium asks onto cc-sessiond.
- Do not make Codex the default backend for public agent ingress.
- Preserve OpenClaw compatibility through the public agent facade.
- Keep public MCP surface minimal.
- Use feature flags for rollout.

Required outcome:
1. Add strategist layer for premium ingress.
2. Replace threshold-only clarify with strategist-driven clarify gate.
3. Turn prompt_builder into a compiler from strategy plan.
4. Make controller path consume compiled prompt semantics.
5. Enrich post-review and EvoMap writeback.

Minimum tests to run:
- ./.venv/bin/pytest -q tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py tests/test_agent_mcp.py
- ./.venv/bin/pytest -q tests/test_ask_contract.py tests/test_prompt_builder.py tests/test_post_review.py
- plus any new strategist/clarify/EvoMap tests you add

Output format:
- Return JSON only with:
{
  "status": "succeeded" | "blocked" | "failed",
  "branch": "branch-name",
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
