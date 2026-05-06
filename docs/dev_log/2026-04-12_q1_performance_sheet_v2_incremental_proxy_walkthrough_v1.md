---
title: Q1绩效考核表 v2 增量校准代理闭环 walkthrough
version: v1
status: completed
updated: 2026-04-12
---

# 背景

用户补充了两份下属李可的 Q1 材料，希望不要重做整张绩效表，而是通过既有系统入口判断这些材料是否足以补强“团队管理 / 下属辅导 / 绩效沟通 / 组织支持”表达，并在必要时对 `Q1绩效考核表草稿_v1` 做一次窄修订。

用户明确要求：

- 不能绕开系统直接做任务
- 必须通过飞书/系统入口执行
- 如果没跑通或质量不过关，要先修系统性问题，再重放，直到闭环

# 本次采取的执行方式

采用 `assistant-first ingress proxy`：

1. 由 Codex 接收用户任务
2. 通过 `ops/run_openclawbot_feishu_proxy_turn.py` 把任务投递到稳定系统入口
3. 监控 `direct_agent_v3 -> coding_agent` 路径
4. 若运行失败或质量不过线，则先修代码再重放
5. 直到生成结果可交付，再做版本化验证文档与 closeout

# 先发现的问题

第一次尝试并未达到闭环质量，主要有两个系统性问题：

1. 本地附件提取不完整
   - 带空格的路径 `2026第一季度绩效考核表 - 李可.xlsx` 未被正确抽取为附件
   - 导致进入系统的材料并不完整

2. `turn timeout` 与 `monitor timeout` 错误耦合
   - 重材料任务被 300 秒提前杀掉
   - 并非任务逻辑失败，而是 runtime budget 设置错误

# 修复动作

## 修复 1：支持包含空格的本地附件路径

文件：

- `ops/run_openclawbot_feishu_proxy_turn.py`
- `tests/test_run_openclawbot_feishu_proxy_turn.py`

动作：

- 在 `_extract_existing_local_file_paths()` 中补充逐行完整路径识别
- 保留正则提取，同时兼容包含空格的绝对路径
- 新增测试覆盖 `2026第一季度绩效考核表 - 李可.xlsx`

提交：

- `5f2e6b12`

## 修复 2：解耦 turn timeout 与 monitor budget

文件：

- `ops/run_openclawbot_feishu_proxy_turn.py`
- `tests/test_run_openclawbot_feishu_proxy_turn.py`

动作：

- 新增 `_EXTENDED_TURN_TIMEOUT_SECONDS = 600`
- 引入 `_effective_turn_timeout_seconds(...)`
- 对 `performance_summary / performance_sheet_fill` 类任务默认延长 execution timeout
- HTTP 请求超时改为 `turn_timeout + 30`

提交：

- `9a96072f`

# 重放与成功运行

成功重放目录：

- `/vol1/1000/projects/ChatgptREST/artifacts/monitor/openclawbot_feishu_proxy_turn/20260412T074951Z`

本次重放确认：

- 4 份材料全部进入请求
- proxy run `ok = true`
- direct advisor session `status = completed`
- materialization `ok = true`
- 最终文件生成：
  - `/vol1/1000/projects/planning/个人绩效/2026Q1/输出/2026-04-12_Q1绩效考核表草稿_v2.xlsx`

同时，Feishu 端三条通知都成功发送：

- 开始通知
- 最终结果通知
- 文件已生成通知

# 质量验收方法

我没有把“文件生成”当作自动通过，而是继续做了三层验收：

1. 公式静态检查
   - `formula_check.py`
   - 结果：`total_errors = 0`

2. 全表差异检查
   - 对比 `v1` 与 `v2`
   - 结果：只有 `B8 / C8 / E8 / F8` 发生变化

3. 关键单元格与空白区检查
   - `G5:G9` 留空
   - `H5:H9` 留空
   - `J5:J10` 留空
   - 关键公式未变化

# 本次为什么算闭环

这次能算闭环，不是因为“系统回了答案”，而是因为同时满足了以下条件：

- 任务通过系统入口真实执行
- 材料完整进入系统
- 结果成功 materialize 成 xlsx 文件
- 表格变化范围符合“窄修订”要求
- 关键公式和空白评分区未被破坏
- 最终内容确实吸收了新增管理证据，而不是胡乱扩写

# 输出边界

本次完成的是：

- `Q1绩效考核表草稿_v2.xlsx`

本次没有完成的是：

- 最终打分版
- 自评分/主管评分填写
- 最终定稿版

如果用户继续推进，下一步应继续沿用同一条 `assistant-first proxy` 路径，不要回到手工直做。
