# 2026-04-03 Planning Agent 未完成部分全量实施计划 Walkthrough v2

## 为什么从 v1 改到 v2

`v1` 的方向没有错，但执行顺序和 gate 写法不够硬。

这次 `v2` 主要吸收了两类新事实：

1. 红队批评：
   - `P0` 真任务验收放太后
   - 阶段完成标准太过程化
2. 现场新事实：
   - 当前 live 阻塞已经不再只是一句旧的 `fetch failed`
   - 最新 evidence 已经推进到 `gemini_web.ask`
   - 当前真实 send-phase blocker 是 `Gemini upload menu button not found`
   - 还暴露出 `job status` 和 `session status` 不一致

## v2 具体改了什么

### 1. 把真实任务 gate 前移

不再等到最后再做 `P0` 验收，而是：

- Phase A 就绑定 `meeting_sedimentation`
- 后续每阶段至少跑一轮 phase-1 三类任务

### 2. 统一用原始验收清单做总口径

直接绑到：

- 不理解偏
- 不漏项
- 口径一致
- 可直接使用
- 可核验

不再把“边界更清楚”“结构更一致”单独拿来充当完成定义。

### 3. 把 work memory 提升到和 runtime pack 同级

`v1` 更偏 `runtime pack`。

`v2` 明确写成两条子线：

1. `work memory ingress / handoff / writeback`
2. `runtime pack freshness / promotion / acceptance`

### 4. 更新了 live 第一优先级

从抽象的“查 fetch failed”改成当前更真实的两件事：

1. `Gemini upload menu button not found`
2. `job/session/checkpoint` 状态一致性

## 当前下一步

`v2` 写完以后，后续代码工作不再扩 planning task type，先做：

1. `W1-S1`
2. `W1-S2`
3. 用 `meeting_sedimentation` 跑第一个 live green
