# 2026-04-02 OpenClawBot Meeting Intake Smoke Test Spec Walkthrough v1

## 本次做了什么

1. 回到 `Step 0`，没有直接写实施方案
2. 先重新核了 `OpenClawBot` Feishu channel 的媒体处理代码
3. 再核了 `openmind-advisor` bridge 的 payload 组装代码
4. 把 `Step 0` 从一个模糊的“大一统 smoke”拆成了三个层次：
   - `Smoke A`: Feishu intake transport
   - `Smoke B`: bridge payload
   - `Smoke C`: optional natural-chain

## 为什么要这样拆

因为当前代码现实已经显示出一个明确结构错位：

1. Feishu channel 上游产出的是 `MediaPaths / MediaUrls / MediaTypes`
2. `openmind-advisor` bridge 下游消费的是 `context.files / context.attachments`

如果不把 transport smoke 和 bridge smoke 分开，一旦失败，就无法判断到底是：

1. 文件没被接住
2. 文件接住了但没投影
3. bridge 组 body 失败
4. agent 根本没调对工具

## 本次最关键的新判断

这次比之前更清楚的一点是：

> `Step 0` 的核心不是“看看 Feishu 能不能发任务”，而是“把会议材料链里的 object shape 断点先找出来”。

当前最值得怀疑的断点是：

1. `MediaPaths -> context.files/attachments` 没有明确投影层
2. `openmind-advisor` 期望的 runtime identity 也还没有被证明真的能拿到

## 为什么这份 spec 先不做成实施方案

因为现在还不适合直接写：

1. `task_id`
2. `checkpoint`
3. `continue/resume`

这些都属于 phase-1 任务层。

但 `Step 0` 还是链路核验，不应和任务层 implementation 混在一起。

## 这版 spec 的作用

它的作用只有两个：

1. 给后续真实 smoke 一个清晰边界
2. 避免后面再把 `OpenClawBot -> canonical task plane` 说成已经存在的链路

## 下一步

下一步不是继续补文档，而是：

1. 用这份 spec 跑一轮 `claudegac` 红队
2. 看它是否认为我又把某些 paper design 说成 running code
3. 如果红队没有推翻结构拆分，再决定是否需要 `v2`
