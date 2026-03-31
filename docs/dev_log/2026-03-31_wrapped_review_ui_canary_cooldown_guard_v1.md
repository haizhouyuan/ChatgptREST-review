# 2026-03-31 Wrapped Review UI Canary Cooldown Guard Walkthrough v1

## 背景

在修完 `verification_pending` 中间态后，wrapped review lane 仍然会周期性重新进入
`verification_pending`。进一步排查 live 运行面发现，问题不只来自人工或 review wrapper，
还来自后台 `ui_canary` 对 ChatGPT driver lane 的周期性探测。

现象：

- `state/driver/chatgpt_blocked_state.json` 的 `blocked_until` 会被持续刷新。
- `journalctl --user -u chatgptrest-driver.service -u chatgptrest-ui-canary.service`
  可以看到 driver 在 canary 周期内反复触发 `CallToolRequest` 和 `GET /json/version`。
- 当 blocked state 仍处于 `verification_pending` / `verification` / `cloudflare`
  冷却期时，继续跑 `chatgpt_web_self_check` 会再次碰到 challenge 页面，导致 review 主 lane
  长时间无法恢复。

## 根因

`ops/maint_daemon.py` 的 UI canary 逻辑此前只区分：

1. `provider self_check 成功`
2. `provider self_check 失败`

它不会在进入 `self_check` 之前读取 ChatGPT 的 blocked-state。因此即使
`chatgpt_blocked_state.json` 已经明确写明当前 lane 在冷却期，UI canary 仍然会继续探测
ChatGPT provider，并在失败时继续触发 `capture_ui`，从而不断刷新 challenge 现场。

## 修复

本次修复做了两件事：

1. 在 `ops/maint_daemon.py` 新增 blocked-state 读取与 skip 判定：
   - `_load_driver_blocked_state(path)`
   - `_ui_canary_skip_for_blocked_state(provider, blocked_state, now)`
2. 当 provider=`chatgpt` 且 blocked-state 仍在冷却期时：
   - UI canary 不再调用 `self_check`
   - 也不再继续跑 `capture_ui`
   - 改为记录一个 `status=cooldown`、`error_type=ProviderBlockedState` 的 canary 结果

这样做的结果是：

- review 主 lane 的 `verification_pending` 可以自然消退，不会被后台 canary 持续刷新
- 运维面仍然能看到 provider 当前处于 degraded/cooldown，而不是“静默跳过”
- incident/evidence 仍然保留 blocked-state 快照，不丢审计链

## 测试

新增回归：

- `tests/test_maint_daemon_ui_canary.py::test_ui_canary_skip_for_chatgpt_blocked_state`
- `tests/test_maint_daemon_ui_canary.py::test_ui_canary_skip_for_blocked_state_ignores_non_chatgpt_or_expired`

这两条测试验证：

- ChatGPT blocked-state 冷却期会被 canary 转成 `cooldown / ProviderBlockedState`
- 非 ChatGPT provider 或已过期 blocked-state 不会误跳过

## 影响边界

- 这是运行治理层修复，不改变 review packet、task intake、canonical answer、work-memory 等契约。
- 修复的目标是让 wrapped review / human review / canary 共用同一 driver lane 时，后台治理不再破坏前台长任务恢复。
