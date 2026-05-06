# 2026-04-02 Planning Agent Dual Review Synthesis v1

## 1. 这份文档在做什么

这份文档不是再做一轮新调查，而是把两份独立审核收成一个统一裁决：

1. [Antigravity 独立审计 v2](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_knowledge_audit_independent_v2.md)
2. [ClaudeGAC 全盘 second opinion](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_claudegac_second_opinion_full_strategy_review_v1.md)

目标只有一个：

> 明确哪些判断已经被双审交叉支持，哪些口径需要改写，下一步该怎么走。

## 2. 先说总裁决

双审后的综合结论是：

> 第一阶段主线方向成立，但必须把“知识层补齐”和“任务层首次实现”明确拆开。

更具体地说：

1. `planning` 主线不该整体重构。
2. `planning` 知识主线应以补齐优先。
3. 统一逻辑任务层不能再被说成“已有基座上的补闭环”，而应被定义为“治理定义已冻结，但最小生产闭环尚未落地”。

## 3. 双审一致通过的部分

### 3.1 第一阶段主线成立

两份审核都没有反对：

1. 第一阶段先做面向 `planning/` 日常工作的长任务 agent
2. 不再继续把入口、平台、知识层、进化层同时摊大

### 3.2 四层 surface 分层成立

双审都没有推翻下面这套结构：

1. `Codex / Claude Code / Antigravity`：主工作台
2. `tmuxagent`：远程入口 + 控制面
3. public MCP + `/v3/agent/turn`：canonical northbound / orchestration 面
4. `chatgpt_web.ask / gemini_web.ask / consult`：internal provider/job lane

也就是说：

> “不要再把这些都混叫执行层” 这条收口是对的。

### 3.3 planning 知识主线成立

Antigravity 和 Claude 都支持下面这条知识主线：

`planning review plane -> reviewed runtime pack -> planning-priority context -> work memory`

区别只在于强调点不同：

1. Antigravity 更强调这条线已经生产可用，当前主要问题是自动化和活化不足。
2. Claude 更强调这条线成立，但不能据此推导出任务层也已经成熟。

### 3.4 KB / vector / graph 应降为支撑层

双审都没有支持“继续把知识平台越做越大”。

共同结论是：

1. `KB / vector / graph` 有价值
2. 但当前应作为 evidence / fallback / storage support layer
3. 不应继续压过 `planning reviewed runtime pack + work memory`

## 4. 两份审核的真正分工

### 4.1 Antigravity 在审什么

Antigravity 这份本质上是在审：

1. `planning runtime pack`
2. `EvoMap retrieval / promotion`
3. `ContextService` 集成
4. `WorkMemoryManager`
5. knowledge DB / bundle / review cycle 的健康度

所以它得出的“补齐优先，不重构”是：

> 对知识架构层成立

而不是对整套 planning agent 所有层都成立。

### 4.2 Claude 在审什么

Claude 这份审的是更大的范围：

1. 目标主线
2. surface 分层
3. 统一逻辑任务层
4. `publicagentmcp` 收口
5. knowledge 主线
6. 任务层与质量治理的节奏

所以它补出来的关键批评是：

> 不能把知识层的“补齐优先”泛化到任务层

## 5. 需要立即改写的口径

### 5.1 要收回的说法

下面这类说法现在不该继续用：

1. “统一逻辑任务层已有基座，只要补闭环”
2. “整个 planning agent 当前都更像补齐，不像首次实现”

原因很明确：

1. `task_runtime` 是 `core=False`
2. 零生产 caller
3. `checkpoint()` 只在测试里被调用
4. `new / continue / branch` 还只是治理定义

### 5.2 应替换成的说法

现在更准确的口径应该是：

1. `知识层`
   - 已有真实效果
   - 当前以补齐为主
   - 重点补 `freshness / promotion / acceptance / writeback`
2. `任务层`
   - 治理定义已经冻结
   - 但最小生产闭环尚未落地
   - 下一步是首次实现一个最小端到端切片

## 6. Antigravity 强化了哪些判断

Antigravity 这份对我们最有价值的强化有 4 点：

### A. runtime pack search 不是假能力

它明确纠正了早期误判：

1. `search_planning_runtime_pack()` 不走 `_ensure_rescored()`
2. 它直接用自己的 bundle + sqlite 查询路径
3. 当前 7 组 golden query 都能返回命中

所以：

> pack search 这条线不能再被说成“不健康”或“空壳”。

### B. `_ensure_rescored()` 不是当前热路径 blocker

它证明了：

1. 当前 zero-quality 比例仅 6.8%
2. 远低于 50% 触发阈值
3. pack search 本身又不走这条路径

所以：

> 这一点现在不该再作为主问题反复讨论。

### C. 真正的知识层问题是自动化缺失

Antigravity 的重点不是“架构坏了”，而是：

1. pack 已 22 天未刷新
2. 99.3% atoms 还在 `staged`
3. 缺 systemd timer / cron / 自动 promotion 管线

所以：

> 知识层的核心问题是自动化和活化不足，而不是结构错了。

### D. EvoMap retrieve 之所以空，不是因为坏了

它解释清楚了：

1. `USER_HOT_PATH` 只允许 `active`
2. 当前绝大多数 atoms 仍是 `staged`

所以：

> 热路径 0 hits 不是 bug，更像是 active 池太小。

## 7. Claude 强化了哪些判断

Claude 这份最值钱的强化有 4 点：

### A. task_runtime 不能再被当成现实基座

这点是最重要的纠偏。

### B. checkpoint 是承重件，而不是可后补的小功能

它提醒得很对：

1. 没有 checkpoint 写回
2. 没有 checkpoint 恢复
3. 没有 new/continue/branch 执行逻辑

就不能说统一逻辑任务层已经进入补齐阶段。

### C. Feishu 入口的成熟度可能被说轻了

这点对下一步入口策略有直接影响。

### D. `publicagentmcp` 必须选定位

这也是后面收口时绕不过去的一步：

1. 是 `ask wrapper`
2. 还是 `orchestration facade`

不选，这个面就会继续漂。

## 8. 现在真正的综合口径

如果把两份审核收成一句最准确的话，我建议冻结成：

> `planning` 第一阶段的正确路线，不是整体重构，也不是笼统“全都补齐”；而是把已经验证有效的知识主线继续补自动化和活化，同时把尚未真正落地的统一逻辑任务层作为一条独立的首次实现工作线推进。

## 9. 综合 Next 3

### 1. 先跑通统一逻辑任务层的最小切片

最小切片至少应包含：

1. 从一个真实 surface 发起 planning 任务
2. 分配 `task_id`
3. 推进一轮
4. 写入 checkpoint
5. 从另一个 surface 恢复
6. 继续任务

这件事是任务层，不是知识层。

### 2. 并行补知识层自动化

这件事是知识层，优先补：

1. runtime pack freshness
2. active atom promotion
3. bootstrap allowlist 扩面

### 3. 明确 publicagentmcp 定位

必须做出选择：

1. `ask wrapper`
2. `orchestration facade`

选完之后，`consult`、`repo_bootstrap`、`repo_doc_obligations` 的处理边界才会稳。

## 10. 一句话结论

双审后的最终结论不是“你之前都说错了”，而是：

> 主线方向是对的，但过去把“知识层已有真实效果”和“任务层尚未真正落地”混成了一个口径；现在必须把这两件事拆开，后续才能稳扎稳打。
