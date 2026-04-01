# 2026-03-16 Runtime API Dashboard Parity Fix v1

## 背景

`8787` 的 dedicated dashboard 已经切到主仓最新控制面语义，但 `18711` 这条 runtime worktree 仍然运行旧版 API 代码，导致：

- `/v2/dashboard/api/command-center` 直接 `404`
- `/v1/ops/status` 仍把原始状态计数和旧 stuck-wait SQL 当成当前真相
- `/v2/telemetry/ingest` 不接受 closeout 使用的 flat event envelope

这会让人类和 agent 从两个入口读到两套不同的系统状态。

## 修复策略

不重写 runtime worktree 的 dashboard service 本体，只补低风险兼容层：

1. `routes_cognitive.py`
   - 接受 flat telemetry event envelope
   - 兼容 `event_type` / `session_id`
2. `routes_ops.py`
   - 引入 `backlog_health` 与 `queue_health`
   - 区分 `jobs_by_status`、`raw_jobs_by_status`、`stale_jobs_by_status`
   - `stuck_wait_jobs` 只统计真实 leased / expired lease 的 wait job
3. `routes_dashboard.py`
   - 增加 `/v2/dashboard/api/command-center`
   - 增加 `/v2/dashboard/api/evomap`
   - 页面路径增加 `/command-center`、`/evomap` redirect alias

## 新增文件

- `chatgptrest/core/backlog_health.py`
- `chatgptrest/ops_shared/queue_health.py`

## 验证

- `python3 -m py_compile chatgptrest/api/routes_cognitive.py chatgptrest/api/routes_ops.py chatgptrest/api/routes_dashboard.py chatgptrest/api/schemas.py chatgptrest/core/backlog_health.py chatgptrest/ops_shared/queue_health.py tests/test_cognitive_api.py tests/test_ops_endpoints.py tests/test_dashboard_routes.py`
- `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_cognitive_api.py tests/test_ops_endpoints.py tests/test_dashboard_routes.py -k 'telemetry_ingest_accepts_flat_closeout_event_envelope or separates_stale_backlog_from_true_stuck_wait or command_center_and_evomap_aliases or ops_status_surfaces_issue_family_wait_and_ui_canary_attention'`

## 结果

目标是让 runtime API 至少在三件关键事上和 dedicated dashboard 对齐：

- closeout telemetry 不再被 `422`
- ops status 不再把 queued/backoff wait 误算成 stuck
- `command-center` / `evomap` API 路径在 runtime 入口上可用
