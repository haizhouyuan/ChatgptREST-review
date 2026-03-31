# 2026-03-06 Full Issue Sweep And Full Regression

## Context

User request: inspect open issues, fix the code-addressable ones directly on `master`, and run full regression without a PR.

This sweep intentionally focused on issues that were still reproducible or still represented real control-plane risk in the current tree. Historical auto-reports, external quota incidents, and pure feature requests were not force-closed as "fixed".

## What Changed

### 1. ChatGPT progress/min-chars visibility

- Added `phase_detail`, `answer_chars`, `completion_quality`, `last_event_type`, `last_event_at`, `prompt_sent_at`, and `assistant_answer_ready_at` to JobView/result surfaces.
- Restored `min_chars` exposure on unified MCP ask/followup flows.
- Added tests covering unified `min_chars` defaults and progress field exposure.

Related commit:
- `41e0a07` `fix: expose job progress and unified min chars guards`

### 2. Gemini robustness

- Hardened Gemini multi-file attachment handling by collapsing multiple text-like attachments into a generated bundle when needed.
- Added `.patch` / `.diff` support to Gemini attachment bundling.
- Added follow-up send observation so Gemini follow-ups do not silently re-scrape the parent answer when no new response actually started.
- Fixed Gemini wait loop robustness:
  - wait deadline tests now use executor clock injection,
  - transient wait transport failures degrade to retryable `in_progress` instead of raw executor crashes,
  - deep-research GDoc fallback honors env toggles correctly even after module import.

Related commit:
- `c7a1c91` `fix: harden gemini followups and attachment bundling`
- `db10b35` `fix: stabilize executor wait loops and routing config`

### 3. Advisor / Feishu / repair control plane

- Unified `/v2/advisor/*` auth and rate-limit enforcement through shared router dependencies.
- Canonicalized OpenMind KB/EventBus path resolution helpers used by router init and health reporting.
- Made Feishu webhook verification fail-closed:
  - empty secret no longer disables verification,
  - invalid timestamp no longer passes,
  - challenge handshake also requires valid signature/timestamp.
- Restricted `repair.*` job submission behind ops-token authorization, with explicit error contracts and tests.
- Allowed ops token on `/v1/jobs*` routes at middleware level so the repair restriction is actually usable when API and ops tokens are separate.

Related commit:
- `ffde84a` `fix: harden advisor and repair control plane`

### 4. Additional regressions uncovered by full pytest

- Fixed ChatGPT debug artifact root resolution so env-provided driver roots win over stale repo-local artifacts.
- Adjusted advisor intent scoring so `调研 + 分析` without an explicit deliverable noun still routes to research instead of report writing.
- Re-aligned routing config drift: `report_writing.min_tier` back to flagship-only (`1`).
- Scoped pause-queue tests to disable the new repair ops-token requirement, because those tests are about pause semantics, not auth.

Related commit:
- `db10b35` `fix: stabilize executor wait loops and routing config`

## Verification

Targeted regressions run during implementation:

- `./.venv/bin/pytest -q tests/test_gemini_drive_attach_urls.py tests/test_gemini_followup_wait_guard.py tests/test_gemini_generate_image_kind.py tests/test_gemini_wait_conversation_url_upgrade.py tests/test_gemini_wait_conversation_hint.py tests/test_gemini_needs_followup_on_prompt_box.py`
- `./.venv/bin/pytest -q tests/test_feishu_async.py tests/test_feishu_webhook_security.py tests/test_phase3_integration.py tests/test_routes_advisor_v3_security.py`
- `./.venv/bin/pytest -q tests/test_repair_check.py tests/test_client_name_allowlist.py tests/test_repair_kind_ops_auth.py tests/test_ops_endpoints.py`
- `./.venv/bin/pytest -q tests/test_advisor_graph.py tests/test_answer_now_writing_code_stuck.py tests/test_pause_queue.py tests/test_routing_fabric.py::TestConfigLoading::test_task_profile_parsed`
- `./.venv/bin/pytest -q tests/test_gemini_deep_research_gdoc_fallback.py tests/test_gemini_wait_transient_handling.py`

Full regression:

- `./.venv/bin/pytest -q`
- Result: pass
- Final rerun after `tests/test_cc_executor.py` mock cleanup: pass, no warning summary emitted.

## Issue Sweep Notes

Items fixed directly in this sweep:

- `iss_4dc2c813038f4f44bd35b8d7046f262e`
- `iss_fc0d81bb3e334486b6d7b3473f71a9c6`
- `iss_0a384a56ba7a420fb3b9ce7f1799b67f`

Merged security review item partially mitigated here:

- `iss_04750fe084d44c3c97e5e659a0fa7a0d`
  - mitigated: advisor auth/rate-limit consistency, repair kind exposure, webhook fail-open
  - pre-existing `input.file_paths` containment checks were already present in `chatgptrest/api/routes_jobs.py`
  - not fully re-scoped here: every historical P1/P2 item under that umbrella
