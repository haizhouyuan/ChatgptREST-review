# Walkthrough: maint_daemon JSONL Cleanup Execution Plan v1

> 日期: 2026-03-25
> 范围: `artifacts/monitor/maint_daemon/maint_*.jsonl`
> 任务类型: docs-only / approval-ready execution design

## 1. 这轮做了什么

本轮没有执行 cleanup，也没有改运行时逻辑。

只做了两件事：

1. 新增正式执行方案：
   - `docs/ops/2026-03-25_maint_daemon_jsonl_cleanup_execution_plan_v1.md`
2. 在 `docs/README.md` 增加入口链接，方便 maintainer 从文档平面直接跳到该方案

## 2. 为什么要单独做这一份执行方案

前一轮 proposal 已经把 monitor 容量热点判断清楚：

- `artifacts/monitor/*` 的主要压力在 `maint_daemon`
- `maint_daemon` 的主要压力在 `maint_*.jsonl`
- 真正的大头不是 `incidents/*`
- 单纯 `>30d` 清理不会显著降压

但 proposal 还不是“可以批准执行的方案”。

这轮补的是下一层：

- 只锁定 `maint_daemon/maint_*.jsonl`
- 明确 future apply 该怎么 dry-run、怎么分层、怎么中止
- 把“不能碰什么”写成硬 guard，而不是口头提醒

## 3. 这轮用到的只读证据

本轮判断依赖的关键事实：

- `maint_*.jsonl` 共 `36` 个日包
- stat 汇总约 `101.6 GB`
- `202603` 单月约 `100.5 GB`
- 仅 `6` 个 `>2 GiB` 日包就占约 `97.9%`
- `8-14d` 窗口约 `88.2 GB`，占约 `86.8%`
- `15-30d` 窗口约 `12.3 GB`
- `31d+` 约 `1.0 GB`

这直接说明：

- 当前问题不是“太老的历史堆积”
- 而是最近一段 closed daily JSONL 爆量

## 4. 为什么方案是这个切法

这轮最终没有把 `maint_*.jsonl` 简化成“全压缩”或“全删除”，而是拆成 4 层状态：

- protected live
- hot raw
- warm compressed
- cold summary-only

原因是：

- 运行中的或刚结束的日包不能碰
- 最近少量 closed 日包仍然需要保 raw，方便直接 grep 和排障
- 中间窗口适合转成 `.jsonl.gz`
- 更老的 closed 日包既不是 canonical incident evidence，也没必要一直保 full payload

这比“按年龄一刀切”更符合当前目录里的事实分布。

## 5. 这轮明确没有做什么

- 没有删除任何 `maint_*.jsonl`
- 没有压缩任何 `maint_*.jsonl`
- 没有迁移任何 monitor 文件
- 没有碰 `maint_daemon/incidents/*`
- 没有碰 `.run/*`、`state/*`、`artifacts/jobs/*`
- 没有改 `ops/maint_daemon.py`
- 没有加 systemd / timer / janitor 自动执行

## 6. 这份方案如何被后续任务使用

后续如果要真正开始 cleanup task，推荐顺序是：

1. 先产出 dry-run evidence
2. 审批 dry-run plan
3. 再做 apply
4. apply 结束后再做结果复核

也就是说，本文件不是“现在就删”的授权，而是“未来要删时必须按这个序列做”的基线。

## 7. 一句话结论

这轮把 `maint_daemon/maint_*.jsonl` 从“已经知道是热点”推进到了“可以单独批准 future cleanup task 的执行方案”，但仍然严格停在 docs-only 边界内，没有做任何实际清理动作。
