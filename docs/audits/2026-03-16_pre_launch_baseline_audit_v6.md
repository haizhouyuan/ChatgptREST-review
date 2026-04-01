# Pre-Launch Baseline Audit v6

日期：2026-03-16
范围：ChatgptREST 核心监控服务修复验证 + monitor-12h + canary 状态修正

## 1. 修复进展

| Finding | 状态 | Commits |
|---|---|---|
| F-02: health-probe 脚本缺失 | ✅ 已修复 | `441c180`, `2f8c7b3` |
| F-02: ui-canary 脚本缺失 | ✅ 已修复 | `441c180`, `2f8c7b3` |
| 时间绑定测试碎裂 | ✅ 已修复 | `d7fe4c6` |
| chatgpt blocked state file | ⚠️ 文件已删除，canary 尚未被新 probe 刷新 | 见 §4 |
| monitor-12h.service | ⚠️ 非 blocker，但最近未完成完整 12h 窗口 | 见 §5 |

## 2. 设计原则（Codex 3 轮审核校正后）

1. **观测与行动分离**: timer 只观测+报告，`--apply` 才能 mutate，且不在 timer ExecStart 中
2. **Lease 主权**: 只有 lease 持有者决定 job 命运；health_probe 跳过 active lease
3. **Sidecar 成功 = 自身任务完成**: exit 0 = snapshot 刷新成功，provider 健康是数据不是 gate
4. **严格 HTTP Liveness**: 只有 401/403/404/405 算 alive；5xx = unhealthy

## 3. Systemd 验证结果

```
chatgptrest-health-probe.service  → status=0/SUCCESS
  7/7 PASS, --fix CANDIDATES: 0 (无 mutation)

chatgptrest-ui-canary.service     → status=0/SUCCESS
  DEGRADED (snapshot refreshed), exit 0

test_build_release_bundle         → 2 passed (was 2 failed before fix)
targeted test suite               → 64/64 passed in 63s
```

## 4. chatgpt blocked 状态（修正）

> [!WARNING]
> v5 写的"chatgpt blocked state 已清除"不够准确。

**当前实际状态**:
- `state/driver/chatgpt_blocked_state.json` 文件已于 15:24 CST 手动删除
- 但 `artifacts/monitor/ui_canary/latest.json`（08:20:09Z 快照）仍报告：
  - chatgpt: `ok=false`, `consecutive_failures=2`, `status=error`
  - 错误信息引用已过期的 blocked cooldown（2026-03-15 15:42:53）
- gemini: `ok=false`, `status=completed`, `error_type=stale`（last probe 24h+ ago）

**原因**: blocked state file 被删除后，maint_daemon 的 ui_canary probe 还没有重跑。canary sidecar 读取的是 maint_daemon 的持久 state，该 state 记录的是上次 probe 结果。只有 maint_daemon 跑一次新 probe 之后，canary 才会显示更新后的状态。

**结论**: "已清除"应改为"blocked state file 已删除，等待下次 maint_daemon ui_canary probe 刷新"。

## 5. monitor-12h.service（修正）

> [!WARNING]
> v5 将 `artifacts/monitor/periodic/monitor_12h_20260316_054251Z.jsonl` 作为"今天有产出"的证据，暗示 monitor-12h 在正常工作。这一结论不成立。

**事实**:
- 该次运行时长仅 40 秒（05:42:52Z → 05:43:32Z），**不是完整的 12h 观测窗口**
- `run_monitor_12h.sh` 调用 `monitor_chatgptrest.py --duration-seconds 43200`（12h = 43200s）
- 40s 运行 = 启动后很快退出/crash，不是正常完成
- 上次 systemd timer 触发（00:06:48 CST）以 status=1/FAILURE 结束

**性质判定**:
- monitor-12h 是长期观测 job，不与 health-probe / ui-canary 同级
- **非上线 blocker**
- 但其最近运行均未完成完整 12h 窗口，失败原因未被复核

**待办**:
- 手动短窗复跑（如 `--duration-seconds 120`）确认脚本本身无误
- 或等待下次 timer（明天 00:05）完成完整运行后确认

## 6. Codex 审核闭环

| Round | 关键发现 | 处置 |
|---|---|---|
| Round 1 | destructive fix, wrong exit codes | 重写 |
| Round 2 | 仍在 timer 中 mutate | 拆分 --fix / --apply |
| Round 3 | HTTP 5xx、exit 1 | 收紧 liveness、修正 exit code |
| Round 4 | monitor-12h 遗漏 + 证据不足 | v6 修正 3 处表述 |
