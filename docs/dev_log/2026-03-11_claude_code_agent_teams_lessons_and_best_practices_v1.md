---
title: Claude Code Agent Teams Lessons and Best Practices
version: v1
updated: 2026-03-11
status: completed
artifact_workspace: /vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541
---

# 目标

记录本次在 `planning` 谱系梳理任务中使用 Claude Code teams 的真实效果、失败模式、可复用方法，并对照官方文档提炼下一轮标准做法。

# 本次实际尝试了什么

## 第一轮：宽切片

初始切片：

- `slice_a_governance_system`
- `slice_b_business_lines`
- `slice_c_reducer_development`
- `slice_d_org_finance_controlled`

结果：

- `slice_a` 可用
- `slice_d` 可用
- `slice_b` 卡死
- `slice_c` 只出半成品

教训：

- “按目录大块平均切” 对 2 万级文件仓库无效
- `review_pack` 密集目录尤其不能用平均切片

## 第二轮：窄切片 + 横向抽边

改成：

- `slice_b1_business_104`
- `slice_b2_business_60`
- `slice_c1_reducer_core`
- `slice_c2_reducer_reviewpack`
- `slice_g_relation_extractor`

结果：

- `b1 / b2 / c1 / g` 都产出了可用报告
- `c2` 仍然卡住

教训：

- 缩切片显著改善成功率
- 但 `reviewpack` 这类目录仍然太大，必须进一步 metadata-first

## 第三轮：reviewpack 专项缩切片

对 `c2` 再缩成：

- 只看 family summary
- 只看 representative files
- 只关心 `README / REQUEST / SUMMARY / RESULT`

并改用受控 runner：

- `ccjob_20260311T004710Z_7548ef4b`

当前判断：

- 这是正确方向
- `reviewpack` 应该被视为 workflow topology 任务，而不是内容通读任务

# 这次什么做法有效

## 1. 先做 inventory，再发 team

有效做法：

- 先全仓做 `all_files.tsv / text_like_files.tsv / pattern_counts.json / monthly_timeline.json`
- 再按统计切 domain/team

为什么有效：

- 没有 inventory，prompt 很容易变成泛泛要求“通读”
- 有 inventory 后可以把任务收缩成“读代表文件 + family summary + 关系候选”

## 2. domain teams 和 relation extractor 分开

有效拆法：

- `domain teams`: 理解内容与历史分期
- `relation extractor`: 横向抽 `VersionFamily / ReviewPack / ModelRun / LatestOutput`
- `synthesizer`: 汇总 lineage graph 与 EvoMap 映射

为什么有效：

- 内容理解和关系抽边是两类工作
- 混在一个 agent 里，成本高且容易丢结构

## 3. 对 review_pack 必须 metadata-first

实际有效的最小单位不是全部文件，而是：

- `family_summary_json`
- `representative_files.tsv`
- `README_*.md`
- `REQUEST_*.md`
- `SUMMARY_*.md`
- `RESULT_*.md`
- 必要时加一小撮 `events.jsonl / run_meta.json` 做佐证

为什么有效：

- `review_pack` 本质是工作流容器
- 真正有价值的是“这轮为什么发起、给了什么输入、模型回了什么、融合后下一轮怎么变”

## 4. 先有 deterministic bootstrap，再让模型补洞

这轮最稳的做法不是只靠 Claude，而是并行生成：

- `bootstrap_version_edges.tsv`
- `bootstrap_latest_output_edges.tsv`
- `bootstrap_model_run_edges.tsv`

为什么有效：

- 即使某个 team 卡住，也不会导致整体没有 graph skeleton
- 模型只需要补充语义判断，不必从 0 发明所有边

## 5. 强输出契约是必要条件

成功切片都要求：

- 先写 Markdown report
- stdout 只输出严格 JSON
- JSON key 固定

为什么有效：

- 方便后续自动读取结果
- 降低“模型写了一堆散文但无法汇总”的风险

# 这次什么做法无效

## 1. wrapper 型老 runner 不可靠

早期 `ccjob_*` wrapper 只留下状态壳子，没有可靠结果文件。

结论：

- 不应再把它当主执行面
- 要么直接 `claudeminmax -p`
- 要么用有 `status/log/result` 的受控 runner

## 2. 宽切片 prompt 失败率高

失败模式：

- 范围太大
- 模型花大部分 token 在理解目录，而不是给出结论
- pre-flight 很容易挂住或低效

## 3. 让模型“平均通读” reviewpack 是错误任务定义

根因：

- `review_pack` 目录中文件数极大，但真正有意义的文件很少
- 二进制/CSV/日志远多于需要读的结论文件

# 对照官方最佳实践

本次对照了 Anthropic 官方文档：

- Common workflows  
  `https://docs.anthropic.com/en/docs/claude-code/common-workflows`
- Best practices  
  `https://docs.anthropic.com/en/docs/claude-code/best-practices`
- Sub-agents  
  `https://docs.anthropic.com/en/docs/claude-code/sub-agents`
- Tutorials  
  `https://docs.anthropic.com/en/docs/claude-code/tutorials`

## 与官方建议一致的部分

### 1. 并行拆任务是对的

官方建议把任务分给 subagents 并行处理；本次经验也证明：

- domain teams + relation extractor + synthesizer
  这种结构优于单 agent 通吃

### 2. headless / automation 模式是对的

官方建议在自动化和大规模任务时使用非交互模式；本次采用 `-p`/runner 也是正确方向。

### 3. 每个并行任务都要给足上下文

官方建议“给足上下文”；本次有效 prompt 也都包含：

- repo 根目录
- slice tsv
- family summary
- representative files
- 输出契约

### 4. 并行任务要避免文件冲突

官方教程强调平行工作宜用独立工作目录 / worktree；本次把所有 team 输出收口到 artifact workspace，没有去写 `planning` 仓库本身，这一点是对的。

## 与官方建议相比，我们这次还不够好的地方

### 1. 切片标准化还不够

官方建议是可复用的流程；本次第二轮虽然改进了切片，但 `c2` 仍然过大，说明切片 contract 还没完全产品化。

### 2. 缺少标准“工作目录隔离”模板

这次虽然用了独立 artifact workspace，但没有给每个 Claude team 建独立 worktree 或统一 run_dir 规范。

### 3. 缺少固定 team catalog

下次不该临场决定切片，而应直接有一套标准：

- domain analyst
- relation extractor
- reviewpack topology analyst
- synthesizer
- reviewer

# 下次的标准做法

## Team 角色模板

### Team-1 Domain Analyst

输入：

- slice TSV
- family summary
- 少量代表文件

输出：

- `major_eras`
- `document_families`
- `process_families`
- `evomap_recommendations`

### Team-2 Relation Extractor

输入：

- version candidates
- latest output candidates
- model run candidates
- review pack summary

输出：

- `version_edges.tsv`
- `review_edges.tsv`
- `model_run_edges.tsv`
- `latest_output_edges.tsv`

### Team-3 Reviewpack Topology Analyst

输入：

- family summary
- representative files
- `REQUEST / SUMMARY / RESULT`

输出：

- review loop topology
- trigger/freeze/escalation pattern
- experience candidates

### Team-4 Synthesizer

输入：

- Team-1/2/3 所有产物

输出：

- final lineage graph
- EvoMap mapping plan
- import strategy

### Team-5 Reviewer

输入：

- final draft

输出：

- 覆盖缺口
- 结构统一建议
- 风险提醒

## Prompt contract 标准

每个 team prompt 必须明确：

1. 禁止写主仓库
2. 允许写的 artifact 目录
3. 任务范围
4. 不要做什么
5. 必读代表文件
6. Markdown 报告路径
7. 严格 JSON 输出契约

## review_pack 专项规则

永远不要要求：

- 通读全部 review_pack 文件

永远优先：

- `README`
- `REQUEST`
- `SUMMARY`
- `RESULT`
- `MODEL_SPEC`
- 少量 run record

## 先验机械抽取规则

未来每次都先跑：

- 版本候选边
- latest output 边
- model run 边
- review pack container 边

这样模型不会被迫从零重建图结构。

# 对 EvoMap 的直接启示

1. 团队分析产生的最稳定产物不是“完整摘要”，而是：
   - family registry
   - lineage edges
   - mapping candidates
2. 这些产物很适合先进 `review_plane`
3. 真正进入 `service_candidate` 的仍然只能是：
   - 当前稳定输出
   - 冻结流程
   - 高复用 lesson/procedure/correction

# 推荐的后续动作

1. 把当前 team prompt 与输出契约沉淀成 repo 内模板
2. 给 `planning` 单独做 `reviewpack_topology` 抽取器
3. 对大仓库优先做 `inventory -> slice summary -> teams -> synthesizer`
4. 若后续常用 Claude teams，补统一 runner + status board + result parser

