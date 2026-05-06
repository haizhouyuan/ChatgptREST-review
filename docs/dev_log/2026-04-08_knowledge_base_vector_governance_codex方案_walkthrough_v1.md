# Knowledge Base / Vector Governance Codex方案 Walkthrough V1

Date: 2026-04-08

## 本次做了什么

1. 基于 live DB、systemd timer、KB probe、runtime pack refresh summary，对当前知识系统重新做了一轮事实核验。
2. 把核验结果与 Claude 的治理方案逐条对比。
3. 输出一版收敛后的 `codex方案` 文档，明确哪些判断成立、哪些已过时、哪些需要改口。

## 为什么要再写一版

之前关于知识库/向量库的问题讨论很多，但容易把：

- 历史判断
- 当前 live 事实
- 某一条 plane 的问题
- 全链路治理问题

混在一起。

这版文档的目的，是把问题重新收敛为：

1. 已核验事实
2. 根因诊断
3. 分阶段治理路径
4. 明确验收标准

## 这次最重要的发现

1. “完全没有调度”已经不是现状，当前 planning bulk promotion 和 review maintenance 都有 live timer。
2. 但“调度存在”不等于“promotion 有效”，当前 active/candidate 仍明显过薄。
3. KB 向量能力不是完全不存在，而是运行时不一致、覆盖太薄、命中偏泛。
4. 真实根问题不是单点向量化，而是 ingestion → promotion → retrieval → feedback 全链路失配。

## 输出物

- 主文档：
  - [2026-04-08_knowledge_base_vector_governance_codex方案_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_knowledge_base_vector_governance_codex方案_v1.md)

## 后续建议

后续若真要执行这套治理，建议单独再开一轮执行计划，不直接把这份分析文档当作 task checklist 使用。
