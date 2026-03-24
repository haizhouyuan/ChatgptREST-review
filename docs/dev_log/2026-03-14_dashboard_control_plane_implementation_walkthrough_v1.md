# Dashboard Control Plane Implementation Walkthrough v1

Date: 2026-03-14  
Repo: `ChatgptREST`  
Branch: `codex/dashboard-control-plane`

## Why this existed

旧版 `/v2/advisor/dashboard` 和第一版 `/v2/dashboard/*` 都还停留在“把现有表/API 拼出来”的阶段。  
这次实现按 Pro 方案收敛成：

`source systems -> adapters/indexers -> canonical lineage + identity -> materialized read models -> dashboard BFF -> web UI`

核心目标不是再做一个更大的拼接页，而是先在 ChatgptREST 内补一个真正的派生式 Dashboard Control Plane。

## What shipped

### 1. Read-side control plane

新增 `chatgptrest/dashboard/control_plane.py`，在 `state/dashboard_control_plane.sqlite3` 物化以下读模型：

- `identity_map`
- `canonical_events`
- `run_index`
- `run_timeline`
- `component_health`
- `incident_index`
- `cognitive_snapshot`

输入源覆盖：

- ChatgptREST: `jobs`, `job_events`, `advisor_runs`, `advisor_steps`, `advisor_events`, `incidents`, `client_issues`
- controller lanes: `lanes`, `lane_events`
- TeamControlPlane slice: `team_runs`, `team_role_runs`, `team_checkpoints`
- OpenMind / EvoMap: KB / memory / event bus / signals / knowledge DB
- OpenClaw runtime reports: guardian / orch / ui_canary / runtime_guard / viewer health

### 2. Unified operator surfaces

`chatgptrest/dashboard/service.py` 改为只读 `materialized read models`，不再让页面请求直接跨系统拼接原始表。

`chatgptrest/api/routes_dashboard.py` 改成按 operator 任务组织的 IA：

- `/v2/dashboard/overview`
- `/v2/dashboard/runs`
- `/v2/dashboard/runs/{root_run_id}`
- `/v2/dashboard/runtime`
- `/v2/dashboard/identity`
- `/v2/dashboard/incidents`
- `/v2/dashboard/cognitive`

兼容 alias 仍保留：

- `/v2/dashboard/tasks`
- `/v2/dashboard/openmind`
- `/v2/dashboard/openclaw`
- `/v2/dashboard/lineage`

### 3. Dedicated dashboard app on 8787

新增：

- `chatgptrest/api/app_dashboard.py`
- `ops/start_dashboard.sh`
- `ops/systemd/chatgptrest-dashboard.service`

这个 app 只承载 dashboard control plane，不跟主 `/v1` 写路径绑在同一个服务生命周期里。

### 4. UI rewrite

模板全部按新的 snapshot shape 重写：

- `overview.html`
- `runs.html`
- `run_detail.html`
- `runtime.html`
- `identity.html`
- `incidents.html`
- `cognitive.html`

目标是把“现在有什么在跑 / 卡在哪层 / 上下游是谁 / 是 job 还是 lane continuity 还是 team role/checkpoint 问题”直接放到主执行面里，而不是按系统边界分栏。

## Important fix during validation

真实数据验证时发现一个架构级错误：

- 页面请求在读模型过期后，会同步触发一次全量 materialization

这违反了“dashboard 不进 hot path”的原则。  
因此又补了一个修正：

- `maybe_bootstrap()` 只在读模型为空时做同步 bootstrap
- 读模型存在但过期时，只启动后台 refresh，不让请求线程承担跨系统归并成本

对应提交：`fix(dashboard): keep materialization off request hot path`

## Verification

### Compile

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/python -m py_compile \
  chatgptrest/dashboard/control_plane.py \
  chatgptrest/dashboard/service.py \
  chatgptrest/api/routes_dashboard.py \
  chatgptrest/api/app_dashboard.py \
  tests/test_dashboard_routes.py
```

### Tests

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_dashboard_routes.py \
  tests/test_api_startup_smoke.py
```

结果：通过。

### Live validation with real data

使用真实数据路径启动独立 dashboard app：

```bash
CHATGPTREST_DB_PATH=/vol1/1000/projects/ChatgptREST/state/jobdb.sqlite3 \
CHATGPTREST_ARTIFACTS_DIR=/vol1/1000/projects/ChatgptREST/artifacts \
CHATGPTREST_CONTROLLER_LANE_DB_PATH=/vol1/1000/projects/ChatgptREST/state/controller_lanes.sqlite3 \
CHATGPTREST_DASHBOARD_DB_PATH=/vol1/1000/projects/ChatgptREST_worktrees/dashboard-control-plane/state/dashboard_control_plane.sqlite3 \
/vol1/1000/projects/ChatgptREST/.venv/bin/python -m chatgptrest.api.app_dashboard --host 127.0.0.1 --port 8787
```

验证点：

- `GET /healthz` 返回 `ok=true`
- 真实 `root_count` materialize 到 `6393`
- `GET /v2/dashboard/overview` 返回 200
- 读模型已存在时，overview 页面实测约 `1.545s` 返回

## Ops/doc updates

已同步更新：

- `docs/runbook.md`
- `ops/systemd/chatgptrest.env.example`

新增端口与服务说明：

- dashboard operator UI: `127.0.0.1:8787`
- read model DB: `state/dashboard_control_plane.sqlite3`

## Notes

- GitNexus `detect_changes()` 在这次任务里会混入主仓库其他并行脏改动，原因是主 repo 本身处于 heavy dirty state；本次实现实际在独立 clean worktree 完成。
- 代码提交与发布应以本分支/本 worktree 的 commit 为准，而不是主仓库当前工作树状态。
