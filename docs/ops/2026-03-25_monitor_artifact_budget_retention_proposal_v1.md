# ChatgptREST Monitor Artifact Budget / Retention Proposal v1

> 日期: 2026-03-25
> 状态: proposal
> 范围: `artifacts/monitor/*`
> 边界: docs-only / no cleanup execution / no migration / no archive action

## 1. 为什么先做这个

当前 repo maintenance 的低风险文档收口已经基本完成。

下一轮最值得做的，不是继续给旧文档贴标签，而是把 `artifacts/monitor/*` 的真实容量热点收成一份可执行 proposal，因为：

- 它是当前最主要的磁盘压力源
- 仍然可以保持 docs-only
- 它会直接决定后续 cleanup 任务的边界、优先级和 guard

## 2. 只读盘点结论

### 2.1 总量与热点

只读盘点显示：

- `artifacts/monitor/`: `128G`
- `artifacts/monitor/maint_daemon`: `120G`
- `artifacts/monitor/periodic`: `6.0G`
- `artifacts/monitor/planning_review_plane_refresh`: `1.5G`

结构结论：

- `maint_daemon` 占 `artifacts/monitor/` 的约 `93.8%`
- 当前 monitor 治理几乎等价于先治理 `maint_daemon`

### 2.2 文件量级

只读盘点显示：

- `artifacts/monitor/*` 总文件数：`221891`
- `artifacts/monitor/maint_daemon/*` 文件数：`220506`
- `maint_daemon` 文件占比约 `99.38%`

进一步看 `maint_daemon/incidents/`：

- incident 目录数：`6130`
- 二级子目录统计：
  - `snapshots`: `6130`
  - `jobs`: `5970`
  - `codex`: `1942`

结论：

- monitor 文件爆炸本质上不是“全局多点分散增长”
- 而是高度集中在 `maint_daemon` 事故包与相关产物

### 2.3 `maint_daemon` 内部结构

按大小看，`maint_daemon` 主要由两部分组成：

- `maint_*.jsonl` 日志总量：`95G`
- `incidents/`: `25G`

占比约为：

- rolling daemon JSONL：`79.2%`
- incident packs：`20.8%`

这意味着：

- 当前最大治理对象不是 incident pack
- 而是高体积的 rolling JSONL

### 2.4 时间分布

按月看 `artifacts/monitor/*` 文件数：

- `2025-12`: `738`
- `2026-01`: `2676`
- `2026-02`: `38006`
- `2026-03`: `180471`

按 `maint_daemon` 看，30 天以上文件只占：

- 文件数约 `5.37%`
- 字节量约 `0.89%`

其中：

- `maint_daemon/incidents/` 30 天以上约 `0.10G`
- `maint_daemon/maint_*.jsonl` 30 天以上约 `0.97G`

结论：

- 单纯做 `>30d` age-based cleanup，不会明显缓解当前容量压力
- 当前压力主要来自最近 30 天内的高增长 rolling telemetry

### 2.5 异常增长窗口

仅 `maint_daemon` 的单日 JSONL 就出现了明显异常大包：

- `maint_20260312.jsonl`: `16G`
- `maint_20260313.jsonl`: `26G`
- `maint_20260314.jsonl`: `37G`

仅这三天就约 `79G`。

再往前看：

- `2026-03-06` 到 `2026-03-14` 的大日包总量约 `94.3G`

这说明后续治理不能只讨论“多久删一次”，还必须引入：

- per-file size guard
- per-day growth guard
- subsystem budget guard

### 2.6 其他子树的形态

`periodic`：

- 总量：`6.0G`
- 文件数：`41`
- 结构：`24` 个 `.jsonl` + `17` 个 summary `.md`
- 多个 12h JSONL 单文件已达 `400M+`

`planning_review_plane_refresh`：

- 总量：`1.5G`
- 文件数：`125`
- 绝大多数批次只有 `2-3M`
- 但存在单个约 `1.5G` 的异常大批次

`ui_canary` / `mihomo_delay`：

- 规模都在 `5.4M`
- 它们不是当前容量主风险

## 3. 先分清对象类型

### 3.1 Tier A: Canonical incident evidence

典型路径：

- `artifacts/monitor/maint_daemon/incidents/*`
- `artifacts/monitor/incidents/*`

性质：

- incident 主键绑定证据
- 用于复盘、审计、回查
- 不应被普通 rolling janitor 直接处理

当前判断：

- 它重要，但不是当前最大容量源
- 后续治理应以保结构、保索引、保 manifest 为前提

### 3.2 Tier B: High-volume rolling telemetry

典型路径：

- `artifacts/monitor/maint_daemon/maint_*.jsonl`
- `artifacts/monitor/periodic/*.jsonl`
- `artifacts/monitor/soak*/*.jsonl`
- 顶层 `monitor_*.jsonl`
- 顶层 `chatgpt_*netlog*.jsonl*`

性质：

- 高频追加
- 大部分可再生
- 当前最主要容量源

当前判断：

- 这是未来 cleanup task 的第一治理对象

### 3.3 Tier C: Bounded rolling health signals

典型路径：

- `artifacts/monitor/ui_canary/*`
- `artifacts/monitor/mihomo_delay/*`
- `artifacts/monitor/health_probe/*`
- `artifacts/monitor/open_issue_list/*`

性质：

- 体量小
- 时间窗口型数据
- 保留最新视图比保留全部历史更重要

### 3.4 Tier D: Analytical / review bundles

典型路径：

- `artifacts/monitor/planning_review_plane_refresh/*`
- `artifacts/monitor/manual/*`
- `artifacts/monitor/reports/*`
- 其他 planning / review bundle 目录

性质：

- 不是 live canonical evidence
- 通常是某轮分析、刷新、导出产物
- 适合单独预算与人工复核

## 4. 预算提案

### 4.1 总预算

建议把 `artifacts/monitor/*` 分成两个预算层：

- 当前告警线：
  - soft: `120G`
  - hard: `140G`
- 后续清理完成后的稳态目标：
  - soft: `60G`
  - hard: `80G`

解释：

- 当前实际已经在 `128G`
- 所以从 proposal 角度看，系统已经越过 soft budget
- 后续 approved cleanup task 的目标，不应只是“略微降一点”，而应把 monitor root 拉回可持续区间

### 4.2 分层预算

| 对象 | 当前量级 | 建议 soft | 建议 hard | 说明 |
|---|---:|---:|---:|---|
| `maint_daemon/maint_*.jsonl` | `95G` | `15G` | `25G` | 当前主要失控点，应优先治理 |
| `maint_daemon/incidents/*` | `25G` | `30G` | `40G` | 保守留高一些，避免误伤 canonical evidence |
| `periodic/*` | `6.0G` | `4G` | `8G` | 12h JSONL 已明显偏大 |
| `planning_review_plane_refresh/*` | `1.5G` | `2G` | `4G` | 允许保留，但要防单次异常大包 |
| `ui_canary` + `mihomo_delay` + `soak*` + `periodic_test` | `<1G` | `1G` | `2G` | 维持小而稳定 |

## 5. 保留窗口提案

### 5.1 Tier A: Canonical incident evidence

建议窗口：

- hot: `0-30d`
- warm: `31-90d`
- archive-candidate: `>90d`

但 guard 更重要：

- 不能直接整目录 age-delete
- 必须先保留 `manifest / summary / actions / snapshots` 的完整可追溯性
- 若未来要 archive，必须先有 incident index / export 方案

### 5.2 Tier B: High-volume rolling telemetry

建议窗口：

- raw hot: `0-7d`
- compressed warm: `8-30d`
- summary-only / prune-candidate: `>30d`

额外 guard：

- 单个 `maint_YYYYMMDD.jsonl` 超过 `2G` 就应告警
- 单个 `periodic` 12h JSONL 超过 `500M` 就应告警
- 不允许再出现 `16G / 26G / 37G` 这种单日滚动文件

### 5.3 Tier C: Bounded rolling health signals

建议窗口：

- raw hot: `0-30d`
- latest + daily summary: `31-90d`
- prune-candidate: `>90d`

### 5.4 Tier D: Analytical / review bundles

建议窗口：

- hot: `0-30d`
- review-hold: `31-90d`
- archive-candidate: `>90d`

额外 guard：

- 单次批次超过 `1G` 时，必须人工说明为什么值得长期保留

## 6. Future cleanup 的硬 guard

未来真正执行 cleanup 时，必须遵守：

1. 先出 inventory / dry-run report，再谈删除
2. 不处理 `.run/*`、`state/*`、`artifacts/jobs/*`
3. 不删 same-day 文件
4. 不把 `maint_daemon/incidents/*` 当普通 rolling telemetry 处理
5. 对 rolling JSONL 的处理优先于 incident pack
6. 删除/压缩前必须保留可读 summary 或 index
7. 任何自动脚本都必须先在单独任务里经过确认

## 7. 下一步最值得做什么

如果要进入下一个批准任务，我建议顺序是：

1. 先做 `maint_daemon/maint_*.jsonl` 的 dry-run budget report
2. 再做 `periodic/*.jsonl` 的 dry-run retention simulation
3. 最后才讨论 `incidents/*` 的 archive/index 方案

而不是反过来：

- 先碰 incident pack
- 或先给小目录做“看起来整洁”的清理

## 8. 一句话结论

> `artifacts/monitor/*` 的当前容量风险，本质上是最近 30 天内失控增长的 rolling JSONL，不是老 incident pack；后续 cleanup 必须先治理 `maint_daemon/maint_*.jsonl` 与 `periodic/*.jsonl`，同时把 `incidents/*` 明确留在 canonical evidence tier。
