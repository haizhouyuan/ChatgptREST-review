You are Claude Code working on ChatgptREST.

Repo:
- /vol1/1000/projects/ChatgptREST

Mission:
- Take the current `cc-sessiond` scaffold to a merge-ready full implementation.

Read these first, in order:
- /vol1/1000/projects/ChatgptREST/AGENTS.md
- /vol1/1000/projects/ChatgptREST/docs/2026-03-17_claude_agent_sdk_session_manager_assessment_v1.md
- /vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-17_claude_agent_sdk_minimax_backend_probe_v1.md
- /vol1/1000/projects/ChatgptREST/docs/2026-03-17_cc_sessiond_full_implementation_blueprint_v1.md
- /vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-17_cc_sessiond_full_implementation_task_spec_for_cc_v1.md

Context:
- The current scaffold commit is not merge-ready.
- Main known failures:
  - wrong route import path
  - route not mounted in `create_app()`
  - scheduler loop never started
  - sync cancel inside async context
  - fake continue semantics
  - `wait(timeout)` ignores timeout
  - SDK dependency not declared / not covered

Required outcome:
1. Repair the existing scaffold and mount it into the real API app.
2. Build a backend adapter layer for:
   - official Claude Agent SDK
   - existing `CcExecutor` headless fallback
   - optional `CcNativeExecutor` adapter boundary
3. Make continue/cancel/wait semantics real.
4. Persist proper session artifacts and events.
5. Add direct route/integration tests proving the surface actually works.

Hard requirements:
- Use GitNexus before editing symbols.
- Commit every meaningful slice.
- Do not touch unrelated dirty files.
- Keep compatibility-first behavior.
- If you add official SDK usage, update `pyproject.toml` and lockfile.
- Write a walkthrough doc with `_v1.md`.
- Run closeout before finishing.

Minimum tests to actually run:
- ./.venv/bin/pytest -q tests/test_cc_sessiond.py
- ./.venv/bin/pytest -q tests/test_api_startup_smoke.py
- ./.venv/bin/pytest -q tests/test_cc_executor.py
- ./.venv/bin/pytest -q tests/test_advisor_runtime.py
- plus any new direct `cc_sessiond` route/integration tests you add

Important review bar:
- Green tests are not enough if they only cover fake in-memory behavior.
- The route must import.
- The app must expose `/v1/cc-sessions`.
- A created session must be able to leave `pending`.
- Cancel must work from async route context.
- Continue must use real backend continuation semantics, not an ignored options field.

When finished, return JSON only with this shape:
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
