# 2026-03-21 Task Spec Canonical Bridge Alignment Walkthrough v2

## 为什么这轮只修一半

review 提了两个点，但它们不是同一性质：

- `priority` 丢失是 bridge 的真实实现 bug
- `TaskSpec` direct construct path 还活着，是 compatibility surface 还没关死

这两件事不能混成一个结论。

如果现在为了“说法更完整”就把 direct construct path 一起砍掉，等于把兼容层治理和 bridge 修 bug 混在一轮里做，风险反而更高。

## 独立判断

这轮正确动作是：

- 修掉 `priority` 丢失
- 把阶段文档从“compatibility bridge 已完全 freeze”收紧成“live ingress freeze 已完成，compatibility surface 还在”

这样阶段判断才够准。
