# 2026-04-02 ClaudeGAC Second Opinion: Full Planning Agent Strategy Review v1

## 1. 审核来源

本次 second opinion 不是手工转述，而是通过 `ccrunner + claudegac` 实际跑出的只读评审。

运行信息：

1. `run_id`: `ccjob_20260402T115140Z_c7d698da`
2. `runner`: `claudegac`
3. `workdir`: `/vol1/1000/projects/ChatgptREST`
4. `prompt_file`: `/tmp/claudegac_planning_full_second_opinion_prompt_20260402.txt`
5. `run_dir`: `/vol1/1000/home-yuanhaizhou/.claude-gac/skills/claudecode-agent-runner/runs/ccjob_20260402T115140Z_c7d698da`

关键产物：

1. [result.json](/vol1/1000/home-yuanhaizhou/.claude-gac/skills/claudecode-agent-runner/runs/ccjob_20260402T115140Z_c7d698da/result/result.json)
2. [claude_result.json](/vol1/1000/home-yuanhaizhou/.claude-gac/skills/claudecode-agent-runner/runs/ccjob_20260402T115140Z_c7d698da/result/claude_result.json)
3. [stdout.log](/vol1/1000/home-yuanhaizhou/.claude-gac/skills/claudecode-agent-runner/runs/ccjob_20260402T115140Z_c7d698da/logs/stdout.log)

## 2. Claude 的总 verdict

Claude 的总判断是：

> `同意但需收紧`

也就是：

1. 我们把主线收口到 `planning` 长任务 agent，这个大方向成立。
2. surface 分层、知识主线、KB 降级为支撑层，这些核心判断成立。
3. 但我把“知识层补齐”和“任务层实现”混成了一个统一口径，这一点需要纠正。

## 3. Claude 认为成立的部分

### 3.1 主线方向成立

Claude 明确支持：

1. 第一阶段收口到 `planning/` 日常工作长任务 agent
2. 不再同时铺开多条平台化路线
3. 优先围绕真实 planning 工作去组织主线

### 3.2 surface 分层成立

Claude 认可把系统拆成：

1. `Codex / Claude Code / Antigravity` 主工作台
2. `tmuxagent` 远程入口 + 控制面
3. public MCP + `/v3/agent/turn` canonical northbound
4. `chatgpt_web.ask / gemini_web.ask / consult` internal lane

它认为这种分层比过去把这些都混叫“执行层”明显更清楚。

### 3.3 planning 知识主线判断成立

Claude 认可：

1. `work memory` 已经有真实效果
2. `planning reviewed runtime pack` 结构成立，但当前半健康
3. `KB / vector / graph` 应降为支撑层，不应继续被当作 planning 主答案面

### 3.4 “先选工作台，不先选模型”的使用法成立

Claude 明确认可我们把：

1. 主工作台
2. 远程入口
3. canonical northbound
4. internal provider lane

区分开来，并认为这比继续以模型/ask 通道为中心更稳。

## 4. Claude 提出的高优先级问题

### H1. task_runtime 被我说成“已有基座”，这句说重了

Claude 做了代码核验，确认：

1. `task_runtime` 在 `app.py` 中是 `core=False`
2. 生产代码里没有实际 caller
3. `checkpoint()` 只在测试里被调用

所以它认为我在 [planning_unified_logical_task_layer_v1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_unified_logical_task_layer_v1.md) 里把 `task_runtime` 说成“仓里已有基座”，会误导后续实施者低估接线工作量。

### H2. checkpoint writeback 不是“闭环没补完”，而是“承重件还没落地”

Claude 认为当前并不存在一个已经真实运行过的：

1. checkpoint 写入
2. checkpoint 恢复
3. new / continue / branch 判断

所以对这层不能简单说“补齐”，更准确是：

> 任务层的统一逻辑任务层仍属于首次实现

### H3. “补齐优先，不重构”不能泛化到任务层

Claude 认可这句话对知识层成立，因为：

1. `work memory`
2. `runtime pack`
3. `KB fallback`

这些都已经有代码、测试和真实验证。

但它认为这句话不能直接套到：

1. `task_id`
2. `checkpoint`
3. `new / continue / branch`

这条任务层上，因为这部分还没有生产实现。

## 5. Claude 提出的中优先级问题

### M1. Feishu 角色可能被我说得太保守

Claude 额外核到：

1. `feishu_handler.py`
2. `feishu_ws_gateway.py`

这条 ingress 已经有 webhook + WS 双模式、签名验证、去重、异步处理、回执卡片等完整接线。

所以它提醒我：

> 如果第一阶段目标是“能接正式工作任务”，Feishu 的现有 ingress 可能比空转的 task_runtime 更接近最先可跑通的入口。

### M2. publicagentmcp 的定位还没彻底选定

Claude 认为我们现在还在两种口径之间摇摆：

1. `ask wrapper`
2. `orchestration facade`

如果不做这个选择，后面所有 pruning 都会反复争论。

### M3. memory scope 四层定义缺少实现路径

Claude 认可 L0/L1/L2/L3 的设计思路，但提醒：

1. 当前 `work_memory_manager` 并没有直接对应这四层
2. 所以这还是治理定义，不是现成实现

### M4. 第一阶段的质量兜底没有完全说清

Claude 认为：

1. 我们已经定义了 5 条验收标准
2. 但 evaluator/skeptical gate 被推到第二阶段

于是第一阶段到底由谁来判“不理解偏 / 不漏项 / 口径一致”，这个地方还需要说清楚。

## 6. Claude 最重要的收紧建议

### 6.1 把两条线分开

Claude 认为现在必须明确拆开两条线：

1. `知识层补齐`
2. `任务层首次实现`

这两条线的成熟度、工作量、验证方法完全不同，不应该继续共用一个“补齐优先”的总口径。

### 6.2 给统一逻辑任务层定义最小端到端切片

Claude 认为：

1. `task_id`
2. `checkpoint`
3. `memory scope`
4. `new / continue / branch`

这些定义本身没有错，但必须选一个最小切片先跑通。

它建议的例子是：

1. 从一个具体 surface 发起真实 planning 任务
2. 分配 `task_id`
3. 推进一轮
4. 写入 checkpoint
5. 从另一个 surface 恢复
6. 读到 checkpoint 继续

## 7. 我对 Claude 评审的吸收

### 7.1 我接受的点

我接受 Claude 的 3 个关键收紧：

1. 不能再把 `task_runtime` 说成“已有可用基座”
2. 不能再把“知识层补齐”泛化成“整个 planning agent 都只是补齐”
3. 下一阶段必须定义一个统一逻辑任务层的最小端到端切片

### 7.2 我仍然保持不变的点

我不会因为这轮 second opinion 推翻下面这些主判断：

1. 第一阶段主线仍应收口到 `planning` 长任务 agent
2. 四层 surface 分层仍然成立
3. `work memory + reviewed runtime pack + planning-priority context` 仍是当前 planning 知识主线
4. `KB / vector / graph` 仍应降为支撑层

也就是说：

> Claude 没有推翻主方向，而是逼我把“哪些已经可补齐、哪些其实还没落地”分得更清楚。

## 8. 下一步口径应该怎么改

基于 Claude 的 second opinion，我认为后续应把总口径改成：

1. `知识层`
   - 已有真实效果
   - 当前以补齐为主
   - 优先补 `freshness / promotion / acceptance / writeback`
2. `任务层`
   - 统一逻辑任务层的治理定义已经冻结
   - 但最小生产闭环尚未落地
   - 下一步重点不是“补齐旧闭环”，而是“先跑通第一个端到端切片”

## 9. Claude 给出的 Next 3

Claude 认为接下来最该做的 3 件事是：

1. 定义并跑通统一逻辑任务层的最小端到端切片
2. 刷新 runtime pack freshness，并提升关键 planning docs 的 atom promotion
3. 明确 `publicagentmcp` 到底是 `ask wrapper` 还是 `orchestration facade`

## 10. 一句话结论

Claude 的 second opinion 没有推翻我们这轮的主线，但它指出了一个关键收紧点：

> 现在可以说“知识层优先补齐”，但不能再笼统说“整个 planning agent 都只是补齐”；统一逻辑任务层目前仍属于首次实现阶段，下一步必须定义最小端到端切片。
