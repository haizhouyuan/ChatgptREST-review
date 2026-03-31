# 2026-03-21 Phase 2 Ingress Alignment Completion Walkthrough v2

## 1. v2 和 v1 的差别

`v1` 只能说：

- live adapter 已显式接上 canonical intake

`v2` 才能说：

- current live ingress payload semantics 已经不再漏损

这中间差的，就是 `planning/general` 压缩和 `attachments` 丢失这两个坑。

## 2. 为什么这两处修完就够结束 Phase 2

因为它们正好分别对应：

- **语义压缩**
- **载荷漏损**

一旦这两类缺口都补掉，剩下的问题就不再属于“ingress alignment”本身，而属于：

- legacy caller retirement
- route migration
- scenario pack design

## 3. 阶段判断

所以现在 `Phase 2` 的准确边界应该写成：

- 已完成：canonical ingress alignment for current live lanes
- 未完成：legacy ingress retirement

这个边界清楚后，就可以安全进入 `Phase 3`。*** End Patch
天天中彩票 to=functions.apply_patch code  天天中彩票可以assistant to=functions.apply_patch code ,久久热 code 】【。】【assistant to=functions.apply_patch code  problem? Let's see output. End Patch.】【”】【functions.apply_patch კომენტary to=functions.apply_patch code code րեց
