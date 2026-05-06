# Targeted Re-Ingest And Entity Boost Residual Risk Note V1

## 1. 当前仍然存在的边界

### 1.1 钛虎仍是桥接召回

- planning 原始文档中没有直接的 `钛虎` 材料
- 当前结果依赖 `机器人/关节模组/合作` 语义桥接
- 因此不能把当前状态表述成“钛虎实体画像可检索”

### 1.2 绿源还没到 dossier 级

- top hits 已变得明显更对，但当前仍以会议纪要、会前包、汇报框架为主
- 若要做完整实体级准备包，仍需要更精确的公司画像、历史合作纪要和 structured entity overlay

### 1.3 planning_controlled 是受控 lane，不是默认世界

- 本波通过 `planning_controlled` 把高价值原料接进 `planning explicit`
- 这不是对所有 planning raw docs 的默认开放
- `USER_HOT_PATH` 没有被放宽

## 2. 下一步建议

优先级：

1. `targeted re-ingest` 第二轮
   - 继续围绕 `绿源` 做更窄的文档补入与质检
2. `entity-aware ranking boost` 微调
   - 继续增强 title/raw_ref exact match
3. `entity bridging spike`
   - 只针对少量真实业务 ask 做 spike
   - 暂不建设通用 registry

## 3. 不建议现在做的事

- 不建议马上上通用 entity registry
- 不建议把 `planning_controlled` 逻辑泛化到所有 retrieval surface
- 不建议把这波表述成“实体知识库建设完成”

