# 2026-03-18 Advisor Synthetic Prompt Containment v1

## Context

Recent ChatGPT front-end threads with low-value prompts such as `hello`, `test blocked state`, and `test needs_followup state` were traced back to the public advisor ingress path:

- `POST /v2/advisor/ask`
- `POST /v3/agent/turn`

The root cause was that prompt policy enforcement only covered direct `/v1/jobs kind=chatgpt_web.ask` submissions. The advisor and public agent facades bypassed that guard and could still create real `chatgpt_web.ask` jobs through `ControllerEngine`.

Those synthetic source jobs were later touched again by:

- `worker_auto_codex_autofix`
- `maint_daemon` repair check / repair autofix submission

This created repeated noise on the same low-value ChatGPT threads.

## Changes

### 1. Block synthetic/trivial prompts at advisor/public ingress

Added prompt-head normalization and a dedicated ingress guard in:

- `chatgptrest/core/prompt_policy.py`

New behavior:

- strips appended `--- 附加上下文 ---` / `--- additional context ---` sections before classification
- blocks synthetic probe prompts like `test needs_followup state`
- blocks trivial prompts like `hello`, `hi`, `ping`, `test`

Guard is now enforced in:

- `chatgptrest/api/routes_advisor_v3.py`
- `chatgptrest/api/routes_agent_v3.py`

Errors returned:

- `agent_synthetic_prompt_blocked`
- `agent_trivial_prompt_blocked`

### 2. Stop repair/autofix from re-touching synthetic source jobs

Added source-job prompt classification helper in:

- `chatgptrest/core/repair_jobs.py`

Applied it in:

- `chatgptrest/worker/worker.py`
- `ops/maint_daemon.py`

New behavior:

- worker auto-autofix skips synthetic/trivial source jobs and records `auto_autofix_skipped_synthetic_source`
- maint daemon skips `repair.check` and `repair.autofix` creation for synthetic/trivial source jobs

This does not change the external contract of `create_repair_check_job()` or `create_repair_autofix_job()`.

## Tests

Executed:

```bash
./.venv/bin/pytest -q \
  tests/test_routes_agent_v3.py \
  tests/test_agent_v3_routes.py \
  tests/test_routes_advisor_v3_security.py \
  tests/test_worker_auto_autofix_submit.py \
  tests/test_maint_daemon_auto_repair_check.py
```

Additional direct probe:

```bash
OPENMIND_API_KEY=test-key OPENMIND_AUTH_MODE=strict ./.venv/bin/python - <<'PY'
from fastapi.testclient import TestClient
from chatgptrest.api.app import create_app
app = create_app()
client = TestClient(app, raise_server_exceptions=False)
...
PY
```

Observed:

- `/v3/agent/turn` with `hello` -> `400 agent_trivial_prompt_blocked`
- `/v3/agent/turn` with `test needs_followup state` -> `400 agent_synthetic_prompt_blocked`
- `/v2/advisor/ask` with `hello` -> `400 agent_trivial_prompt_blocked`

## Runtime rollout

Restarted:

- `chatgptrest-api.service`
- `chatgptrest-worker-send.service`
- `chatgptrest-worker-wait.service`
- `chatgptrest-maint-daemon.service`

## Notes

- This containment closes the main live-traffic loophole that was still creating noisy ChatGPT threads from advisor/public-agent test traffic.
- It does not retroactively remove old synthetic threads already created before the fix.
