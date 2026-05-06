# Convergence Test Program TODO

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Worktree: `/vol1/1000/projects/ChatgptREST/.worktrees/convergence-validation-program-20260313`  
Owner: Codex

Status: in_progress

This revision moves the convergence validation program from design-only docs
into executable repository changes.

---

## Objective

Implement the first production-backed tranche of the convergence validation
program with real code and tests.

Do not overwrite existing versions.

---

## Scope For This Revision

- [ ] add shared convergence fixture infrastructure:
  - `MockLLMConnector`
  - `InMemoryAdvisorClient`
  - `FeishuGatewaySimulator`
  - `MemoryManagerFixture`
- [ ] add deterministic probe-semantic coverage for:
  - `/livez`
  - `/healthz`
  - `/readyz`
  - probe auth exemption
- [ ] harden `cc-control` loopback auth against trusted-proxy bypass
- [ ] add black-box regression coverage for proxy-forwarded `cc-control`
- [ ] add one business-flow dependency-loss regression using the new fixture layer
- [ ] run curated validation for the changed scope
- [ ] commit each meaningful stage
- [ ] refresh PR #160 with execution-tranche results
- [ ] record walkthrough and closeout

---

## Working Notes

- `make_router` has `HIGH` upstream blast radius because it sits under
  `create_app`; keep the change surface minimal and probe-focused.
- `_require_cc_control_access` has low blast radius; preferred fix is to use
  the existing CIDR-aware `get_client_ip()` helper instead of raw
  `request.client.host`.
- New business-flow regression should prove failure semantics, not just success.

---

## Planned Deliverables

- [ ] `tests/convergence_fixtures.py`
- [ ] updated `tests/conftest.py`
- [ ] probe-semantic regression tests
- [ ] proxy-safe `cc-control` regression tests
- [ ] dependency-loss Feishu gateway regression test
- [ ] production updates in `chatgptrest/api/app.py`
- [ ] production updates in `chatgptrest/api/routes_jobs.py`
- [ ] production updates in `chatgptrest/api/routes_advisor_v3.py`
- [ ] `docs/dev_log/2026-03-13_convergence_test_program_walkthrough_v3.md`

---

## Validation Target

Recommended command set for this revision:

```bash
python3 -m py_compile chatgptrest/api/app.py chatgptrest/api/routes_advisor_v3.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_ops_endpoints.py \
  tests/test_routes_advisor_v3_security.py \
  tests/test_feishu_ws_gateway.py
```

Additional scope-expansion validation after green local tranche:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_api_startup_smoke.py \
  tests/test_contract_v1.py \
  tests/test_advisor_api.py \
  tests/test_advisor_orchestrate_api.py \
  tests/test_advisor_runs_replay.py \
  tests/test_cognitive_api.py \
  tests/test_openclaw_cognitive_plugins.py
```

---

## Commit Plan

- Commit 1: add execution-tranche TODO anchor
- Commit 2: add fixture infrastructure + tests + production hardening
- Commit 3: add walkthrough, refresh PR context, and close out
