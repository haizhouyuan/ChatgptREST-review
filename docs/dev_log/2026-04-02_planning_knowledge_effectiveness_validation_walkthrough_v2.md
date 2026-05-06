# 2026-04-02 Planning Knowledge Effectiveness Validation Walkthrough v1

## 这轮为什么要补这份验证

前一轮已经回答了：

1. 做过哪些开发
2. 哪些看起来对 `planning` 有价值

但这还不够。

用户明确要求继续往前走一层：

> 做了并不代表效果就达到了，必须验证它到底好不好用。

所以这轮从“存在性盘点”切到了“效果验证”。

## 这轮怎么验证

我把验证拆成 4 类：

1. 定向 pytest
2. runtime pack offline validation
3. work-memory manifest import + retrieval smoke
4. live `ContextResolver` query smoke

这样能同时看到：

1. 代码逻辑是否成立
2. 真实 materials 是否能跑通
3. 运行时 query 是否真的拿到对的上下文

## 这轮最关键的新增结论

### 1. work memory 不是半成品，它已经有真实效果

这条线最接近“做出来并且能用”。

### 2. runtime pack 不是错架构，但现在只有半健康

结构对、部分 query 有效，但 freshness 和 active atom coverage 不够。

### 3. KB / vector / graph 不该继续当 planning 第一主线

它们该保留，但更适合继续当底座和 fallback 层。

## 这轮最终收口

当前最合理的口径不是：

1. “全都没用，推倒重来”
2. “都做完了，直接上”

而是：

1. 主线方向对
2. work memory 已经足够证明可继续投
3. runtime pack 应补 freshness / promotion / acceptance
4. KB / vector / graph 应降级成支撑层
