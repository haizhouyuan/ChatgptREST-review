# 2026-03-09 Issue Knowledge / Graph Architecture Note

## 这次做了什么

把“问题知识系统”与“图检索/统一中间层”这两条线收敛成了一份正式架构草案：

- 明确先做 `data audit`
- 明确不先做 graph-first
- 把 `issue / incident / verification / usage evidence` 纳入 canonical schema
- 把 `mitigated / closed` 的自动化口径写成可实现状态机
- 把 `open issue list` 与 `history evolution` 定义成 projection，而不是手工台账

## 这次没有做什么

- 没有开始实现 graph backend
- 没有改动现有 issue ledger 状态机代码
- 没有改动 guardian sweep
- 没有改动 `docs/handoff_chatgptrest_history.md` 的生成逻辑

## 为什么先停在文档层

当前阶段最容易犯的错误是：

- 先选图库
- 先建图
- 再回头补 schema、provenance 和 close 规则

这样返工概率很高。  
所以这次先把四层边界钉死：

1. 原始层
2. 中间层
3. 图/检索投影层
4. 展示层

## 关键结论

### 1. Issue domain 不是例外，而是统一知识系统的一个试点域

它不该再以“零散文档 + ledger 表”存在。  
它应该进入统一 schema，并输出：

- open issue list
- history evolution
- graph navigation

### 2. Ledger 决定状态，Graph 不决定状态

`open / in_progress / mitigated / closed` 必须仍由 ledger authoritative。  
图层只负责：

- 关联
- 检索
- 解释
- 归档

### 3. `mitigated` 与 `closed` 的口径已经足够明确，可直接进入实现

- live verified => `mitigated`
- mitigated 后 3 次 qualifying client success 且无复发 => `closed`

### 4. open issue list 与历史演进不应继续完全手工维护

它们都应该从结构化对象投影而来。

### 5. 并行 graph 审计结果与这份架构稿一致

今天另一路 Codex graph 会话已经完成第一阶段深挖，并给出几条应直接纳入本稿的结论：

- Codex 历史会话可重建，不应只当日志
- planning 应优先于 maint 做第一试点
- planning 已有 `_kb/index/manifest.json + index.sqlite + extracted/` 这套中间层，应复用
- research 的主图源应优先从 `claims / inputs_index / EVIDENCE_MAP / CHANGELOG` 入手
- 技术路线应保持：
  - Hybrid RAG 主干
  - Property Graph 增强
  - Obsidian 作为人类界面层
  - Neo4j 倾向于长期后端
  - LlamaIndex 仅作 PoC/抽取编排

这意味着当前最正确的下一步不是“先写图库接入”，而是：

1. 统一 schema
2. 统一 provenance
3. 明确试点顺序
4. 再做 projection / pilot

## 输出文档

- 设计稿：
  - `docs/reviews/2026-03-09_issue_knowledge_graph_and_retrieval_architecture.md`

## 下一轮建议

1. 先做 source inventory
2. 再做 canonical schema v0
3. 再实现 issue domain 的首批 projection
4. 最后才进入 graph pilot
