# 2026-04-02 Feishu OpenClawBot Ingress Constraint Walkthrough v1

## 1. 为什么要补这份文档

前面几轮调查里，关于 `Feishu` 的表述有一个持续的模糊点：

1. 一部分文档在说 `Feishu / OpenClawBot`
2. 一部分调查在直接看 ChatgptREST-native `feishu_ws_gateway.py`
3. 红队进一步建议“把 Feishu gateway 迁到 `/v3/agent/turn`”

这些说法混在一起，容易把“代码里有什么路径”和“产品最终要让哪条路径当 owner”混成一件事。

用户这轮补充了一个清晰约束：

> Feishu 得走 `OpenClaw/OpenClawBot`

所以必须把这件事单独冻结。

## 2. 这轮核对了什么

### 2.1 ChatgptREST-native Feishu path

核对了：

1. [feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py#L49)

结论：

1. 当前默认仍指向 `/v2/advisor/advise`

### 2.2 OpenClaw bridge path

核对了：

1. [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L301)
2. [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L363)
3. [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L444)

结论：

1. OpenClaw bridge 确实会构造 versioned `task_intake`
2. 也确实会打 `/v3/agent/turn`

## 3. 这轮真正冻结的不是代码事实，而是 owner 决策

代码事实本身没有变：

1. ChatgptREST 内仍然有 native Feishu path
2. OpenClaw bridge 也仍然存在

这轮新增的是 owner 决策：

1. `Feishu` 的 human-facing production owner 是 `OpenClaw/OpenClawBot`
2. ChatgptREST-native Feishu path 不再作为 planning 第一阶段主入口来思考

## 4. 它改写了哪条红队建议

红队原话更接近：

1. 直接把 Feishu gateway 改到 `/v3/agent/turn`

现在应改写成：

1. 确保 `OpenClawBot -> canonical task plane` 收敛

这样保留了红队最值钱的部分：

1. Feishu 不能停在和主任务层断裂的路径上

同时避免走错实现位置：

1. 不把 ChatgptREST-native Feishu gateway 错当成产品主入口 owner

## 5. 后续计划上最重要的变化

以后凡是提“Feishu 入口怎么做”，都必须先写清楚到底在讨论哪层：

1. `Feishu human-facing owner`
2. `OpenClawBot bridge`
3. `ChatgptREST canonical task plane`
4. `ChatgptREST native fallback/internal Feishu tooling`

如果不先分层，后面又会把：

1. OpenClaw runtime
2. OpenClawBot
3. ChatgptREST-native Feishu ingress
4. `/v2/advisor/advise`
5. `/v3/agent/turn`

重新搅成一团。

## 6. 这轮输出

新增：

1. [2026-04-02_feishu_openclawbot_ingress_constraint_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_feishu_openclawbot_ingress_constraint_v1.md)
2. [2026-04-02_feishu_openclawbot_ingress_constraint_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-02_feishu_openclawbot_ingress_constraint_walkthrough_v1.md)
