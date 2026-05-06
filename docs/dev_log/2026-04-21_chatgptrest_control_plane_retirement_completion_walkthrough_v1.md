# ChatgptREST control-plane retirement completion walkthrough v1

## Objective

Retire the historical planning/advisor control plane and converge ChatgptREST on its production role as:

- automation-kernel
- job queue / worker runtime
- observability / ops / dashboard

## What changed

### 1. Runtime and northbound surfaces

- `/v3/agent/*` route mounting was removed from the FastAPI app.
- mounted advisor routes (`/v1/advisor/*`, `/v2/advisor/*`) were removed.
- public/admin MCP surfaces no longer expose `advisor_agent_*` or `coding_agent_*` compatibility tools.
- CLI no longer exposes retired `advisor` / `agent` commands.

### 2. Retired control-plane code and scripts

Removed the dormant control-plane code and directly coupled tooling:

- `chatgptrest/api/routes_agent_v3.py`
- `chatgptrest/api/agent_session_store.py`
- `chatgptrest/api/agent_ingress_receipts.py`
- `chatgptrest/planning/meeting_task_store.py`
- planning checkpoint CLIs under `scripts/`
- direct `/v3/agent/*` Feishu/proxy/canary scripts under `ops/`

### 3. Eval / release-gate cleanup

Removed public-agent / planning-specific validation packs and launch gates that only exercised the retired surface, including:

- route parity / branch coverage / work-sample validators
- premium default-path and public-surface launch gates
- planning/openclaw ingress quality acceptance harnesses

The remaining production regression runner now validates the supported surface set:

- core runtime surface
- public MCP surface
- rebuilt OpenClaw stack surface

### 4. Current docs and policy contract

Updated current canonical guidance so it matches the retired runtime:

- `AGENTS.md`
- `docs/runbook.md`
- `docs/contract_v1.md`
- `CLAUDE.md`
- `GEMINI.md`
- `docs/client_projects_registry.md`
- `ops/registries/*`
- `ops/policies/*`

### 5. Dashboard / observability alignment

The shared-cognition scoreboard no longer depends on retired phase8 multi-ingress validation artifacts. It now reads the supported production regression artifact family.

## Commit chain

- `cd64264a` Keep live validation off premium ChatGPT/Gemini lanes
- `15e5c00e` runtime plane / dashboard lock / unit install stabilization
- `8abc9d44` missing snapshot session refresh hardening
- `dd669265` retire `/v3/agent/*` route mount and first planning test/eval batch
- `1c72024a` retire OpenClaw advisor-facing defaults
- `fafe1e65` retire mounted advisor APIs and health assumptions
- `584e247c` remove retired `openmind-advisor` plugin package
- `a7ba2619` remove retired public-agent release gates / validation harnesses
- `7f94bd2f` remove retired advisor/agent CLI commands
- `2bc68f94` remove retired MCP compatibility tools
- `2f2ef650` retire direct agent control-plane state and canaries
- `9e67ea4c` finish retiring public-agent evals and compat guidance

## Verification

### Focused pytest bundles

```bash
./.venv/bin/pytest -q \
  tests/test_shared_cognition_scoreboard.py \
  tests/test_agent_mcp.py \
  tests/test_mcp_server_entrypoints.py \
  tests/test_health_probe.py \
  tests/test_api_startup_smoke.py \
  tests/test_agent_control_plane_retirement.py \
  tests/test_run_openmind_production_regression.py \
  tests/test_cli_improvements.py \
  tests/test_cli_chatgptrestctl.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_install_openclaw_cognitive_plugins.py \
  tests/test_verify_openclaw_openmind_stack.py \
  tests/test_skill_chatgptrest_call_coding_agent_v1.py \
  tests/test_openclaw_adapter.py
```

### Compile / health / regression artifacts

```bash
python3 -m py_compile \
  chatgptrest/dashboard/shared_cognition_scoreboard.py \
  chatgptrest/mcp/agent_mcp.py \
  chatgptrest/core/ask_guard.py \
  ops/run_shared_cognition_status_board.py \
  ops/run_openmind_production_regression.py

python3 ops/health_probe.py --fix
python3 ops/run_openmind_production_regression.py --dry-run \
  --output-dir artifacts/monitor/openmind_production_regression/manual_dryrun_2
python3 scripts/check_doc_obligations.py --diff HEAD
```

## Resulting production posture

The supported production surface is now:

- REST `/v1/jobs*` and related backend job artifacts
- public MCP `automation-kernel-v1`
- worker/driver/dashboard/health/ops observability

The following are retired and should not be reintroduced as active surfaces:

- `/v1/advisor/*`
- `/v2/advisor/*`
- `/v3/agent/*`
- `advisor_agent_*`
- `coding_agent_*`
- planning checkpoint CLIs and related route/canary harnesses

## Remaining notes

- Historical dev-log / review / blueprint documents intentionally still mention retired surfaces for archival traceability.
- User-owned local changes outside this task remain untouched:
  - `.gitignore`
  - `ops/chrome_stop.sh`
  - `ops/systemd/chatgptrest.env.example`
  - `ops/chrome_profile_state.py`
  - `tmp/`
