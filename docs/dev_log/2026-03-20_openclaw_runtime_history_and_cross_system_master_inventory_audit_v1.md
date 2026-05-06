# 2026-03-20 OpenClaw Runtime History And Cross-System Master Inventory Audit v1

## 1. 目的与范围

这份文档把此前 3 轮盘点与本次补查的 `OpenClaw` 实际运行记录合并，目标是回答 4 个问题：

1. 当前系统里到底有哪些真实子系统在跑。
2. `OpenClaw` 到底指的是哪一套代码、哪一套状态、哪一套安装版运行时。
3. `2026-03-08` 到 `2026-03-20` 之间，OpenClaw 有哪些可验证的运行痕迹。
4. 这些系统之间目前最大的边界冲突和长期规划约束是什么。

本次审计对象：

- `ChatgptREST`
- `OpenMind`
- `OpenClaw`
- `Finagent`
- `~/.openclaw` 用户态状态目录
- `openclaw-gateway.service` 用户级 systemd 运行记录

不纳入本次主结论的对象：

- 早期大型 upstream 参考仓的泛化平台能力，不直接等同于本机实际运行面
- 已弃用的 `AIOS`

## 2. 关联盘点文档

本报告建立在以下盘点基础上：

- [2026-03-19_memory_kb_graph_inventory_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_memory_kb_graph_inventory_audit_v1.md)
- [2026-03-20_full_repo_inventory_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_full_repo_inventory_audit_v1.md)
- [2026-03-20_openclaw_finagent_cross_repo_inventory_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_openclaw_finagent_cross_repo_inventory_audit_v1.md)

这次新增的部分主要是：

- `OpenClaw` 运行史
- `OpenClaw repo / installed runtime / state dir` 三层身份拆分
- `飞书那一版` 的实际落点与证据

## 3. 核心结论

### 3.1 真实系统分层

当前本机真实运行的不是一个系统，而是至少 4 个相互耦合的系统：

- `ChatgptREST`：重执行、Web 代理、Advisor、KB/Memory/EvoMap 主宿主。
- `OpenMind`：认知与规划方向，当前更多以 `ChatgptREST` 内嵌实现与扩展形式存在。
- `OpenClaw`：消息入口、常驻 gateway、agent runtime、session/cron/subagent 底座。
- `Finagent`：相对独立的投研垂直应用。

### 3.2 “飞书那一版” 的准确定义

用户在飞书上真正使用过一段时间的 OpenClaw，不能仅理解成某个 git worktree。它至少包含 3 层：

1. 代码仓：
   [openclaw](/vol1/1000/projects/openclaw)

2. 用户态状态目录：
   [/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw)

3. 已安装运行时：
   `/vol1/1000/home-yuanhaizhou/.home-codex-official/.local/share/openclaw-2026.3.7/...`

也就是说，`OpenClaw repo` 和 `OpenClaw runtime` 在 `2026-03-08` 到 `2026-03-20` 之间发生过一次从 repo-source 到安装版 runtime 的迁移，但共享同一套 `.openclaw` 状态资产。

### 3.3 3 月 8 日是一个真实分界点

`2026-03-08` 不是猜测性的目录时间，而是有强证据的状态切换日：

- 当天留下 `31` 份 `.openclaw.migration-backup-20260308T*`
- 留下 1 份 `.openclaw.role-session-reset-20260308T192621Z`
- `config-audit.jsonl` 在当天记录了 OpenClaw 对 `chatgptrest-*` agents 的连续配置写入
- 飞书会话、飞书 skills、ChatgptREST bridge 都已进入用户态状态目录

### 3.4 当前最重要的架构事实

`OpenClaw` 不是“入口壳”这么简单。它已经是：

- 常驻 gateway
- session runtime
- route/binding 层
- cron 与 heartbeat 执行底座
- agent/subagent 宿主
- Feishu/DingTalk 渠道宿主

但它不是认知核心，也不是 KB/Memory/EvoMap 的唯一真相源。

## 4. 资产身份拆分

### 4.1 OpenClaw Repo

代码仓：
[openclaw](/vol1/1000/projects/openclaw)

当前仓内版本号：

- core `version = 2026.2.9` [package.json](/vol1/1000/projects/openclaw/package.json#L3)
- Feishu 插件 `version = 2026.2.9` [package.json](/vol1/1000/projects/openclaw/extensions/feishu/package.json#L3)

Feishu 插件本体明确存在于 repo：

- [extensions/feishu/package.json](/vol1/1000/projects/openclaw/extensions/feishu/package.json)
- [extensions/feishu](/vol1/1000/projects/openclaw/extensions/feishu)

### 4.2 OpenClaw Installed Runtime

当前 agent session 中实际加载的 skills 路径已经指向安装版 runtime，例如：

- `.../.local/share/openclaw-2026.3.7/node_modules/openclaw/extensions/feishu/...`

这在当前 `finbot`/`maintagent` session 台账里可见：

- [agents/finbot/sessions/sessions.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/agents/finbot/sessions/sessions.json#L8)
- [agents/maintagent/sessions/sessions.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/agents/maintagent/sessions/sessions.json#L113)

### 4.3 OpenClaw State Dir

用户态状态目录：
[.openclaw](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw)

当前运行配置中可直接确认：

- Feishu channel 开启 [openclaw.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L262)
- Feishu default account 存在 [openclaw.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L276)
- `main` route 绑定到 Feishu [openclaw.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L313)
- OpenMind 扩展从 `ChatgptREST/openclaw_extensions` 注入 [openclaw.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L238)

## 5. OpenClaw 运行史时间线

### 5.1 2026-03-08：迁移与重置窗口

最早一份迁移备份：
[manifest.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw.migration-backup-20260308T155032Z/manifest.json#L2)

证据点：

- 当天共生成 `31` 份 migration backup
- 最早备份里已经包含 `feishu-intake`、`main`、`planning`、`research-orch`、`finagent` 等 agent 状态 [manifest.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw.migration-backup-20260308T155032Z/manifest.json#L14)
- 当天同时存在角色会话重置快照：
  [/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw.role-session-reset-20260308T192621Z](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw.role-session-reset-20260308T192621Z)

### 5.2 2026-03-08：飞书会话已真实存在

`research-orch` 会话台账显示：

- `channel = feishu` [sessions.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw.role-session-reset-20260308T192621Z/research-orch/sessions/sessions.json#L9)
- `origin.provider = feishu` [sessions.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw.role-session-reset-20260308T192621Z/research-orch/sessions/sessions.json#L18)
- `from = feishu:ou_...` [sessions.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw.role-session-reset-20260308T192621Z/research-orch/sessions/sessions.json#L21)

这说明到 `2026-03-08` 晚上，飞书并不是“准备接”，而是已经留下真实 session 资产。

### 5.3 2026-03-08：ChatgptREST Bridge 接入

同一天 `config-audit.jsonl` 记录到从 `cwd=/vol1/1000/projects/ChatgptREST` 对 OpenClaw 配置的连续写入：

- `chatgptrest-orch` [config-audit.jsonl](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/logs/config-audit.jsonl#L42)
- `chatgptrest-codex-w1` [config-audit.jsonl](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/logs/config-audit.jsonl#L43)
- `chatgptrest-guardian` [config-audit.jsonl](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/logs/config-audit.jsonl#L46)

Inference：这一天 OpenClaw 已经不是孤立消息网关，而是在被用作 ChatgptREST 对接的 agent runtime。

### 5.4 2026-03-09：cron 与 delivery failure 密集出现

当前 `.openclaw` 内留存的 cron run 文件共有 4 份：

- `hragent-daily-quota-watch`
- `hragent-hourly-governance-loop`
- `finbot-theme-batch-evening`
- `d9df56ac-f486-4248-96ed-cfa366c772e7.jsonl`

时间分布：

- `2026-03-09`：`hragent-*` cron 运行落盘
- `2026-03-15`：`finbot-theme-batch-evening`

示例：

- [hragent-daily-quota-watch.jsonl](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/cron/runs/hragent-daily-quota-watch.jsonl#L1)
- [hragent-hourly-governance-loop.jsonl](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/cron/runs/hragent-hourly-governance-loop.jsonl#L1)
- [finbot-theme-batch-evening.jsonl](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/cron/runs/finbot-theme-batch-evening.jsonl#L1)

同时，delivery queue failed 目录里保留了 `15` 个失败 payload，时间集中在：

- `2026-03-09`
- `2026-03-11`

Inference：这段时间 OpenClaw 在真实承接出站通知/递送，但 delivery reliability 并不稳定。

### 5.5 2026-03-12 到 2026-03-15：入站媒体与业务侧使用

`media/inbound` 当前保留 4 个入站资产：

- `2026-03-12` 两个 PDF
- `2026-03-12` 一个 PDF
- `2026-03-15` 一个 JPG

这说明至少在这段期间，渠道入站媒体处理是真实跑过的，不是纯文本会话壳。

### 5.6 2026-03-16 到现在：gateway 服务持续运行

当前 `systemd` 状态：

- `openclaw-gateway.service`
- `Active: active (running) since Mon 2026-03-16 21:14:03 CST`
- `OpenClaw Gateway (v2026.3.7)`

近端证据：

- [main session](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/agents/main/sessions/sessions.json#L4)
- [maintagent session](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/agents/maintagent/sessions/sessions.json#L239)
- [finbot cron session](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/agents/finbot/sessions/sessions.json#L4)

## 6. 当前仍可见的运行资产

### 6.1 会话台账

当前最明确的持久 sessions：

- `main`：
  [agents/main/sessions/sessions.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/agents/main/sessions/sessions.json#L2)
- `maintagent`：
  [agents/maintagent/sessions/sessions.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/agents/maintagent/sessions/sessions.json#L240)
- `finbot`：
  [agents/finbot/sessions/sessions.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/agents/finbot/sessions/sessions.json#L2)

当前统计：

- `agents/*/sessions/*.jsonl = 39`
- `main / maintagent / finbot` 三套 sessions.json 仍在更新

### 6.2 cron

当前持久 cron runs 数量：

- `4`

关键问题：

- `2026-03-08` 的 `hragent-daily-quota-watch` 报 `Feishu account "main" not configured` [hragent-daily-quota-watch.jsonl](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/cron/runs/hragent-daily-quota-watch.jsonl#L8)
- `2026-03-15` 的 `finbot-theme-batch-evening` 报脚本在 sandbox 中不可访问，且通知未送达 [finbot-theme-batch-evening.jsonl](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/cron/runs/finbot-theme-batch-evening.jsonl#L1)

### 6.3 delivery queue

当前 `delivery-queue/failed` 内保留：

- `15` 个失败 payload

时间窗口主要在：

- `2026-03-09`
- `2026-03-11`

### 6.4 inbound media

当前 `media/inbound` 保留：

- `4` 个文件

说明渠道文件接收路径至少在 `2026-03-12` 到 `2026-03-15` 期间是活的。

## 7. 与此前盘点的合并结论

### 7.1 ChatgptREST

根据此前全库盘点，`ChatgptREST` 目前承载：

- REST job queue
- Web driver
- OpenMind v3 advisor runtime
- KB / Memory / EvoMap
- controller/team 协作栈
- dashboard / projection / issue / telemetry 等运维层

它仍然是当前全局最重的宿主仓。

### 7.2 OpenMind

OpenMind 的正确定位仍然是：

- intake / clarify / scope
- 规划、研究、知识治理
- KB / memory / graph / EvoMap 认知侧

但当前很多能力已经以内嵌扩展方式进入 ChatgptREST 与 OpenClaw，而不是独立稳定服务。

### 7.3 OpenClaw

OpenClaw 的正确定位应修正为：

- 多渠道 gateway
- 持续在线 assistant runtime
- session / heartbeat / cron / agent runtime / bindings

而不是“只有入口壳”。

### 7.4 Finagent

Finagent 仍是相对边界最清晰的垂直域系统，反而不是当前最大架构冲突源。

## 8. 当前最大的边界冲突

### 8.1 Repo / Runtime / State 三层经常被混为一谈

当前“OpenClaw”一词至少指向：

- git repo
- 安装版 runtime
- 用户态状态目录

这会直接导致盘点、修复、部署、回滚时认知错位。

### 8.2 OpenClaw 与 ChatgptREST 都长出了 orchestration 语义

冲突点包括：

- session truth
- memory / graph 回调
- runtime supervision
- agent team / orch 命名和控制权

### 8.3 运行记录分散

真正有价值的运行证据目前分散在：

- `.openclaw/*`
- `.openclaw.*backup*`
- `journalctl`
- `ChatgptREST artifacts/logs`

缺少统一可检索的“运行史视图”。

## 9. 对长期规划的约束

这份盘点对后续蓝图意味着：

1. 不能再把 OpenClaw 降格成单纯入口壳。
2. 也不能把 OpenClaw 当认知核心。
3. `OpenClaw` 与 `ChatgptREST` 之间必须明确：
   - 会话归谁
   - 任务归谁
   - 执行归谁
   - 知识归谁
4. 后续任何“重构 execution/orchestrator”方案，都必须先承认现在已有真实运行资产，而不是当成白纸重画。

## 10. 建议的下一步文档化动作

建议后续在此基础上再补 3 份专项文档：

1. `OpenClaw repo/runtime/state identity contract`
2. `OpenClaw ↔ ChatgptREST runtime boundary contract`
3. `OpenClaw operational evidence map`

如果只允许先做 1 件事，优先做第 2 件。

## 11. 审计附录

本次直接验证到的关键统计：

- migration backups: `31`
- role-session-reset dirs: `1`
- cron runs: `4`
- failed delivery payloads: `15`
- inbound media files: `4`
- persisted agent session jsonl files: `39`

本次直接读取过的关键证据路径：

- [.openclaw/openclaw.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json)
- [.openclaw/logs/config-audit.jsonl](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/logs/config-audit.jsonl)
- [.openclaw/agents/main/sessions/sessions.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/agents/main/sessions/sessions.json)
- [.openclaw/agents/maintagent/sessions/sessions.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/agents/maintagent/sessions/sessions.json)
- [.openclaw/agents/finbot/sessions/sessions.json](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/agents/finbot/sessions/sessions.json)
- [.openclaw/cron/runs](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/cron/runs)
- [.openclaw/delivery-queue/failed](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/delivery-queue/failed)
- [.openclaw/media/inbound](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/media/inbound)
- [.openclaw.migration-backup-20260308T155032Z](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw.migration-backup-20260308T155032Z)
- [.openclaw.role-session-reset-20260308T192621Z](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw.role-session-reset-20260308T192621Z)
- [openclaw/package.json](/vol1/1000/projects/openclaw/package.json)
- [openclaw/extensions/feishu/package.json](/vol1/1000/projects/openclaw/extensions/feishu/package.json)
