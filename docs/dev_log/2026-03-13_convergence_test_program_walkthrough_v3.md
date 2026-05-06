# Convergence Test Program Walkthrough

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Worktree: `/vol1/1000/projects/ChatgptREST/.worktrees/convergence-validation-program-20260313`  
Status: complete

This walkthrough records the first implementation tranche that turns the
convergence validation program into executable repository changes.

---

## Why This Revision Exists

The earlier branch revisions established the design:

- `plan_v2` and `plan_v3`
- `matrix_v1` and `matrix_v2`
- the doc-only TODO and walkthrough chain

What was still missing was real repository implementation.

This revision closes that gap by landing the first concrete test-program
artifacts:

- shared deterministic fixtures
- probe-semantic regression coverage
- proxy-safe `cc-control` auth coverage
- a dependency-loss business-flow regression

---

## Independent Engineering Judgments Applied

I did not treat the earlier review docs as authority. I re-checked the current
branch and made the following implementation judgments:

1. `make_router` is high blast radius because it sits under `create_app`, so
   probe changes must stay narrowly scoped.
2. `cc-control` should not trust raw `request.client.host`; it should reuse the
   existing CIDR-aware `get_client_ip()` helper.
3. The highest-value deterministic gap in the current repo is probe honesty:
   `livez`, `healthz`, and `readyz` need distinct semantics that tests can
   demonstrate.
4. The business-flow regression worth adding first is a dependency-loss path
   that proves Feishu ingress sends a retryable failure reply rather than
   failing silently.

---

## Files Added Or Changed

### New Test Infrastructure

- `tests/convergence_fixtures.py`
- `tests/test_convergence_fixture_infra.py`

### Updated Test Harness

- `tests/conftest.py`

### Updated Regression Suites

- `tests/test_ops_endpoints.py`
- `tests/test_routes_advisor_v3_security.py`
- `tests/test_feishu_ws_gateway.py`

### Production Changes

- `chatgptrest/api/app.py`
- `chatgptrest/api/routes_jobs.py`
- `chatgptrest/api/routes_advisor_v3.py`

### Process Record

- `docs/dev_log/2026-03-13_convergence_test_program_todo_v3.md`
- `docs/dev_log/2026-03-13_convergence_test_program_walkthrough_v3.md`

---

## What Landed

### 1. Shared Convergence Fixtures

Added deterministic test helpers for the exact fixture types the plan called
for:

- `MockLLMConnector`
- `InMemoryAdvisorClient`
- `FeishuGatewaySimulator`
- `MemoryManagerFixture`

These are now wired into `tests/conftest.py` as reusable fixtures so later
business-flow and fault-injection tests do not have to hand-roll transport or
memory scaffolding.

### 2. Probe Semantics Hardened

Added `/livez` and made it globally bearer-exempt alongside `/healthz` and
`/readyz`.

The resulting semantics are now explicitly test-backed:

- `/livez` means process is alive
- `/healthz` means DB path is healthy enough for a simple query
- `/readyz` means DB plus driver dependencies are actually ready

This is intentionally stricter than “everything returns 200” but still does not
claim to solve the broader fail-open startup problem for optional modules.

### 3. `cc-control` Proxy Bypass Closed

`_require_cc_control_access()` now uses the existing trusted-proxy-aware
`get_client_ip()` helper instead of raw socket peer IP.

New tests prove both sides:

- true loopback control traffic still works
- a forwarded non-loopback client behind a trusted proxy is rejected

### 4. Dependency-Loss Business-Flow Regression

The Feishu WS gateway now has deterministic regression coverage for advisor API
dependency loss. The test asserts that the gateway:

- still sends the immediate ack
- records the advisor call payload
- returns a retryable user-facing failure message instead of silently dropping
  the request

This is the first concrete business-flow simulation from the plan to become a
real executable test.

---

## Validation Performed

### Static Check

Executed:

```bash
python3 -m py_compile chatgptrest/api/app.py chatgptrest/api/routes_advisor_v3.py
```

Result:

- passed

### Focused Execution-Tranche Regression

Executed:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_convergence_fixture_infra.py \
  tests/test_ops_endpoints.py \
  tests/test_routes_advisor_v3_security.py \
  tests/test_feishu_ws_gateway.py
```

Result:

- passed

### Expanded Curated Regression

Executed:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_convergence_fixture_infra.py \
  tests/test_ops_endpoints.py \
  tests/test_routes_advisor_v3_security.py \
  tests/test_feishu_ws_gateway.py \
  tests/test_client_ip.py \
  tests/test_api_startup_smoke.py \
  tests/test_contract_v1.py \
  tests/test_advisor_api.py \
  tests/test_advisor_orchestrate_api.py \
  tests/test_advisor_runs_replay.py \
  tests/test_cognitive_api.py \
  tests/test_openclaw_cognitive_plugins.py
```

Result:

- passed

Observed warnings:

- upstream `lark_oapi` / `websockets` deprecation warnings only

---

## What This Revision Does Not Claim

This revision does **not** claim the full convergence program is complete.

Still open for later waves:

- restart durability and state recovery
- shadow/canary and soak execution
- broader business-flow catalog implementation
- full knowledge-authority validation
- startup fail-closed enforcement for optional but product-critical modules

The purpose of this revision was to convert the plan from doc-only into a real
implementation foothold with reusable infrastructure and high-signal
deterministic coverage.

---

## Commit Sequence For This Revision

1. `docs: add convergence execution tranche todo v3`
2. `test: add convergence fixture and probe regressions`
3. pending at time of writing: walkthrough, PR refresh, and closeout

---

## PR Handling

This revision continues to update the existing PR rather than opening a second
parallel PR for the same workstream.

Target PR:

- `https://github.com/haizhouyuan/ChatgptREST/pull/160`

Reason:

- preserves one review thread for the convergence-validation program
- keeps the document lineage and implementation lineage together
- avoids duplicate or drifting PR narratives for the same branch
