# 2026-04-02 Feishu OpenClawBot Ingress Constraint v1

## 1. 这份文档在冻结什么

这份文档冻结一个新的产品边界约束：

> `Feishu` 人类入口必须走 `OpenClaw / OpenClawBot`，不把 ChatgptREST-native Feishu gateway 升格成 planning 第一阶段的生产主入口。

这不是在否定前面的代码调查，而是在前面调查结论之上，加入一个新的业务/产品层拍板。

## 2. 代码现实和产品边界要分开

现在必须把两层东西分开说：

### 2.1 代码现实

当前仓内同时存在两条与 Feishu 相关的路径：

1. ChatgptREST-native Feishu WS gateway  
   [feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py#L49)
   默认走 `/v2/advisor/advise`

2. OpenClaw `openmind-advisor` bridge  
   [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L301)
   会构建 versioned `task_intake` 并打 `/v3/agent/turn`

### 2.2 产品边界

你现在明确给出的约束是：

1. `Feishu` 要走 `OpenClawBot`
2. 不希望直接把 ChatgptREST-native Feishu gateway 做成最终人类入口

所以后续 planning 第一阶段里，Feishu 的 authoritative human-facing owner 应该是：

1. `OpenClaw`
2. `OpenClawBot`

而不是：

1. ChatgptREST 内置 `feishu_ws_gateway`

## 3. 这会改写哪些既有口径

### 3.1 改写点 A：Feishu 的 owner

以后更准确的说法不是：

> `Feishu / OpenClawBot` 是一个合在一起的模糊入口。

而是：

> `Feishu` 的生产入口 owner 是 `OpenClaw/OpenClawBot`；ChatgptREST 只承接其后续 task plane / cognition / execution 能力。

### 3.2 改写点 B：红队对 Feishu 的建议

上一轮红队最强的建议之一是：

1. 把 Feishu gateway 从 `/v2/advisor/advise` 迁到 `/v3/agent/turn`

在这个新边界下，这句话不能原样执行。

更准确的改写应该是：

> 如果 Feishu 要进入 planning 第一阶段主线，那么应该优先保证 `OpenClawBot -> canonical task plane` 收敛，而不是先把 ChatgptREST-native Feishu gateway 升格。

也就是说，红队指出的 gap 仍然成立，但修复位置要改：

1. 不是优先改 ChatgptREST-native Feishu gateway 成主入口
2. 而是优先检查并收敛 `OpenClawBot` 到 canonical task plane 的桥接

### 3.3 改写点 C：任务层第一条生产切片

之前红队建议的最窄切片是：

1. Feishu 发起
2. 改走 `/v3/agent/turn`
3. 分配 `task_id`
4. Codex 推进
5. 回写 checkpoint

在新约束下，更准确的切片应该写成：

1. `Feishu -> OpenClawBot`
2. `OpenClawBot -> canonical task plane`
3. 分配 `task_id`
4. `Codex / Claude Code / Antigravity` 推进
5. 写 checkpoint
6. 从 `OpenClawBot` 查状态或恢复

## 4. 这对 surface authority 的影响

在 planning 第一阶段，我建议把 Feishu 相关 surface 改成下面这个更明确的分层：

### 4.1 Human-facing ingress owner

1. `Feishu -> OpenClawBot`

这是人类入口层。

### 4.2 ChatgptREST northbound / task plane

1. public MCP
2. `/v3/agent/turn`

这是 ChatgptREST 的 canonical northbound / task plane。

### 4.3 ChatgptREST-native Feishu handlers

1. `feishu_ws_gateway.py`
2. `feishu_handler.py`

这层不应再被当成 planning 第一阶段的默认产品入口，而更适合作为：

1. internal tooling
2. fallback tooling
3. historical compatibility surface

## 5. 这对主计划的真实影响

这个约束会把我们后面实施顺序再收紧一层：

### 5.1 不再把“Feishu 入口”理解成“直接改 ChatgptREST Feishu gateway”

后续凡是讨论“Feishu 怎么接任务”，都应优先问：

1. `OpenClawBot` 当前怎么接
2. 它如何把请求送入 canonical task plane
3. 它如何承接 task status / checkpoint 恢复

### 5.2 任务层 MVP 应围绕 OpenClawBot 设计

如果后面要做第一条真实生产切片，入口应当优先写成：

1. `Feishu / OpenClawBot`
2. 而不是 ChatgptREST-native Feishu gateway

### 5.3 红队结论仍有效，但需要重定向

红队最有价值的提醒依然成立：

1. 任务层目前没有生产闭环
2. Feishu 相关路径和 canonical task plane 之间有明显 gap
3. 不能再只冻结定义

但现在修复的主落点应改成：

1. `OpenClawBot bridge`
2. `canonical task plane`
3. `checkpoint / task truth layer`

而不是先去强化 ChatgptREST-native Feishu WS path。

## 6. 当前建议冻结的表述

后续如果只想保留一句产品边界口径，我建议用这句：

> Feishu 是 planning 第一阶段的重要人类入口，但它的 authoritative owner 是 `OpenClaw/OpenClawBot`；ChatgptREST 承接其后的 canonical task plane、knowledge plane 和 execution capabilities，而不是直接充当最终 Feishu 入口宿主。

## 7. 一句话结论

这个新约束不会推翻前面的调查，但会改写后续实施路线：

> Feishu 要进入主线，但必须以 `OpenClawBot` 为入口 owner 进入主线，而不是把 ChatgptREST-native Feishu gateway 直接升格为 planning 第一阶段的人类入口。
