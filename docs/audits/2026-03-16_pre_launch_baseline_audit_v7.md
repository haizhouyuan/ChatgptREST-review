# Pre-Launch Baseline Audit v7

日期：2026-03-16
范围：ChatgptREST 核心监控服务修复 + state file path mismatch 修复

## 1. 修复进展

| Finding | 状态 | Fix |
|---|---|---|
| health-probe 脚本缺失 | ✅ 已修复 | `441c180`, `2f8c7b3` |
| ui-canary 脚本缺失 | ✅ 已修复 | `441c180`, `2f8c7b3` |
| 时间绑定测试碎裂 | ✅ 已修复 | `d7fe4c6` |
| **ui-canary 读错 state file** | ✅ 已修复 | systemd drop-in `20-runtime-worktree.conf` |
| monitor-12h 最近未完成 12h 窗口 | ⚠️ 非 blocker，待下次完整运行 | — |

## 2. 关键发现：State File Path Mismatch（Codex round-4 根因）

> [!IMPORTANT]
> 这是整个审核链中最有价值的发现。

**根因**: `maint_daemon.service` 通过 `20-runtime-worktree.conf` drop-in 将 `WorkingDirectory` 重定向到 `.worktrees/runtime-feature-memory/`，因此它的 state file 写入：

```
.worktrees/runtime-feature-memory/state/maint_daemon_state.json  (93KB, 16:33 更新)
```

而 `ui-canary.service` 的 `WorkingDirectory` 仍指向主仓，sidecar 默认读取：

```
state/maint_daemon_state.json  (47KB, Mar 15 16:14 最后更新)
```

**影响**: canary 一直在读 Mar 15 的过期 state，所以持续报告已过时的 chatgpt blocked 错误。

**修复**: 为 `chatgptrest-ui-canary.service` 添加 drop-in 配置：

```ini
# ~/.config/systemd/user/chatgptrest-ui-canary.service.d/20-runtime-worktree.conf
[Service]
Environment=CHATGPTREST_MAINT_STATE_PATH=/vol1/1000/projects/ChatgptREST/.worktrees/runtime-feature-memory/state/maint_daemon_state.json
```

**验证结果**:

```
chatgptrest-ui-canary.service → status=0/SUCCESS
  ❌ chatgpt: completed — stale: last probe was 1696s ago
  ❌ gemini: completed — stale: last probe was 1696s ago
```

chatgpt blocked 错误已消失。两个 provider 现在都显示 "stale"（上次 probe 1696s 前，超出默认 600s 阈值）。当前已不再是 blocked state，而是 stale；是否属于正常 probe cadence 仍待后续确认。

## 3. monitor-12h.service（与 v6 一致）

- 非上线 blocker
- 最近运行仅 40s（05:42:52 → 05:43:32），不是完整 12h 窗口
- 待下次 timer（明天 00:05）或手动短窗复跑确认

## 4. Systemd 最终状态

| Service | Status | 备注 |
|---|---|---|
| health-probe | ✅ `status=0/SUCCESS` | 7/7 PASS，--fix CANDIDATES: 0 |
| ui-canary | ✅ `status=0/SUCCESS` | DEGRADED（两 provider stale 但无 blocked 错误） |
| maint-daemon | ✅ `active (running)` | 运行 3h+，正常写入 worktree state |
| monitor-12h | ⚠️ 上次 exit=1 | 非 blocker，待完整窗口验证 |

## 5. Codex 审核闭环

| Round | Finding | 处置 |
|---|---|---|
| 1 | destructive fix, wrong exit codes | 重写 |
| 2 | 仍在 timer 中 mutate | 拆分 --fix / --apply |
| 3 | HTTP 5xx、exit 1 | 收紧 liveness、修正 exit code |
| 4a | monitor-12h 遗漏 + 证据不足 | v6 修正表述 |
| 4b | **state file path mismatch** | v7 修复根因 + systemd drop-in |
