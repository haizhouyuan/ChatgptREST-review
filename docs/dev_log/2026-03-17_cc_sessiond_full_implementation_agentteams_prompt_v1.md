You are Claude Code working on ChatgptREST.

Repo:
- /vol1/1000/projects/ChatgptREST

Mode:
- Use Claude Code Agent Teams.
- Optimize for quality and correctness first, not token savings.
- Use a single integration lead lane plus bounded supporting lanes.

Mission:
- Take the current `cc-sessiond` scaffold to a merge-ready full implementation.

Read these first, in order:
- /vol1/1000/projects/ChatgptREST/AGENTS.md
- /vol1/1000/projects/ChatgptREST/docs/2026-03-17_claude_agent_sdk_session_manager_assessment_v1.md
- /vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-17_claude_agent_sdk_minimax_backend_probe_v1.md
- /vol1/1000/projects/ChatgptREST/docs/2026-03-17_cc_sessiond_full_implementation_blueprint_v1.md
- /vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-17_cc_sessiond_full_implementation_task_spec_for_cc_v1.md

Current reality:
- The existing scaffold is not merge-ready.
- Main known failures:
  - wrong route import path
  - route not mounted in `create_app()`
  - scheduler loop never started
  - sync cancel inside async context
  - fake continue semantics
  - `wait(timeout)` ignores timeout
  - SDK dependency not declared / not covered

Team topology:

1. Lead lane: `integration-lead`
- Owns final architecture and merge decisions
- Owns write access to these core files:
  - `chatgptrest/api/routes_cc_sessiond.py`
  - `chatgptrest/api/app.py`
  - `chatgptrest/kernel/cc_sessiond/client.py`
- Responsible for final integration, conflict resolution, and final test run

2. Support lane: `backend-adapters`
- Build backend abstraction and adapters
- Primary files:
  - `chatgptrest/kernel/cc_sessiond/base.py` or equivalent
  - `chatgptrest/kernel/cc_sessiond/backend_sdk.py`
  - `chatgptrest/kernel/cc_sessiond/backend_cc_executor.py`
  - optional adapter boundary for `CcNativeExecutor`
- Must not directly rewrite route wiring without lead approval

3. Support lane: `state-lifecycle`
- Focus on registry, scheduler, artifact store, cancel/wait/continue semantics
- Primary files:
  - `chatgptrest/kernel/cc_sessiond/registry.py`
  - `chatgptrest/kernel/cc_sessiond/scheduler.py`
  - `chatgptrest/kernel/cc_sessiond/events.py`
  - new artifact helper files if needed
- Must coordinate any client interface changes with integration lead

4. Support lane: `tests`
- Focus on route and integration coverage
- Primary files:
  - `tests/test_cc_sessiond.py`
  - new `tests/test_cc_sessiond_routes.py`
  - new `tests/test_cc_sessiond_integration.py`
  - `tests/test_api_startup_smoke.py`
- Should avoid editing production files unless absolutely necessary

5. Support lane: `docs`
- Focus on contract, walkthrough, rollout notes
- Primary files:
  - `docs/contract_v1.md`
  - new walkthrough doc
  - any cc-sessiond docs needed

Execution rules:
- Do not let multiple lanes edit the same core file at once.
- The lead lane must integrate adapter and lifecycle work after reviewing support lane diffs.
- If there is uncertainty between speed and correctness, choose correctness.
- Use stronger LLM reasoning when architecture or continuation semantics are ambiguous.
- Do not implement fake continuation or fake cancellation just to satisfy tests.

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
- The dependency story must be reproducible from repo files, not local machine accidents.

Recommended delivery sequence:

Phase A: lead lane repairs scaffold and app wiring
Phase B: adapter lane and lifecycle lane build their slices in parallel
Phase C: test lane adds direct route/integration coverage against the integrated branch
Phase D: docs lane updates contract and walkthrough after final behavior is stable
Phase E: lead lane runs the full required test matrix, resolves conflicts, and prepares final PR

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
