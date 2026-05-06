## Task

把 `Q1绩效考核表草稿` 做出来，但执行方式必须是：

- 用户把任务交给 Codex
- Codex 作为第一入口
- Codex 再把任务投递到系统入口
- Codex 监控链路、修系统问题、验质量
- 不允许直接绕开入口手工做表

## What Happened

前一阶段已通过 assistant-first proxy 路径完成了 `Q1工作总结梳理 v1`。本轮目标是在此基础上，继续通过同一路径生成实际的 `xlsx` 绩效考核表草稿。

初始链路并不稳定，连续暴露出多类 materialization 问题：

1. 系统回答里给出 fenced YAML 赋值块，materializer 不识别
2. 后续回答改成 fenced `text` / `A1=...` / `Row5:` 风格，materializer 仍不识别
3. 回答出现 `G5:H9` 这类矩形区间，materializer 不支持
4. parser 先吃 prose guidance，再吃真正 assignment block，导致把错的内容写进表
5. proxy prompt 合同过宽，允许模型把解释语句混进单元格赋值

这些问题说明：问题不在“模型没写内容”，而在“系统链路没有把模型输出收敛成可靠的机器写表合同”。

## Fixes

为此做了以下系统性修复：

### 1. 增加绩效表 materializer

- [materialize_performance_sheet_from_answer.py](/vol1/1000/projects/ChatgptREST/ops/materialize_performance_sheet_from_answer.py)

作用：

- 从系统 answer 中提取 cell assignment
- 基于模板 `xlsx` 生成绩效表草稿
- 保护公式区与空白评分区

### 2. 扩展 parser 能力

依次补了：

- YAML assignment 识别
- fenced `text` assignment 识别
- `RowN:` assignment 识别
- 矩形区间赋值展开
- fenced block 优先级高于 prose guidance

对应提交：

- `969bbc30`
- `63481643`
- `a29faa87`
- `a2db86fe`
- `09e87e20`

### 3. 收紧 proxy 输出合同

在 [run_openclawbot_feishu_proxy_turn.py](/vol1/1000/projects/ChatgptREST/ops/run_openclawbot_feishu_proxy_turn.py) 中，为“绩效考核表填充”类请求追加 machine-writing appendix，要求：

- 必须输出 fenced `text` block
- 每行只能是 cell/range assignment
- 不允许 explanation inline
- 公式保留必须显式写成保留模板原公式
- 留空区域必须显式写成留空

对应提交：

- `ac33cd98`

## Final Successful Run

最终成功的 proxy run 为：

- [summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/openclawbot_feishu_proxy_turn/20260412T071005Z/summary.json)

关键信号：

- `ok = true`
- `direct_turn.status = completed`
- `materialization.ok = true`
- `feishu_notices.materialized.ok = true`

最终生成文件：

- [2026-04-12_Q1绩效考核表草稿_v1.xlsx](/vol1/1000/projects/planning/个人绩效/2026Q1/输出/2026-04-12_Q1绩效考核表草稿_v1.xlsx)

## Final Quality Checks

为了避免“看起来生成成功，其实内容脏了”，本轮又加做了最终质量验收：

1. `formula_check.py --report`
   - `total_errors = 0`
2. zip/XML 直接检视关键单元格
   - 标题、周期、表头已季度化
   - 模块区文字已落表
   - `G/H/J` 保持空白
   - `I5/I9/I10/B21/B23` 公式仍在
   - 没有把说明性文字写进结构化单元格

## Result

这次真正完成的是：

- `Q1绩效考核表草稿`

这次没有做的是：

- 最终自评分
- 主管评分
- 最终提交版修辞微调

所以这是一个达标的 `draft deliverable`，不是 pretending-complete。

## Commits

本轮相关提交：

- `969bbc30` Add performance sheet materialization via proxy
- `63481643` Support YAML performance sheet assignment parsing
- `a29faa87` Support text-block performance sheet materialization
- `a2db86fe` Handle rectangular performance sheet ranges
- `ac33cd98` Tighten proxy contract for performance sheet fills
- `09e87e20` Prefer fenced performance sheet assignments over guidance

## Closeout

本轮 closeout 结论：

- user requirement respected：是
- system-path execution respected：是
- runtime issues fixed systemically：是
- final file quality inspected independently：是
- deliverable accepted：是
