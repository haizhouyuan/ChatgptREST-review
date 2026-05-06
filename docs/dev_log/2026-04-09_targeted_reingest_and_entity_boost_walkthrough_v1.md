# Targeted Re-Ingest And Entity Boost Walkthrough V1

## 做了什么

1. 重新检查了 planning 原始文档覆盖，确认：
   - `绿源` 和 `两轮车车轮市场竞争分析` 在 planning 原料中真实存在
   - `钛虎` 不在 planning 原料中
2. 给 `NoteSectionExtractor` 增加 `path_allowlist` 支持，用于受控 targeted re-ingest
3. 在 `planning explicit` retrieval 上增加 entity-aware exact-match boost
4. 新增 `ops/run_planning_targeted_reingest.py`
5. live 执行 targeted re-ingest，把高价值 planning 文档导入 `planning_controlled`
6. 重新跑 EvoMap vector backfill
7. 用三条真实 query 跑 semantic recall harness，并逐个检查 top hit 的源文档

## 为什么这样做

因为当前最大问题不是“没有向量”，而是：

- planning 原料没进 EvoMap promoted/candidate plane
- 进入后也没有被 `planning explicit` 优先理解成实体/业务强词命中

所以这波采用“先补原料、再调排序”的最小闭环，而不是直接上更重的 entity framework。

## 关键发现

- `绿源` 在 planning 原料里非常丰富，之前主要是没被定向 ingest 到合适的 lane
- `钛虎` 当前没有原料，因此只能桥接召回
- `planning_controlled` 是一个足够稳妥的受控导入口，可以在不污染 `USER_HOT_PATH` 的前提下提升 planning explicit 质量

## 验证

- focused tests: `12/12 pass`
- targeted re-ingest: `23 docs / 1833 candidate atoms`
- vectors: `4547 -> 6356`
- semantic recall harness:
  - `绿源来访准备` -> `3 hits`
  - `钛虎机器人关节模组合作` -> `4 hits`
  - `两轮车车轮市场竞争分析` -> `4 hits`

