# 2026-04-02 Planning Knowledge Effectiveness Verification Walkthrough v1

## 这轮为什么要补验证版

上一轮已经把：

1. 做了哪些能力
2. 哪些对 `planning` 有价值

梳出来了。

但用户提出了一个更关键的问题：

> 做了，不代表效果真的达到了。

所以这轮不再做“存在性盘点”，而是改成：

1. 跑定向测试
2. 跑 runtime smoke
3. 看当前 live bundle / live pack / temp work-memory import 到底是不是好用

## 这轮最重要的发现

### 1. `planning runtime pack` 不是坏掉，而是“半健康”

它的结构是对的，热路径也能命中，但：

1. 当前 pack 已经过期
2. offline validation 只验证 doc/title/token，不验证真实 runtime hit
3. 某些文档虽然在 pack 里，但因为没有 active atoms，运行时仍然查不到

### 2. `work memory` 比预期更接近可用

真实 planning manifests 已经可以：

1. 导入
2. 写成 durable work-memory
3. 被 `ContextResolver` 按 `account_role` 命中
4. 回到 prompt-safe context

所以 `work memory` 的问题不是“要不要推翻”，而是“赶紧把剩下两类对象和真实 ingress 接进来”。

### 3. 真正需要补齐，不需要大重构

这轮最大的判断变化不是能力排序，而是：

1. `planning runtime pack` 需要补 runtime 验证与 freshness
2. `work memory` 需要补真实入口接线
3. `KB / vector / graph` 不该再喧宾夺主
