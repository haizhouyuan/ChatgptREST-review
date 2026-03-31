# YogaS2 主机运维概况（ChatgptREST 视角）

> 本文件由 `/vol1/maint` 维护仓库同步而来，供 ChatgptREST 开发/运维参考。
> 完整运维文档位于 `/vol1/maint/`。

## 主机硬件（2026-03-02）

| 项目 | 规格 |
|------|------|
| CPU | Intel i7-8550U (4C/8T, 1.8-4.0GHz) |
| 内存 | DDR4-2400 × 2（8GB + 16GB = 24GB；计划换到 16+16=32GB） |
| 存储 | 致态 Ti600 2TB NVMe（SMART PASSED，磨损 3%） |
| OS | Debian 12 bookworm + fnOS/Trim，内核 6.12.18-trim |

## ChatgptREST 相关服务

### systemd（用户级）
```
chatgptrest-api.service      # REST API（:18711）
chatgptrest-mcp.service      # MCP adapter（:18712）
chatgptrest-driver.service   # CDP driver（内部 IPC）
chatgptrest-chrome.service   # Chrome 自动化实例
chatgptrest-viewer-watchdog.timer  # viewer 黑屏巡检
```

### ChatgptREST 在 earlyoom 自愈白名单中
当 earlyoom kill Chrome 后，`ops-memory-recovery` 会自动恢复：
- `chatgptrest-api.service`
- `chatgptrest-mcp.service`
- `chatgptrest-driver.service`
- `chatgptrest-chrome.service`

### ChatgptREST 相关监控
- `ops/maint_daemon.py` — incident 证据包、ui_canary 巡检
- `ops/monitor_chatgptrest.py` — JSONL 监控
- `ops/viewer_watchdog.py` — viewer 黑屏自愈

## 内存约束（对 ChatgptREST 的影响）

### 当前内存分布
- 系统总内存：24GB（可用约 8GB）
- 用户进程总 RSS：~18GB
- ChatgptREST + Chrome 约占 4-5GB

### 保护机制
1. **earlyoom** 优先杀 Chrome renderer（`--prefer chrome`），保护 sshd/mihomo/fail2ban
2. **cgroup** `user-1000.slice` → MemoryMax=20G / MemorySwapMax=6G
3. **zram** 8G 高优先级 swap（压缩率约 3:1）
4. **自愈** 被杀后 30s 内自动恢复 ChatgptREST 服务

### 32GB 升级后的调整建议
- cgroup MemoryMax 从 20G → 26G
- zram 从 8G → 12-16G
- vm.swappiness 从 80 → 60
- Chrome 实例不再是首要 OOM 压力源

## 网络与代理

### 代理（mihomo）
- SOCKS5: `127.0.0.1:7890`
- HTTP: `127.0.0.1:7890`
- Controller: `127.0.0.1:9090`
- ChatgptREST Chrome 启动时默认走代理

### 防火墙
- iptables INPUT 默认 DROP，已白名单放行 ChatgptREST 相关端口
- Tailscale 全放行

## Codex 双 HOME 配置

ChatgptREST 可能被以下 AI 工具调用：

| 工具 | wrapper | CODEX_HOME |
|------|---------|------------|
| codex | `~/.home-codex-official/.local/bin/codex` | `/vol1/1000/home-yuanhaizhou/.codex1` |
| codex2 | `~/.home-codex-official/.local/bin/codex2` | `/vol1/1000/home-yuanhaizhou/.codex2` |
| claude code | `~/.home-codex-official/.local/bin/claude` | 默认 HOME |
| gemini cli | `~/.home-codex-official/.local/bin/gemini` | 默认 HOME |

- 所有工具的 wrapper 都安装在 `~/.home-codex-official/.local/bin/` 下
- 活跃 Codex 运行态统一使用 `HOME=/home/yuanhaizhou`，只通过 `CODEX_HOME` 切换 `codex1` / `codex2`
- `~/.home-codex-official` 是 symlink → `/vol1/1000/home-yuanhaizhou/.home-codex-official`
- `~/.home-codex-official/.codex` 仅保留为历史目录；当前活跃双 home 为 `/vol1/1000/home-yuanhaizhou/.codex1` 与 `/vol1/1000/home-yuanhaizhou/.codex2`
- 凭证统一由 `/vol1/maint/MAIN/scripts/credctl.py` 管理

## 备份覆盖

以下路径已纳入每日 restic 备份（→ HomePC）：
- `/vol1/1000/projects`（含 ChatgptREST）
- `/etc`、`/home/yuanhaizhou`、`/vol1/maint`、`/vol1/ops`

## 关键排障路径

| 场景 | 操作 |
|------|------|
| Chrome 被 earlyoom 杀 | 等 30s 自愈，或 `ops/chrome_start.sh` |
| API 502/无响应 | `systemctl --user status chatgptrest-api` |
| 内存飙高 | `ps aux --sort=-%mem \| head -20` |
| 代理挂了 | `systemctl --user status mihomo` |
| 系统级排障 | 完整运维手册 → `/vol1/maint/docs/ops_manual.md` |
