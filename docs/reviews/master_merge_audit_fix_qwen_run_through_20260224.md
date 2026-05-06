# Master Merge Audit: `fix/qwen-run-through` -> `master` (2026-02-24)

## 1) Scope and Baseline

- Audit time (UTC): `2026-02-24T10:01:14Z`
- Merge range: `d458981..d1d3556`
- Source branch: `origin/fix/qwen-run-through`
- Target branch: `origin/master`
- Merge mode: fast-forward

Range stats:

- commits (no merge commits): `20`
- files changed: `55`
- insertions/deletions: `+9564 / -298`

## 2) Merge Execution Record

Executed in clean worktree:

- `git worktree add -b docs/master-merge-audit-20260224 /tmp/chatgptrest-master-audit-20260224 origin/master`
- `git -C /tmp/chatgptrest-master-audit-20260224 merge --ff-only origin/fix/qwen-run-through`
- `git -C /tmp/chatgptrest-master-audit-20260224 push origin HEAD:master`

Push result:

- `origin/master`: `d458981 -> d1d3556`

## 3) Per-Commit Inventory (逐一查明)

- `f3d0e2f349bc1353f7f6e046ee9248875b73478a` fix(qwen): add noVNC login hint + smoke/doctor scripts
  - files: chatgpt_web_mcp/providers/qwen_web.py; docs/runbook.md; ops/qwen_doctor.sh; ops/smoke_test_qwen.sh; tests/test_qwen_viewer_hint.py
- `d0536d77111c4efa5689e6ee5d2d2d2add474b75` fix(gemini): harden Pro selector and import-code fail-open
  - files: chatgpt_web_mcp/providers/gemini/core.py; chatgpt_web_mcp/providers/gemini_helpers.py; docs/runbook.md; ops/systemd/install_user_units.sh; tests/test_gemini_mode_selector_resilience.py
- `9666d959d6044ea5bb2e6f5eefa2dfbdc37f84e1` fix: harden driver CDP binding and blocked recovery
  - files: chatgpt_web_mcp/_tools_impl.py; chatgptrest/executors/repair.py; docs/handoff_chatgptrest_history.md; docs/repair_agent_playbook.md; docs/runbook.md; ops/maint_daemon.py; ops/start_driver.sh; ops/systemd/chatgptrest-chrome.service; ops/systemd/chatgptrest-driver.service; ops/systemd/chatgptrest.env.example; tests/test_maint_daemon_provider_tools.py; tests/test_repair_provider_tools.py
- `c4fa14c0b2c1aead4a77abc3a5a68652cae7f6e2` fix(gemini): harden deep-research toggle state inference
  - files: chatgpt_web_mcp/providers/gemini/core.py; docs/handoff_chatgptrest_history.md; docs/runbook.md; tests/test_gemini_mode_selector_resilience.py
- `dd824c4f5ab977fcfc5772059b009c8c8fe8e9a6` feat(mcp): hard-disable foreground wait via env switch
  - files: chatgptrest/mcp/server.py; docs/runbook.md; ops/systemd/chatgptrest.env.example; tests/test_mcp_job_wait_autocooldown.py
- `c55a84d7aaf5821498e9fc5ece0f6f86d8719caa` fix(autofix): clear systemd start-limit-hit before driver restart
  - files: chatgptrest/executors/repair.py; ops/maint_daemon.py
- `9aab6a7e133b089278e1083b5c01d09e65d6f81b` fix(chatgpt_web): recover upload on set_input_files target-closed
  - files: chatgpt_web_mcp/_tools_impl.py; tests/test_chatgpt_upload_recovery.py
- `e08e6f211340834f72d276997e39911937839c7b` fix(chatgpt_web): add upload-stage retry for page-closed drift
  - files: chatgpt_web_mcp/_tools_impl.py
- `956be4be39ee81b75e638e3d8377278cf65e0d70` fix(send): stop sticky upload retry loops; add incident-class codex runbook
  - files: AGENTS.md; chatgptrest/core/job_store.py; docs/README.md; docs/handoff_chatgptrest_history.md; docs/repair_agent_playbook.md; docs/runbook.md; tests/test_leases.py
- `ffc9ea0120549c1b85d04c1572ce752dd0547fae` [codex-session-id:chatgptrest-orch] ops/chatgpt_agent_shell_v0: add Idempotency-Key header on submit
  - files: ops/chatgpt_agent_shell_v0.py
- `320923ba88c59e34a5a654548cb882512259a563` docs: add 2026-02-24 oncall self-heal retro report
  - files: docs/reviews/chatgptrest_oncall_self_heal_retro_20260224.md
- `88e7cad0cc5d28c78ceb93b9023e9d0fa3ffe770` fix(gemini): harden deep research tool selection in UI
  - files: chatgpt_web_mcp/providers/gemini/core.py; chatgpt_web_mcp/providers/gemini/deep_research.py; chatgpt_web_mcp/providers/gemini_helpers.py; docs/reviews/gemini_dr_ui_probe_fix_20260224.md; tests/test_gemini_mode_selector_resilience.py; tests/test_gemini_tools_menu_selectors.py
- `23804d7448793b9bd6243cc6360d517d98b80bfd` feat(gemini): add deep research gdoc export fallback
  - files: chatgpt_web_mcp/providers/gemini/deep_research_export.py; chatgpt_web_mcp/providers/gemini_web.py; chatgpt_web_mcp/tools/gemini_web.py; chatgptrest/executors/gemini_web_mcp.py; tests/fixtures/mcp_tools_snapshot.json; tests/test_gemini_deep_research_gdoc_fallback.py
- `bf028e1e2cd06cf99e67d684e8da94d963099446` feat(ops): add wrapper v1 with dual-review hardening and tests
  - files: docs/reviews/wrapper_v1_dual_review_devlog_20260224.md; ops/chatgpt_wrapper_v1.py; tests/test_wrapper_v1.py
- `396ef0db4ebe469a7530c93d1fb02782f2b84629` fix(ops): harden advisor identity repair and followup turn guard
  - files: ops/chatgpt_agent_shell_v0.py; ops/chatgpt_wrapper_v1.py; tests/test_chatgpt_agent_shell_v0_client_headers.py; tests/test_chatgpt_agent_shell_v0_turn_guard.py; tests/test_wrapper_v1.py
- `058d1300b46ff59ec8f2612520c13861708ed1eb` feat(advisor): add first-class REST and MCP advisor entrypoints
  - files: chatgptrest/api/app.py; chatgptrest/api/routes_advisor.py; chatgptrest/api/schemas.py; chatgptrest/mcp/server.py; docs/contract_v1.md; tests/test_advisor_api.py; tests/test_mcp_advisor_tool.py
- `e8d4023b2ba4eae302786c9f834841b190816c71` fix(advisor): enforce safe options and non-blocking stateless plan mode
  - files: chatgptrest/api/routes_advisor.py; docs/contract_v1.md; tests/test_advisor_api.py
- `a64aa9ec769d064228e3e176865d0faf1b34cd31` fix(mcp): prevent stateless background wait hangs
  - files: chatgptrest/mcp/server.py; tests/test_mcp_job_wait_autocooldown.py; tests/test_mcp_stateless_mode.py
- `88a2a882bb5842793ddc76dc4e38096ceec5dd10` fix(worker): guard deep-research export reconcile and tool-payload completion
  - files: chatgptrest/worker/worker.py; docs/reviews/chatgptrest_chain_runthrough_remediation_plan_20260224.md; tests/test_deep_research_export_guard.py; tests/test_tool_payload_answer_guard.py
- `d1d35561d9428894aaca5c4e9deb7a330db13ccf` chore(worker): audit wait no-progress guard eval failures
  - files: chatgptrest/worker/worker.py; docs/reviews/chatgptrest_chain_runthrough_remediation_plan_20260224.md; tests/test_wait_no_progress_guard_audit.py

## 4) Verification

### 4.1 Targeted regression in isolated worktree

Command:

```bash
PYTHONPATH=/tmp/chatgptrest-master-audit-20260224 \
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_chatgpt_agent_shell_v0_client_headers.py \
  tests/test_chatgpt_agent_shell_v0_turn_guard.py \
  tests/test_deep_research_export_guard.py \
  tests/test_gemini_deep_research_gdoc_fallback.py \
  tests/test_maint_daemon_provider_tools.py \
  tests/test_mcp_advisor_tool.py \
  tests/test_mcp_job_wait_autocooldown.py \
  tests/test_mcp_stateless_mode.py \
  tests/test_qwen_viewer_hint.py \
  tests/test_repair_provider_tools.py \
  tests/test_tool_payload_answer_guard.py \
  tests/test_wrapper_v1.py
```

Result:

- `72 tests collected`
- all passed (`[100%]`)

### 4.2 Full changed-suite collect check (18 files)

Attempted to collect all changed tests from this merge range. Result:

- `72 tests collected, 6 errors`

Error classes observed:

1. `ImportError: cannot import name '_enforce_client_name_allowlist' from chatgptrest.api.routes_jobs`
   - triggered by imports in `chatgptrest/api/routes_advisor.py`
2. `ModuleNotFoundError: No module named 'chatgpt_web_mcp.providers.gemini.capture_ui'`
   - `chatgpt_web_mcp/providers/gemini_web.py` imports module not present in tracked tree

Implication:

- Main merge is complete, but isolated-environment collection exposes integration gaps that should be fixed in a follow-up patch before claiming full green on this changed-suite set.

## 5) Independent Judgment

- The merge to `master` is correct and complete from Git-history perspective (20 commits fully landed).
- Critical remediation from `88a2a88` and `d1d3556` is included in `master`.
- There are two post-merge integrity gaps in isolated test collection:
  - advisor import contract drift (`routes_advisor` -> `routes_jobs` helper)
  - missing `gemini/capture_ui.py` tracked module
- Recommendation: handle these as immediate follow-up fixes (P0) and rerun full changed-suite collection.
