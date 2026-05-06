# 2026-03-09 OpenClaw OpenMind Review Hardening Round 16

## Trigger

While the refreshed public branch was under external review, the live ChatGPT Pro reasoning trace moved from topology and gateway checks into `skills-src/chatgptrest-call`. The likely next blocker was portability:

- the skill wrapper hardcoded `/vol1/1000/projects/ChatgptREST`
- the interval state file also hardcoded the same host-specific path
- `SKILL.md` examples and install notes were written like a single-machine local convention instead of a public package

## Changes

- updated `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
  - default ChatgptREST root now comes from the script location
  - `CHATGPTREST_ROOT` can override the default
  - default interval state file now lives under the discovered repo root
  - `CHATGPTREST_CALL_INTERVAL_STATE_FILE` can override the interval state path
  - Python execution now prefers repo-local `.venv/bin/python`, then falls back to the current interpreter
- updated `skills-src/chatgptrest-call/SKILL.md`
  - examples now use repo-relative commands
  - install notes describe the active Codex home generically
  - added explicit note that copied-out skill installs should set `CHATGPTREST_ROOT`
- added regression coverage in `tests/test_skill_chatgptrest_call.py`
  - default root derives from the repository under test
  - interval state path derives from the repository under test
  - `_python_bin()` falls back to the current interpreter when no repo-local `.venv` exists
- refreshed the topology review bundle so public reviewers can see the skill portability fix in the bundle itself

## Validation

```bash
./.venv/bin/pytest -q tests/test_skill_chatgptrest_call.py tests/test_codex_cold_client_smoke.py tests/test_cli_improvements.py
./.venv/bin/python -m py_compile skills-src/chatgptrest-call/scripts/chatgptrest_call.py
```

## Outcome

The public `chatgptrest-call` skill no longer assumes the author machine path as its only valid runtime. This closes the most obvious portability gap that an external reviewer could flag after the topology/package/gateway fixes from round 15.
