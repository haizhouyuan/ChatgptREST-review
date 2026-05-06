# 2026-03-16 Finbot Investor Dashboard Final Review Synthesis v1

## Inputs

这轮不是封闭自评，而是吸收了两类外部意见：

- 早一轮 Gemini / ChatGPT Pro review 对 multi-lane finbot 的批评
- 本轮追加的开放式 review 问题：
  - 如何把系统从“更好的 analyst notebook”提升成“真正的 investor operating system”

## Strongest External Signals

### 1. 顶部不是 Summary，而是 Epistemic Tear-Sheet

顾问意见一致认为，机会页顶部不该只是“最新研究包摘要”，而应该是一张投资人先看一眼就能决定是否继续往下读的卡：

- semantic delta
- conviction bottleneck
- kill box
- best expression
- next proving milestone

这轮实现已吸收。

### 2. History 不是 changelog，而是 action-oriented semantic diff

高质量研究历史不该是“文件更新了什么”，而应回答：

- 这次判断离行动更近还是更远
- goalpost 有没有移动
- 哪些 source 被升级 / 降级
- 哪些 claim 新增 / 退役

这轮实现已吸收。

### 3. Source 不能只看 hit-rate，必须区分 originator vs amplifier

外部意见最有价值的一点是：

- 不是所有“被引用很多次的 source”都同样有价值
- originator、corroborator、amplifier 必须分开

这轮实现已吸收，并回写到 source score 与 dashboard。

### 4. Thesis truth 与 expression tradability 必须拆开

投资人最容易被误导的一点，就是把“逻辑对不对”和“现在能不能做”混为一谈。

这轮实现里显式拆成：

- thesis truth
- expression tradability
- why not investable yet

## What Was Still Weak Before This Pass

在本轮之前，系统已经比 scout 阶段好很多，但仍有四个结构性弱点：

1. claim 虽有结构，但 citation 对象还不够稳定
2. source/KOL feedback 有写回，但页面上没有真正解释它们是什么类型的信息源
3. history 虽然有 diff，但对投资动作的语义不够直接
4. theme detail 存在 schema 漂移导致 live 500 的风险

## What This Pass Fixed

### Evidence Layer

- claim objects 补齐 falsification condition / load-bearing / evolution status
- citation objects 补齐稳定引用与质量信息
- claim -> citation edges 可在页面和 artifact 中直接追溯

### Source Layer

- source score ledger 记录长期贡献
- source detail 明确：
  - keep / downgrade decision
  - score timeline
  - information role

### History Layer

- opportunity history 变成 semantic delta + distance-to-action
- theme history 支持 evolution timeline
- thesis change summary / blocking facts / intelligence requirements 纳入 dossier

### Product Layer

- investor home 变成研究覆盖 + 最新研究更新，而不是对象堆栈
- opportunity/theme/source 三个页面之间形成可点击闭环
- live investor theme 500 已修复

## Current Assessment

当前 `finbot` 已经不再只是“会发现机会的侦察兵”，而是具备了以下投资人可消费特征：

- 可以看出当前研究推进到哪一步
- 可以看出为什么还不能投
- 可以看出最优表达为什么胜出
- 可以看出 thesis 在朝哪里变化
- 可以看出哪些 source 值得长期信任

## Still Not Final-Form

即便这轮完成后，也仍然有三件事属于下一阶段，而不是这一阶段 blocker：

1. claim -> citation 还没上真正的独立 graph/ledger backend
2. source score 现在是结构对了，但样本期还短，不能过度解读分数本身
3. expression 层仍缺正式 valuation / scenario engine

## Verdict

这轮之后，系统已经达到：

**投资人可以每天实际打开使用，并且不会被噪音页面和原始数据淹没。**

它还不是终局版顶级研究平台，但已经跨过了“只是更好看的研究笔记”这道坎。
