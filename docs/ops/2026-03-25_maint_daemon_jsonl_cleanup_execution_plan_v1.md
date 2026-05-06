# ChatgptREST maint_daemon JSONL Cleanup Execution Plan v1

> 日期: 2026-03-25
> 状态: approval-ready execution design
> 范围: `artifacts/monitor/maint_daemon/maint_*.jsonl`
> 当前任务边界: docs-only / no cleanup execution / no runtime code change

## 1. 目标

把 `maint_daemon/maint_*.jsonl` 从“已确认的容量热点”收成一份可批准的执行方案，供后续单独 cleanup 任务按 dry-run -> approval -> apply 的方式实施。

本方案追求的不是“顺手清空 monitor”，而是：

- 在不碰 incident pack 的前提下，把 `maint_*.jsonl` 拉回预算区间
- 先定义可审计、可回滚、可中止的执行顺序
- 明确哪些动作属于正常滚动治理，哪些必须另起任务

## 2. 非目标

- 不删除 `artifacts/monitor/maint_daemon/incidents/*`
- 不处理 `artifacts/monitor/periodic/*`
- 不处理 `.run/*`、`state/*`、`artifacts/jobs/*`
- 不改 `ops/maint_daemon.py` 运行逻辑
- 不改 systemd、timer、默认端口、service wrapper
- 不在本轮执行任何压缩、迁移、归档、删除

## 3. 当前只读事实

### 3.1 当前体量

2026-03-25 只读盘点显示：

- `maint_daemon/maint_*.jsonl` 共 `36` 个日包
- stat 汇总约 `101.6 GB`（约 `94.6 GiB`）
- `du -sh` 视角约 `95G`
- `202603` 月份单月约 `100.5 GB`，占全部 `98.9%`

### 3.2 集中度

- 仅 `6` 个 `>2 GiB` 日包就占全部字节量约 `97.9%`
- 其中最大 6 个文件为：
  - `maint_20260314.jsonl`: `39.0 GB`
  - `maint_20260313.jsonl`: `27.8 GB`
  - `maint_20260312.jsonl`: `16.3 GB`
  - `maint_20260307.jsonl`: `8.8 GB`
  - `maint_20260311.jsonl`: `4.9 GB`
  - `maint_20260306.jsonl`: `2.7 GB`

### 3.3 按文件日期看窗口分布

以文件名中的 `YYYYMMDD` 为准，当前分布为：

| 窗口 | 文件数 | 体量 | 占比 |
|---|---:|---:|---:|
| `0-7d` | `1` | `4.4 MB` | `~0.00%` |
| `8-14d` | `7` | `88.2 GB` | `86.8%` |
| `15-30d` | `13` | `12.3 GB` | `12.1%` |
| `31d+` | `15` | `1.0 GB` | `1.0%` |

结论：

- 这不是“老文件拖累”，而是最近一段 closed daily JSONL 失控增长
- 单纯做 `>30d` age-based cleanup，解决不了当前压力

### 3.4 运行态事实

`ops/maint_daemon.py` 当前按 UTC 日切分：

- 当天写入路径形如 `artifacts/monitor/maint_daemon/maint_YYYYMMDD.jsonl`
- 当前仓内没有看到额外的历史日包 reopen 逻辑

但执行方案仍然必须按更保守口径设计：

- 永远不触碰 active file
- 默认连“最新两个日包”一起视为 no-touch
- 即使当前快照里最新文件不是今天，也不能把这理解成“older files 都可随意处理”

## 4. 执行边界与硬 guard

后续真正 apply 时，必须同时满足以下边界：

### 4.1 只允许处理的对象

- `artifacts/monitor/maint_daemon/maint_*.jsonl`

### 4.2 明确禁止处理的对象

- `artifacts/monitor/maint_daemon/incidents/*`
- `artifacts/monitor/incidents/*`
- `artifacts/monitor/periodic/*`
- `.run/*`
- `state/*`
- `artifacts/jobs/*`

### 4.3 明确禁止的动作

- 禁止把 `incidents/*` 当普通 rolling telemetry 清理
- 禁止在没有 dry-run 报告的情况下直接 apply
- 禁止触碰“最新两个日包”
- 禁止改 `ops/maint_daemon.py`、systemd、timer、wrapper 作为本 cleanup 的前置条件
- 禁止把这轮 cleanup 和其他 monitor 子树治理混做

### 4.4 审批规则

未来 cleanup 任务必须分成两次批准：

1. dry-run 报告批准
2. apply 执行批准

不能把“看完提案后直接删”视为同一轮动作。

## 5. 预算与成功标准

沿用已批准的 monitor retention proposal，本对象预算为：

- `maint_daemon/maint_*.jsonl`
  - soft: `15 GiB`
  - hard: `25 GiB`

额外 guard：

- 任一单日包 `>2 GiB`：进入异常增长告警
- 任一单日包 `>5 GiB`：进入 overflow 审批视图

执行成功标准分两层：

### 5.1 最低成功线

- apply 后 `maint_daemon/maint_*.jsonl + *.jsonl.gz` 合计 `<=25 GiB`
- `incidents/*` 未被触碰
- 最新两个日包仍保持原样

### 5.2 稳态目标

- apply 后 `maint_daemon/maint_*.jsonl + *.jsonl.gz` 合计 `<=15 GiB`
- 日常排障仍能直接访问最近若干天原始 JSONL
- 较老 closed 日包保留 manifest / summary，可回查是否需要额外证据

## 6. 目标状态设计

本方案把 `maint_*.jsonl` 分成 4 层状态。

### 6.1 State A: Protected live window

对象：

- active UTC 日包
- 最新两个日包（按文件名日期排序；若不足两个，则全部保护）

动作：

- 永远不处理

原因：

- 避免碰到 live append
- 避免误伤刚结束的运行窗口或人工补跑窗口

### 6.2 State B: Hot raw window

对象：

- 除 protected window 外，最近 `3` 个 closed 日包

动作：

- 保持原始 `.jsonl`

原因：

- 给排障和 grep 保留一个短而稳定的原始窗口
- 让“最近一周怎么坏的”仍然可直接查

### 6.3 State C: Warm compressed window

对象：

- 再往前的 closed 日包，默认覆盖到 `14d`

动作：

- 把 `maint_YYYYMMDD.jsonl` 压成同目录下的 `maint_YYYYMMDD.jsonl.gz`
- 写入每日日志 manifest
- 校验成功后删除对应 raw `.jsonl`

要求：

- 必须记录 `source_bytes`、`compressed_bytes`、`sha256`、`line_count`
- 必须先验证 gzip 可读，再删 raw

### 6.4 State D: Cold summary-only window

对象：

- `>14d` 的 closed 日包

动作：

- 先生成 daily summary / manifest
- 再删除 raw 或 compressed full payload

daily summary 最低必须包含：

- source file name / day
- original size
- line count
- sha256
- first / last timestamp（若可解析）
- top event types
- incident-related event counts
- error / warning 类事件计数

口径说明：

- `maint_*.jsonl` 属于 Tier B rolling telemetry，不是 canonical incident evidence
- 对 `>14d` 的 closed daily JSONL，允许进入 summary-only
- incident 相关完整证据仍由 `incidents/*` 保存

## 7. 预算驱动的执行算法

后续 apply 不应靠“拍脑袋删到看起来差不多”，而应按固定算法推进。

### 7.1 默认目标窗口

默认目标状态为：

- protected live: 最新 `2` 个日包，不动
- hot raw: 再往前 `3` 个 closed 日包，保 raw
- warm compressed: 其余 `14d` 内 closed 日包，保 `.jsonl.gz`
- cold summary-only: `>14d` closed 日包，只保 summary / manifest

### 7.2 若 dry-run 预测仍超 hard budget

如果 dry-run 根据样本压缩率预测，默认目标状态下仍会 `>25 GiB`，则继续收紧：

1. 先把 warm compressed window 从“到 `14d`”收紧为“到 `10d`”
2. 若仍超 hard，再把 `>7d` closed 日包全部转为 summary-only

### 7.3 若已经低于 hard 但仍高于 soft

允许先按 hard-recovery 方案执行，再单独批准第二轮 steady-state 优化；不要为了追 soft budget，在同一次 apply 里临时扩大删除范围。

## 8. Dry-run 必需产物

未来 cleanup 任务必须先产出一套 dry-run evidence，建议落到：

- `artifacts/monitor/reports/maint_daemon_jsonl_cleanup/<timestamp>/`

最低必需文件：

- `inventory_before.json`
- `inventory_before.md`
- `compression_sample.json`
- `dry_run_plan.json`
- `dry_run_plan.md`

### 8.1 `inventory_before` 最低字段

- file name
- file day
- size bytes
- mtime
- age by file day
- tier candidate
- protected / not protected

### 8.2 `compression_sample` 最低字段

- sampled files
- sample method
- source bytes
- compressed bytes
- observed ratio
- projected window footprint

### 8.3 `dry_run_plan` 最低字段

- current footprint
- projected footprint
- files to keep raw
- files to compress
- files to summarize-only
- files explicitly excluded
- hard budget pass/fail
- soft budget projected pass/fail

## 9. Apply 必需产物

只有 dry-run 批准后，才允许 apply。

建议 apply 产物继续落到同一时间戳目录下：

- `apply_manifest.jsonl`
- `inventory_after.json`
- `inventory_after.md`
- `final_report.json`
- `final_report.md`
- `summaries/maint_YYYYMMDD.summary.json`
- `summaries/maint_YYYYMMDD.summary.md`

`apply_manifest.jsonl` 每条至少记录：

- timestamp
- source file
- action (`compress` / `summarize_only`)
- before bytes
- after bytes
- sha256
- verification result

## 10. 执行步骤

后续真正执行时，顺序必须固定。

1. 盘点当前 `maint_*.jsonl`，生成 `inventory_before`
2. 标出 protected live window，确认不含在任何动作里
3. 做压缩样本，算出实际 ratio 与 projected footprint
4. 生成 `dry_run_plan`
5. 人工批准 dry-run plan
6. 先执行 warm compressed window
7. 校验 gzip 可读、manifest 完整、预算回落情况
8. 如 plan 包含 cold summary-only，再执行 summary 生成与 full payload 移除
9. 生成 `inventory_after` 与 `final_report`
10. 人工复核是否达到 hard / soft target

## 11. 中止与回滚条件

任一条件触发，必须立即中止，不继续向后推进：

- dry-run 无法明确识别 protected live window
- 压缩样本比预期差，预测执行后仍无法回到 hard budget
- 发现有脚本/流程强依赖 older raw `.jsonl`，但尚未准备读取 `.jsonl.gz` 或 summary
- gzip 校验失败
- manifest / summary 生成失败
- 发现目标目录在执行窗口内仍有写入

回滚原则：

- 对 warm compressed window，只有在 `.jsonl.gz` 校验通过后才允许删 raw
- 若 apply 中途失败，应保留已生成的 manifest 与失败记录，不得清空现场
- summary-only 必须先有 summary，再允许移除 full payload

## 12. 对 runbook / 运维习惯的影响

当前 runbook 与若干 dev log 仍默认引用：

- `artifacts/monitor/maint_daemon/maint_YYYYMMDD.jsonl`

因此后续真正 apply 前，需要同时准备一项轻量配套：

- 要么更新 runbook，明确 older closed files 可能变成 `.jsonl.gz`
- 要么提供一个统一 reader / helper，避免运维继续假设所有日包都必须是裸 `.jsonl`

这项配套不属于本轮文档设计的执行对象，但属于 future apply 的前置准备。

## 13. 批准口径

如果要把本方案作为后续 cleanup 任务的批准基线，建议按下面一句话理解：

> 未来只允许对 `maint_daemon/maint_*.jsonl` 做预算驱动的分层治理：最新两个日包永远不碰，最近少量 closed 日包保 raw，中间窗口转 `.jsonl.gz`，更老窗口只保 summary / manifest；任何动作都必须先有 dry-run 报告，并且不得触碰 `incidents/*`。
