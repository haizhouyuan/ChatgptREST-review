# 2026-03-20 OpenClaw Runtime History And Cross-System Master Inventory Audit Walkthrough v1

## 做了什么

- 复核了此前 `OpenClaw` 识别是否误指向旧 upstream 大仓。
- 重新从本机真实运行面收证，而不是只看 git repo。
- 把 `OpenClaw repo / installed runtime / state dir` 三层身份拆开。
- 把 `2026-03-08` 到 `2026-03-20` 的运行记录按时间线收敛。
- 将本次结论与以下盘点汇总进一份主文档：
  - `memory_kb_graph_inventory_audit_v1`
  - `full_repo_inventory_audit_v1`
  - `openclaw_finagent_cross_repo_inventory_audit_v1`

## 关键证据来源

- `~/.openclaw/openclaw.json`
- `~/.openclaw/logs/config-audit.jsonl`
- `~/.openclaw/agents/*/sessions/sessions.json`
- `~/.openclaw/cron/runs/*.jsonl`
- `~/.openclaw/delivery-queue/failed/*.json`
- `~/.openclaw/media/inbound/*`
- `~/.openclaw.migration-backup-20260308T*`
- `~/.openclaw.role-session-reset-20260308T192621Z`
- `journalctl --user -u openclaw-gateway.service`

## 为什么这次结论比前一轮更可靠

- 前一轮更偏 repo inventory。
- 这次加入了用户态状态目录和 systemd 运行记录。
- 这次确认了“飞书那一版”确实跑过，并且能落到具体 session、具体 cron、具体 delivery failure、具体 gateway service。

## 最终判断

- `OpenClaw` 当前不能再被描述成“纯入口壳”。
- 你后面做架构重划时，必须把 `OpenClaw` 视为真实的 runtime substrate。
- 但认知核心和知识治理主线，仍然不该让 `OpenClaw` 主导。
