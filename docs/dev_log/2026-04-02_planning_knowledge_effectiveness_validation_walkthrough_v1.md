# 2026-04-02 Planning Knowledge Effectiveness Validation Walkthrough v1

## 这轮为什么要补这份 review

前一轮已经回答了：

1. 你做过哪些知识能力
2. 哪些对 `planning` 有价值

但这还不够。

真正还要回答的是：

1. 它们到底有没有达到效果
2. 不好用是因为没补齐，还是架构方向错了

所以这轮改成：

1. 跑定向 pytest
2. 跑 planning runtime pack offline validation
3. 跑 planning runtime pack readiness 检查
4. 跑 planning manifests 的 work memory import + retrieval smoke
5. 跑 live `ContextResolver.resolve()` 看真实 query 能不能打中

## 这轮最重要的收口

结论不是“都挺好”，也不是“都推倒重来”。

更准确的是：

1. `work memory` 比预期更实，已经有真实价值
2. `planning runtime pack` 架构方向对，但 freshness 和 coverage 明显不够
3. `KB / vector / graph` 是支撑层，不该继续喧宾夺主

## 最关键的现实发现

### 1. planning runtime pack 不是坏的，但已经老了

- offline validation 对 4 个 golden queries 通过
- release readiness 直接判 `freshness_ok=false`
- 当前仓里最新 pack 还是 `20260311T083052Z`

### 2. work memory 不是空架子

- `27` 条 planning seed 能分流成 `24 written + 3 manual review`
- `ContextResolver` 能把 `Active Project Map + Decision Ledger` 真组装回 prompt-safe context

### 3. 真正的问题是“热路径不够新、不够全”

我用 live resolve 验证时看到：

- `预算关键数字` 能打中 planning pack
- `shared cognition 四端 联合验收` 打不中 planning pack，直接退回普通 KB

这说明：

1. 架构不是白做
2. 但现在还不能把它当成“planning 全域可靠热路径”

## 这轮之后的判断基线

后面如果继续讨论这条知识主线，基线应该变成：

1. `work memory` 继续补齐
2. `planning runtime pack` 补 freshness 和 coverage
3. 不要把注意力重新拉回“做更大的通用 KB/vector/graph 平台”
