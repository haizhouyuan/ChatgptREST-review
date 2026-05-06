# 2026-03-16 UI Canary Threshold Alignment v1

## 问题

runtime worktree 上的 `ops/status` 仍然把任何 `ui_canary` provider 的 `ok=false` 直接视作失败，
没有遵守 canary 自己的 `consecutive_failures` / `threshold` 语义。

这会让 `18711` API 过早进入：

- `ui_canary_ok=false`
- `attention_reasons += ui_canary_failed`

即使 canary 还处于允许的一次性抖动窗口内。

## 修复

`chatgptrest/api/routes_ops.py`

- `ok=false` 且 `consecutive_failures >= threshold` 才算失败
- 缺失阈值信息时回退到 `threshold=1`

## 验证

- `python3 -m py_compile chatgptrest/api/routes_ops.py tests/test_ops_endpoints.py`
- `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_ops_endpoints.py -k 'ops_status_surfaces_issue_family_wait_and_ui_canary_attention or ignores_ui_canary_failures_below_threshold'`
