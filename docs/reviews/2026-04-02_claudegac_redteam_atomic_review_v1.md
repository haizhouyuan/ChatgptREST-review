# 2026-04-02 ClaudeGAC Redteam Atomic Review v1

## 1. 这份文档在做什么

这不是一份顺从式 second opinion。

这次要求 `claudegac` 做的是：

1. 原子级核代码
2. 尽量反对我已经冻结过的口径
3. 明确指出哪些说法是“说轻了”、哪些判断会误导后续计划
4. 给出更尖锐但可执行的替代表述

本轮审核对应的完整运行证据在：

1. `run_id`: `ccjob_20260402T143122Z_ed431e74`
2. `run_dir`: `/vol1/1000/home-yuanhaizhou/.claude-gac/skills/claudecode-agent-runner/runs/ccjob_20260402T143122Z_ed431e74`
3. `result.json`: `/vol1/1000/home-yuanhaizhou/.claude-gac/skills/claudecode-agent-runner/runs/ccjob_20260402T143122Z_ed431e74/result/result.json`
4. `claude_result.json`: `/vol1/1000/home-yuanhaizhou/.claude-gac/skills/claudecode-agent-runner/runs/ccjob_20260402T143122Z_ed431e74/result/claude_result.json`
5. `stdout.log`: `/vol1/1000/home-yuanhaizhou/.claude-gac/skills/claudecode-agent-runner/runs/ccjob_20260402T143122Z_ed431e74/logs/stdout.log`

## 2. 红队一句话结论

如果把这次红队审核压成一句话，它的核心意思是：

> 目前最大的风险不是方向错了，而是纸面设计已经非常完整，但真正跑在生产路径上的统一任务层几乎还不存在；因此下一步不该继续冻结更多定义，而该先证明一个最窄场景真的能跑通。

这份审核比之前那版 Claude second opinion 更尖锐，主要强化了 3 个反对点：

1. `task_runtime` 不能再被叫成“已有基座”
2. `Feishu` 不是自然会并入主线的“薄次入口”
3. `publicagentmcp` 被重新命名成 `ask wrapper` 这件事，本身也值得被反对

## 3. 红队最核心的不同意见

### 3.1 HIGH-1: 统一逻辑任务层不是“补闭环”，而是首次生产集成

红队明确反对我之前的这类表述：

1. “统一逻辑任务层已有基座，只差补齐闭环”
2. “任务层主要也是补齐，不像首次实现”

它给出的代码依据是：

1. `task_runtime_v1` 在 [app.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/app.py#L196) 注册时就是 `core=False`
2. `/v1/tasks` 系列端点当前没有生产 caller
3. `routes_agent_v3.py` 里的 `logical_task_id` 只是 telemetry 透传，不接 `task_runtime`
4. `agent_mcp.py` 对 `task_runtime`、`checkpoint`、`logical_task` 没有真实生产引用
5. `TaskStateMachine.checkpoint()` 只在测试里被调用

红队的结论是：

> 任务层不是“补闭环”，而是 P0 的首次集成工程。

### 3.2 HIGH-2: Feishu 现在不在 canonical northbound 主线上

红队明确反对我之前把 `Feishu / OpenClawBot` 定位成“capture / dispatch / 轻交互，后续自然并入任务层主线”的说法。

它给出的代码依据是：

1. [feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py#L49) 默认直打 `http://127.0.0.1:18711/v2/advisor/advise`
2. 整条 Feishu 路径对 `/v3/agent/turn` 的引用为 0
3. Feishu 构造的 payload 结构和 `AgentTurnRequest` 不是一套契约

红队的结论是：

> 只要 Feishu 还停在 `/v2/advisor/advise`，多端共享 `task_id + checkpoint` 的主叙事就还没有真正开始。

### 3.3 HIGH-3: `publicagentmcp` 已经更像 orchestration facade，而不是 ask wrapper

这条是红队最直接反对当前新冻结口径的地方。

红队认为：

1. [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py) 已经包含 watch store、autostart、session 恢复、deferred delivery、background watcher
2. [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py) 已经承载 duplicate detection、microtask routing、structured output hints、workspace integration、memory capture 等厚逻辑
3. 把它重新命名成 `ask wrapper`，然后说“聪明能力以后上提到 policy layer”，风险是把复杂度拆成两摊，而不是减少复杂度

红队的结论是：

> 更诚实的口径，是承认它已经是 orchestration facade，然后考虑在内部做拆分，而不是在外面再发明一层。

### 3.4 HIGH-4: `workflow / skill / policy layer` 目前更多是计划，不是代码现实

红队也反对我把 `Lane Policy / Attachment Preflight Policy / Fast vs Deep Delivery Policy` 说得太像“只差冻结”的姿态。

它指出：

1. 仓内并没有真正的 policy engine / policy registry / policy module
2. 当前多数“聪明逻辑”还是硬编码在 `routes_agent_v3.py`
3. 把 client 负担“上提到 policy layer”是方向判断，不是现状描述

红队的结论是：

> 这层是待建系统，不是现成承重层。

### 3.5 HIGH-5: 第一阶段 scope 仍然偏大

红队认为我们虽然在收口，但“第一阶段”仍然说得过宽。

它不同意：

1. 一上来冻结 8 种 planning 工作类型
2. 同时讨论多端统一、任务层、知识层、policy、surface authority

它建议把 MVP 再收窄成 1 种任务类型，优先建议：

1. `会议沉淀`
2. 或 `项目现状诊断`

## 4. 红队认可了什么

这次不是全盘推翻。它仍然认可 5 个核心判断：

1. `Codex / Claude Code / Antigravity` 是现实里的主工作台
2. 把 surface 分层，比混成一个“执行层”更正确
3. `planning review plane + reviewed runtime pack + work memory` 是知识主线
4. `KB / vector / graph` 当前应降成支撑层
5. 旧层不该一刀切删除，而应先收 authority 再逐步退役

所以红队并不是说：

1. 总方向错了
2. planning 主线错了
3. 知识层要推翻重做

它真正反对的是：

1. 把任务层说得太像已经存在
2. 把 Feishu 路径差距说轻了
3. 把 `publicagentmcp` 收口说得太顺

## 5. 这次红队要求改写的总口径

它提出的替代表述可以压成这一句：

> Planning agent 第一阶段的真实状态是：知识层已经半可用，应该继续补自动化；但任务层和多端连续性还没有在生产里跑起来。当前最大的风险不是方向错，而是纸面设计完整度高于运行态证明程度。

这句话和之前“双审综合裁决”的差异在于：

1. 之前的综合裁决已经把知识层和任务层拆开了
2. 但这次红队进一步要求，把“首次生产实现”说得更重，而不是继续沿用“补齐”语气
3. 同时，它对 `publicagentmcp=ask wrapper` 这个新定性提出了直接反对

## 6. 红队给出的 Alternative Next 3

### 6.1 先做一个最窄的生产切片

红队建议不要继续冻结定义，而是直接跑通一条最窄场景：

1. 任务类型只选 `会议沉淀`
2. 从 Feishu 发起
3. 改走 `/v3/agent/turn`
4. 分配 `task_id`
5. 在 Codex 推进一轮
6. 写 checkpoint
7. 从 Feishu 查状态或恢复

红队强调：

> 在这条链路没跑通前，4 层 memory scope、14 字段 checkpoint、8 种任务类型都还是纸面设计。

### 6.2 把 Feishu gateway 迁到 `/v3/agent/turn`

红队认为，这是多端统一叙事成立的前提。

如果 Feishu 继续走 `/v2/advisor/advise`：

1. 它就不在 canonical northbound 主线上
2. 它也无法自然复用后续 task layer 能力
3. “多端共享同一任务真相层”就会继续停留在口号

### 6.3 在 `routes_agent_v3.py` 内部做 policy 抽离，而不是外建一层

红队不是反对 policy 本身，而是反对“先发明一个新层”。

它建议：

1. 先承认 `routes_agent_v3.py` 已经是承重 facade
2. 在它内部提取可重用 policy 函数/类
3. 等真实切片跑通后，再决定是否需要独立 policy layer

## 7. 我对这次红队审核的当前判断

### 7.1 我接受的部分

我认为红队这 4 点是成立的，而且需要进入后续主计划口径：

1. `task_runtime` 不能再被叫成“已有基座”
2. Feishu 到 canonical northbound 的 gap 的确被之前文档说轻了
3. “policy layer” 当前更像待建系统，而不是现有承重层
4. 第一阶段 MVP 还可以再窄

### 7.2 我暂不直接改写的部分

我暂时不会直接把 `publicagentmcp` 的 freeze 从 `ask wrapper` 改回 `orchestration facade`，原因不是红队没道理，而是：

1. 这是一个“现状描述”和“目标收口”混在一起的问题
2. 从现状看，它的确已经承载了 orchestration facade 的厚度
3. 但从目标收口看，你已经明确希望它不要继续长成大杂烩

所以更准确的说法应当是：

> 代码现实上，它已经像 orchestration facade；目标收口上，应当朝 ask-wrapper-like boundary 收缩。

这两个判断不能混成一句。

## 8. 当前最有价值的决策影响

这次红队审核对后续真正有价值的，不是“再多一份 review”，而是把下一步排序重新收紧：

1. `知识层`
   - 继续补 `freshness / promotion / acceptance / writeback`
   - 不重构
2. `任务层`
   - 不再空谈统一逻辑任务层
   - 直接做第一条真实生产切片
3. `Feishu`
   - 不再只按“轻入口”来想
   - 要正视它和 canonical northbound 的断裂
4. `publicagentmcp`
   - 不再只讨论名字
   - 要区分“代码现状厚度”和“目标边界收缩”

## 9. 一句话裁决

如果只保留一句最实用的话，我建议冻结成：

> 这次 ClaudeGAC 红队没有推翻 planning 主线，但它成功证明了：任务层和多端连续性目前仍然主要停留在设计稿上，下一步必须拿一个最窄场景做生产证明，而不是继续靠定义推进。
