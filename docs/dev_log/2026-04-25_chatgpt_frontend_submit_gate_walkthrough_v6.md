# ChatGPT Frontend Submit Gate Follow-Up v6

Date: 2026-04-25

## Context

The first submit gate blocked new `chatgpt_web.ask` jobs while the shared ChatGPT browser session was in a frontend rate-limit hold. A follow-up audit found one similar low-level path: direct `chatgpt_web.conversation_export` / `chatgpt_web.extract_answer` jobs are resolved to the ChatGPT Web executor and can call `chatgpt_web_conversation_export` without going through the ask preflight.

During a manual Pro watch window, that class of job is still unsafe because it can touch the same ChatGPT Web session and backend export API even when prompt sends are blocked.

## Change

- Extend the API submit gate from only `chatgpt_web.ask` to all `chatgpt_web.*` job kinds.
- Preserve idempotent replay semantics by allowing an existing `Idempotency-Key` to resolve to its existing job view.
- Keep the gate ChatGPT-specific; Gemini and other non-ChatGPT kinds remain unaffected.
- Add a regression test for direct `chatgpt_web.conversation_export` submission during a frontend rate-limit hold.
- Update the public contract and runbook wording from "ask" to "ChatGPT Web job".

## Validation

Targeted validation for this v6 follow-up:

```bash
PYTHONPATH=. ./.venv/bin/python -m py_compile chatgptrest/api/routes_jobs.py tests/test_chatgpt_frontend_submit_gate.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_chatgpt_frontend_submit_gate.py
```

Broader validation should include:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_jobs_write_guards.py tests/test_low_level_ask_guard.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_contract_v1.py tests/test_ask_contract.py
PYTHONPATH=. ./.venv/bin/python scripts/check_doc_obligations.py --diff HEAD
```

## Runtime Note

The live API process needs a restart to load this follow-up. The active manual Pro watch runtime already has a systemd API drop-in pointing the submit gate at:

```text
/vol1/1000/projects/ChatgptREST/state/driver/chatgpt_blocked_state.json
```
