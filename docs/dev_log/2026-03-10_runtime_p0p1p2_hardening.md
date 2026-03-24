# 2026-03-10 Runtime P0/P1/P2 Hardening

## Context

Based on a 24-hour runtime review, the main production risks were grouped into three layers:

1. `P0`: short-but-complete ChatGPT answers were being downgraded back into wait/export loops; submit-time kind gating was also drifting.
2. `P1`: Gemini deep-research wait behavior still mixed two different failure families:
   - no stable thread URL
   - stable thread URL but no progress
3. `P2`: `/v1/ops/status` could still look green while incidents, issue families, and stuck wait jobs were accumulating underneath.

## What Changed

### P0

- `chatgptrest/core/conversation_exports.py`
  - Tightened `classify_answer_quality()` so concise multi-sentence answers are no longer treated as suspect short answers.
- `chatgptrest/worker/worker.py`
  - Allowed semantically final short answers to complete under `min_chars` instead of looping forever.
- `chatgptrest/api/routes_jobs.py`
  - Added submit-time gating for disabled `qwen_web.*` kinds.
- `chatgptrest/executors/factory.py`
  - Restored direct `local_llm.ask` executor dispatch.
- `chatgptrest/advisor/qa_inspector.py`
  - Normalized QA Inspector submissions so they match the current `/v1/jobs` contract.

### P1

- `chatgptrest/worker/worker.py`
  - Added `_should_release_in_progress_web_job_to_wait()`.
  - Gemini now only leaves `send` when there is a stable Gemini thread URL.
  - Added issue-family tagging for wait timeout payloads:
    - `gemini_no_thread_url`
    - `gemini_stable_thread_no_progress`
- `chatgptrest/executors/gemini_web_mcp.py`
  - Added provider-aware wait backoff when Gemini is already in a stable thread but still `in_progress`.
  - Added `wait_state` metadata (`stable_thread_wait` vs `waiting_for_thread_url`) to make the wait family visible to worker/issue automation.

### P2

- `chatgptrest/api/routes_ops.py`
  - `/v1/ops/status` now surfaces:
    - `active_incident_families`
    - `active_open_issues`
    - `active_issue_families`
    - `stuck_wait_jobs`
    - `ui_canary_ok`
    - `ui_canary_failed_providers`
    - `attention_reasons`
- `chatgptrest/api/schemas.py`
  - Expanded `OpsStatusView` to expose the new read-only health fields.

## Tests

- `tests/test_answer_quality_completion_guard.py`
- `tests/test_min_chars_completion_guard.py`
- `tests/test_preset_required.py`
- `tests/test_qa_inspector.py`
- `tests/test_executor_factory.py`
- `tests/test_worker_and_answer.py -k 'gemini or wait_no_progress or wait_phase'`
- `tests/test_gemini_followup_wait_guard.py`
- `tests/test_ops_endpoints.py -k 'ops_status or ops_incidents'`

## Commits

- `ad68acc` `fix(runtime): harden short-answer guard and submit gating`
- `777d67b` `fix(gemini): split wait families and back off stable threads`
- `39cb931` `feat(ops): surface issue families and stuck wait health`

## Operational Notes

- `P1` and `P2` require reloading the live API / worker processes to take effect:
  - `chatgptrest-api.service`
  - `chatgptrest-worker-send.service`
  - `chatgptrest-worker-wait.service`
- The new `/v1/ops/status` fields are derived views only; they do not change the authoritative issue/incident state machines.

## Live Validation

- Services reloaded at `2026-03-10 09:06:10 CST`:
  - `chatgptrest-api.service`
  - `chatgptrest-worker-send.service`
  - `chatgptrest-worker-wait.service`
- Post-restart `/v1/ops/status` now reports family-aware health:
  - `build.git_sha=39cb931c4a04`
  - `active_incidents=62`
  - `active_incident_families=62`
  - `active_open_issues=12`
  - `active_issue_families=12`
  - `stuck_wait_jobs=1`
  - `ui_canary_ok=true`
  - `attention_reasons=["active_incidents","active_open_issues","stuck_wait_jobs"]`
- ChatGPT concise-answer smoke:
  - `job_id=9bcb9a0ae3e2430a8aaa39f2ada33298`
  - Human prompt: “请用四句话说明 issue ledger 里 mitigated 和 closed 的区别，以及为什么不能把它们混为一谈。”
  - Observed path: `send -> conversation_url_set -> phase=wait`
  - No new `completion_guard_downgraded` event was emitted during the send-stage handoff.
  - The same job later completed with `answer_chars=295`.
  - This gives live proof that the new guard avoided the earlier false-short-answer downgrade and still allowed the job to reach a real completed state.
- Gemini deep-research root smoke:
  - `job_id=fb1884078c1745fea6526266f62ee501`
  - Human prompt: “请研究机器人关节模组代工的主要供应链风险，并给出结构化结论。”
  - After reload the job stayed on `phase=send` with lease renewals before any thread evidence existed, which confirms the new code did not incorrectly requeue Gemini into `wait` before a stable thread URL existed.
  - The same root job later completed with a stable Gemini thread URL:
    - `conversation_url=https://gemini.google.com/app/cb345de426183a2c`
    - `answer_chars=651`
- Gemini same-conversation follow-up smoke:
  - `job_id=597d0b68ee094f82b3895c963e05562e`
  - Human prompt: “继续同一会话，不要复述前文，直接补充一个更深的角度：哪些风险最容易在早期样品阶段被低估，为什么？”
  - The follow-up request was created with both:
    - `parent_job_id=fb1884078c1745fea6526266f62ee501`
    - `conversation_url=https://gemini.google.com/app/cb345de426183a2c`
  - Live events then showed:
    - `conversation_url_rebound` from the parent thread URL to a new stable Gemini thread URL
    - `phase_changed {from: send, to: wait}`
  - Current rebound thread URL:
    - `conversation_url=https://gemini.google.com/app/b3038095ef1b60b0`
  - That proves the live path now preserves parent-chain, tolerates Gemini thread rebinding, and hands the follow-up into `wait` instead of failing on a stale conversation URL.
  - The same follow-up later completed with `answer_chars=17433`.
  - Final completion stored back onto the canonical Gemini conversation URL:
    - `conversation_url=https://gemini.google.com/app/cb345de426183a2c`
  - This upgrades the live proof from “handoff is correct” to “same-conversation Gemini DR follow-up survives thread rebound and still reaches a real completed state”.
