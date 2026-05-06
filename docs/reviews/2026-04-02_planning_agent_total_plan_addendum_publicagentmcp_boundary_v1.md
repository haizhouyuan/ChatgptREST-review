# 2026-04-02 Planning Agent Total Plan Addendum: PublicAgentMCP Boundary v1

## 1. 这份补丁在解决什么

这份文档是给现有总计划补一块缺失的边界：

> 既然 `publicagentmcp` 现在明确按 `ask wrapper` 冻结，而不是 `orchestration facade`，那么过去为了减轻 client 负担塞进去的那一大堆“聪明能力”，后面该放到哪里。

用户真正担心的不是“名字该怎么定义”，而是这些现实问题：

1. client 不知道选哪个模型/哪条 lane
2. client 不知道附件是否齐全
3. client 对产品功能不熟，不知道系统会什么
4. `Pro` 很慢，client 以为 5 分钟就该有完整结果
5. 提示词太封闭，导致调用方式僵硬

所以这份文档的结论不是“退回去”，而是：

> 把这些问题从 `publicagentmcp` 里拿出来，转移到 `workflow / skill / policy layer` 解决。

## 2. 冻结结论

### 2.1 PublicAgentMCP 的定位

现在冻结：

> `publicagentmcp` 是 `ask wrapper`，不是 `orchestration facade`。

这意味着它的角色应该是：

1. 提供稳定的高层调用壳
2. 处理 ask lifecycle
3. 处理基本附件透传
4. 处理后台执行与状态恢复

而不是：

1. 承担整套 planning agent 的策略大脑
2. 承担所有 lane 决策
3. 承担复杂的产品能力解释层
4. 承担任务层的总编排中心

### 2.2 client 负担不靠 MCP 变胖来解决

后续的正确路线不是：

1. 再往 `publicagentmcp` 里加更多智能分支
2. 再往 `turn` 上塞更多特化参数

而是：

1. 让 `MCP runtime` 保持薄且稳定
2. 把“怎么用得聪明”上提到 `workflow / skill / policy layer`

## 3. 三层实现边界

### 3.1 Thin MCP Runtime

这一层只负责“稳”，不负责“聪明”。

建议保留在 `publicagentmcp` 里的能力：

1. `advisor_agent_turn`
2. `advisor_agent_status`
3. `advisor_agent_cancel`
4. `advisor_agent_wait`
5. 附件接收与透传
6. 背景执行与生命周期
7. 幂等、状态、超时、恢复

这层只回答：

1. 请求有没有成功交出去
2. 任务现在是什么状态
3. 要不要等、能不能取消
4. 附件有没有跟着走

### 3.2 Planning Agent Policy Layer

这一层负责“聪明”，而且应该主要由：

1. `prompt`
2. `workflow`
3. `skill`
4. `policy doc`

来承载。

它负责的事情包括：

1. 判断这是什么任务
2. 决定默认走哪条 lane
3. 判断要不要 `consult`
4. 判断要不要接 `workspace`
5. 把用户自然语言整理成高质量 `task_intake`
6. 决定是先给快答还是直接深跑
7. 决定输出形态和交付模式

### 3.3 Task Truth Layer

这一层不应该塞进 `publicagentmcp`，而应独立作为 planning 第一阶段后续主线：

1. `task_id`
2. `checkpoint`
3. `memory scope`
4. `new / continue / branch`
5. `memory writeback`

这层负责跨端连续性和任务真相，不应与 ask wrapper 混成一层。

## 4. 过去那些“塞进 MCP 的功能诉求”，现在分别怎么处理

### 4.1 “client 不知道选哪个模型”

解决方式：

> 不让 client 直接选模型，让 client 选任务模式。

例如只暴露：

1. `快答`
2. `深答`
3. `双审`
4. `继续任务`
5. `收材料`

具体走什么模型/哪条 lane，由 policy layer 决定。

### 4.2 “附件不全，不知道缺什么”

解决方式：

> 做 `attachment preflight policy`，而不是往 MCP 里塞越来越多附件分支。

每次任务先判断：

1. 已收到什么
2. 关键缺件是什么
3. 是否允许带缺件继续

缺关键件时 fail-closed，不要假装能做。

### 4.3 “提示词太封闭，对产品功能不了解”

解决方式：

> 做 `capability / workflow profile`，不把产品知识硬编码进 MCP。

这层要解决的是：

1. planning agent 会什么
2. 哪些入口适合什么任务
3. 什么时候能后台跑
4. 什么时候能双审
5. 什么时候必须补附件

这些都属于 `skill / workflow / usage policy`，不是 MCP 运行时壳。

### 4.4 “Pro 很慢，client 不知道”

解决方式：

> 做 `fast vs deep delivery policy`。

默认分成两阶段：

1. `快答`
   - 5 分钟内给初步理解、缺件判断、任务计划、早期结论
2. `深答`
   - 转后台长跑
   - 后续再交付完整结果

这样解决的是用户体验问题，不是通过让 MCP 胖起来解决。

### 4.5 “client 想 5 分钟拿到答案”

解决方式：

> 区分 `quick triage` 和 `deep completion`。

快阶段给：

1. 我理解的任务是什么
2. 现在缺什么
3. 我建议走什么模式
4. 初步判断或结构化计划

完整深答则作为后台交付。

## 5. 现在要进入总计划的 3 份 policy

这部分应正式纳入总计划，而不是继续作为零散想法。

### P0-A. Lane Policy

这份 policy 只定义：

1. 不同 planning 任务默认走哪条 lane
2. 什么情况下升级到 `consult`
3. 什么情况下需要 `workspace`
4. 什么情况下允许后台执行

### P0-B. Attachment Preflight Policy

这份 policy 只定义：

1. 附件清单怎么列
2. 什么叫关键缺件
3. 缺件时是否允许继续
4. 如何回给用户补件请求

### P0-C. Fast vs Deep Delivery Policy

这份 policy 只定义：

1. 5 分钟内该交付什么
2. 什么任务必须转后台
3. 后台结果怎么回收
4. 什么时候允许只给快答不深跑

## 6. 对总计划优先级的影响

这份补丁加入后，总计划应调整成：

### 第一主线

1. `planning` 长任务 agent 主线
2. 统一逻辑任务层的最小端到端切片
3. 知识层补 `freshness / promotion / acceptance`

### 关键支撑

1. `publicagentmcp` 薄 runtime 化
2. `workflow / skill / policy layer` 吸收 client 负担

### 现在不要继续扩的

1. 不要把 `publicagentmcp` 再做成大杂烩
2. 不要把“client 负担”都理解成需要加后端参数
3. 不要在任务层未落地前继续扩更多 northbound surface

## 7. 一句话结论

既然 `publicagentmcp` 已冻结为 `ask wrapper`，那后续减轻 client 负担的正确方法不是继续把它做胖，而是：

> 让 `MCP runtime` 保持薄而稳定，把 lane 选择、附件预检、快慢交付、能力理解这些“聪明问题”上提到 `workflow / skill / policy layer`，并把这三份 policy 正式纳入总计划。
