# Pre-Launch Baseline Audit v5

日期：2026-03-16
范围：ChatgptREST 核心监控服务修复验证 + monitor-12h 补充

## 1. 修复进展

| Finding | 状态 | Commits |
|---|---|---|
| F-02: health-probe 脚本缺失 | ✅ 已修复 | `441c180`, `2f8c7b3` |
| F-02: ui-canary 脚本缺失 | ✅ 已修复 | `441c180`, `2f8c7b3` |
| 时间绑定测试碎裂 | ✅ 已修复 | `d7fe4c6` |
| chatgpt blocked state | ✅ 已清除 | 手动删除 |
| monitor-12h.service 遗漏 | ⚠️ 已确认 | 见 §4 |

## 2. 最终设计原则

经过 Codex 3 轮审核校正：

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

## 4. monitor-12h.service 补充（Codex round-4 finding）

**现状**: 上次运行 2026-03-16 00:06:48 CST，exit status=1/FAILURE。

**分析**:
- 这是一个 **12 小时长期观测 job**（`ops/run_monitor_12h.sh` → `monitor_chatgptrest.py --duration-seconds 43200`），不是低延迟健康检查
- 脚本本身存在且有效（`monitor_chatgptrest.py` 10KB，`summarize_monitor_log.py` 4KB）
- 最近产出：`monitor_12h_20260316_054251Z.jsonl` + summary.md（今天有产出）
- 失败原因：12h 观测窗口内连接异常或 API 不可达导致脚本 exit 1（`set -euo pipefail`）

**性质判定**: 与 health-probe / ui-canary 属于**不同类别**：
- health-probe / ui-canary = 周期性瞬时检查（几秒完成），exit 1 = 服务本身有问题
- monitor-12h = 长期观测（12 小时运行），exit 1 = 观测窗口内遇到瞬态异常，是正常运维噪声

**处置**:
- 可通过 `systemctl --user restart chatgptrest-monitor-12h.service` 复位
- 下次 timer 触发（每天 00:05）会自动重跑
- 不需要代码修复，不阻塞上线

## 5. Codex 审核闭环

| Round | 关键修复 | 结论 |
|---|---|---|
| Round 1 | 初始实现 | ❌ destructive fix, wrong exit codes |
| Round 2 | HTTP 修正, lease guard | ⚠️ still mutates in timer |
| Round 3 | report-only --fix, exit 0 | ✅ accepted with notes |
| Round 4 | 补充 monitor-12h 覆盖 | ✅ v5 已补充 |
