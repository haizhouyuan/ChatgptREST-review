# 2026-03-17 cc-sessiond Live Rerun For Agent BI Tests v1

## Summary

`cc-sessiond` was used to run a real Claude Code validation task against the
OpenClaw/OpenMind public agent surface test claims.

This was done because the hand-written BI summary overclaimed completion and
production readiness.

## First Attempt

The first live `cc-sessiond` run failed before Claude could finish the task.

Failure:

- `ArtifactManager.append_event()` attempted to `json.dumps()` SDK message
  objects directly
- the SDK emitted a `SystemMessage`
- artifact persistence crashed with:

```text
TypeError: Object of type SystemMessage is not JSON serializable
```

Fix applied:

- `chatgptrest/kernel/cc_sessiond/artifacts.py`
- added recursive normalization for SDK message/event objects before JSON write
- added regression coverage in `tests/test_cc_sessiond.py`

Commit:

- `9272401 fix(cc-sessiond): serialize sdk events for artifacts`

## Second Attempt

After the serialization fix, the same read-only Claude Code task was rerun
through `cc-sessiond` using the official SDK backend.

Request shape:

- backend: `sdk_official`
- model: `sonnet`
- tools limited to `Bash`, `Read`, `Glob`, `Grep`
- no file edits allowed by instruction
- repo: `/vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317`

Task:

- rerun these test commands exactly:
  - `timeout 30s ./.venv/bin/pytest -q tests/test_agent_v3_routes.py`
  - `timeout 30s ./.venv/bin/pytest -q tests/test_bi09_mcp_business_pass.py`
  - `timeout 30s ./.venv/bin/pytest -q tests/test_bi14_fault_handling.py`
  - `timeout 30s ./.venv/bin/pytest -q tests/test_openclaw_cognitive_plugins.py`
- inspect:
  - `chatgptrest/api/routes_agent_v3.py`
  - `docs/dev_log/artifacts/bi_tests/BI_Test_Report.md`

## Claude Code Result

Returned session id:

- `36540522-2821-4d26-9da2-b6e760bf307f`

Cost/usage summary:

- `total_cost_usd = 0.584761`
- `input_tokens = 15976`
- `output_tokens = 1229`
- `turns = 7`

Claude Code conclusion:

- `tests/test_agent_v3_routes.py` failed
- `tests/test_bi09_mcp_business_pass.py` passed
- `tests/test_bi14_fault_handling.py` passed
- `tests/test_openclaw_cognitive_plugins.py` passed

Claude Code findings matched the local review:

- auth is not enforced right now on `/v3/agent/*`
- `BI-06` is not complete
- the BI summary/report overclaims production readiness

## Why This Matters

This run upgraded the previous validation from:

- local human review

to:

- local human review
- plus a real `cc-sessiond -> claude_code_sdk -> Claude Code` execution

So the rejection of the "all complete / production ready" claim is now backed by
both:

- direct local reproduction
- independent Claude Code rerun through `cc-sessiond`

## Artifact Location

The live rerun artifacts were written under a temporary artifact root:

- `/tmp/cc-sessiond-openclaw-bi-artifacts-meetn1l_`

## Net Result

`cc-sessiond` is now able to execute a real Claude Code validation task end to
end for this scenario.

The BI summary should still be treated as **not accepted** until:

1. `/v3/agent/*` auth is re-enabled and tested
2. `BI-06` is actually completed
3. the failing `tests/test_agent_v3_routes.py` expectations are reconciled with
   the live surface behavior
