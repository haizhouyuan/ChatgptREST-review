# 2026-03-16 Runtime Dashboard Proxy Alignment v1

## 问题

runtime worktree 上新增的 `/v2/dashboard/api/command-center` 和 `/v2/dashboard/api/evomap`
虽然不再 `404`，但仍然回的是本地旧 `DashboardService` 快照。

结果是：

- `18711` 的 agent 入口看到的是旧读模型
- `8787` 的 dedicated dashboard 才是人类看到的新控制面
- 同一系统仍有两套 dashboard truth

## 修复

在 `chatgptrest/api/routes_dashboard.py` 增加低风险代理层：

- 默认把 `command-center` / `evomap` alias 代理到 `http://127.0.0.1:8787/dashboard/api/*`
- 若 dedicated dashboard 不可达或返回非法 JSON，再 fallback 到本地 `service.overview_snapshot()` / `service.cognitive_snapshot()`

环境变量：

- `CHATGPTREST_DEDICATED_DASHBOARD_BASE_URL`

## 验证

- `python3 -m py_compile chatgptrest/api/routes_dashboard.py tests/test_dashboard_routes.py`
- `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_dashboard_routes.py -k 'command_center_and_evomap_aliases or aliases_prefer_dedicated_dashboard_proxy'`
