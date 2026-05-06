---
title: Q1绩效考核表 v2 增量校准代理链路验证
version: v1
status: completed
updated: 2026-04-12
---

# 概要

本次闭环对象不是“直接人工改表”，而是通过 `assistant-first ingress proxy` 把“在既有 `Q1绩效考核表草稿_v1` 基础上，吸收李可绩效材料做增量校准”的任务投递到系统入口，再对运行链路、材料注入、生成结果与表格质量做验收。

最终结果：

- 代理链路执行成功
- `Q1绩效考核表草稿_v2.xlsx` 已真实生成
- v2 仅做 4 个目标单元格的窄修订：`B8 / C8 / E8 / F8`
- 公式区与空白评分区保持不变
- 结果已通过静态公式检查与差异边界检查

# 本次新增输入

本次增量校准相较 v1 新增两份下属管理证据：

- `/vol1/1000/projects/planning/个人绩效/2026Q1/素材/2026第一季度绩效考核表 - 李可.xlsx`
- `/vol1/1000/projects/planning/个人绩效/2026Q1/素材/绩效面谈_2026年第一季度.xlsx`

系统判断：

- `绩效面谈_2026年第一季度.xlsx` 是最高价值新增证据
  - 直接证明袁海州作为面谈人完成了季度绩效沟通、问题反馈、改进计划对齐与支持需求识别
- `2026第一季度绩效考核表 - 李可.xlsx` 为中等强度补强证据
  - 能证明存在对下属季度结果的正式评价输入
  - 但不足以单独推出“体系化团队建设成果显著”

# 本次修复的系统性根因

本次闭环不是单纯重跑，而是先修了两个真实断点：

1. `assistant-first proxy` 对包含空格的本地附件路径提取不完整
   - 根因：`ops/run_openclawbot_feishu_proxy_turn.py` 仅靠正则提取，像 `2026第一季度绩效考核表 - 李可.xlsx` 这类路径会被截断
   - 修复：补充逐行完整路径提取逻辑，支持包含空格的绝对路径
   - 提交：`5f2e6b12`

2. proxy 的 turn timeout 错误耦合到 monitor timeout
   - 根因：`/v3/agent/turn` 的 `timeout_seconds` 被错误设置为外层 monitor budget，导致材料重任务在 300s 被提前杀掉
   - 修复：将 turn timeout 与 monitor budget 解耦；对 `performance_summary / performance_sheet_fill` 类本地材料优先任务默认放宽到 `600s`
   - 提交：`9a96072f`

# 执行证据

本次成功 run：

- artifact dir:
  - `/vol1/1000/projects/ChatgptREST/artifacts/monitor/openclawbot_feishu_proxy_turn/20260412T074951Z`
- direct advisor session:
  - `agent_sess_72cf7c8ad1384d54`
- run id:
  - `c6fc32d56fb449f194831178cbe037e3`

关键证据：

- `summary.json`
  - `ok = true`
  - `direct_turn.status = completed`
  - `materialization.ok = true`
  - `materialization.output = /vol1/1000/projects/planning/个人绩效/2026Q1/输出/2026-04-12_Q1绩效考核表草稿_v2.xlsx`
- Feishu notices 全部发送成功
  - `start.ok = true`
  - `final.ok = true`
  - `materialized.ok = true`

# 结果质量验收

## 1. 文件已真实生成

最终产物：

- `/vol1/1000/projects/planning/个人绩效/2026Q1/输出/2026-04-12_Q1绩效考核表草稿_v2.xlsx`

## 2. 公式完整性通过

使用 `minimax-xlsx` 的 `formula_check.py` 对 v2 做静态检查，结果：

- `status = success`
- `total_formulas = 8`
- `total_errors = 0`

## 3. 改动范围通过“窄修订”要求

对 `v1` 与 `v2` 做全表差异比较，只有 4 个单元格发生变化：

- `B8`
- `C8`
- `E8`
- `F8`

未出现其它 KPI、权重、公式或评分区的误改。

## 4. 关键单元格检查

关键变化：

- `B8`
  - `v1 = 组织协同、资源整合与风险管控`
  - `v2 = 组织协同、团队管理与风险管控`
- `C8`
  - 新增“下属季度目标回顾与绩效沟通”
- `E8`
  - 新增“季度工作回顾完成下属绩效沟通、目标复盘和改进计划对齐”
- `F8`
  - 新增“团队管理证据更完整”“仍缺连续量化结果”的克制表述

同时确认：

- `G5:G9 = 留空`
- `H5:H9 = 留空`
- `J5:J10 = 留空`
- 公式保持：
  - `I5 = =D5*H5`
  - `I8 = =D8*H8`
  - `I10 = =SUM(I5:I9)`
  - `B21 = =I10`
  - `B23 = =B21`

# 结论

本次 `Q1绩效考核表草稿_v2` 已达到交付标准，且满足用户要求的严格边界：

- 通过系统入口完成，不是绕开入口手工做表
- 先做系统性修复，再重放同一任务
- 结果不是“能跑就算过”，而是通过了材料完整性、窄修订边界、公式完整性和关键字段正确性检查

当前正确口径：

- `v2` 是在 `v1` 基础上吸收下属管理证据后的增量修订版
- 它仍然是“绩效考核表草稿”，不是最终打分版
- 当前最合理的下一步是：如用户确认，继续通过同一 proxy 路径生成“自评版”或“定稿版”
