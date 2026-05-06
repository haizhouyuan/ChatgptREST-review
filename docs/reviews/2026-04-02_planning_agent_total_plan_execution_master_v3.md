# 2026-04-02 Planning Agent Total Plan Execution Master v3

## 1. 这份 v3 相比 v2 改了什么

`v3` 只做一件事：

> 把 `Step 0` 从“材料链 smoke”正式升级成“transport / bridge / main-path 三层 gate”。

原因不是方向变化，而是这轮红队和本地核验都表明：

1. `bridge 本体直调` 可以成立
2. 但这不等于 `OpenClawBot` 的 canonical main path 也成立

## 2. 当前总判断

目前最准确的综合口径是：

1. `planning` 第一阶段主线不变
2. `知识层` 仍然并行做补齐
3. `任务层` 仍属于首次生产实现
4. `Feishu` 的 owner 仍然是 `OpenClaw/OpenClawBot`
5. `Codex / Claude Code / Antigravity` 仍然是深度工作台
6. `Step 0` 现在必须先证明 `OpenClawBot` 主链是真的，而不是只证明 bridge 本体

## 3. phase-1 任务类型不变

phase-1 第一条生产切片仍然只做：

1. `会议沉淀`

## 4. Step 0 现在的正确 gate

在任何 `task_id / checkpoint / continue` 实施规格之前，必须先完成：

> `OpenClawBot` 会议沉淀材料链三层 smoke gate

### 4.1 Gate A: transport

只看：

1. `Feishu -> OpenClawBot` 是否接住消息
2. 音频 / 文件 / 图片是否落盘
3. `MediaPaths` 是否进入 inbound context

### 4.2 Gate B1: bridge contract

只看：

1. `openmind_advisor_ask` 在受控直调下
2. 是否能正确生成 `/v3/agent/turn` payload
3. `task_intake.attachments` / `body.attachments` 是否按预期生成

### 4.3 Gate B2: canonical main path

这是 `v3` 明确新增的强制 gate。

只看：

1. 真正的 `OpenClawBot -> auto-reply -> runEmbeddedPiAgent -> customTools` 路径里
2. bridge 是否真的收到：
   - 主链提供的附件
   - 主链提供的 runtime identity
3. tool caller / agent model 是否真的把文件路径写进 `openmind_advisor_ask.params.context`

### 4.4 Gate C: optional natural-chain

只有 `A + B1 + B2` 都通过后，才做：

1. 让 agent 自然决定是否调用 `openmind_advisor_ask`

## 5. 为什么必须这样拆

因为当前代码现实已经说明：

1. `openmind-advisor` 只认 `context.files / context.attachments`
2. canonical plugin tool context 不含 `files / attachments`
3. `runEmbeddedPiAgent()` 主链没有看到把 `MediaPaths` 显式投影成 plugin attachment context
4. `pi-tool-definition-adapter` 当前 common path 会丢掉 `_ctx`
5. 旧的 replay gate PASS 来自手工注入 `runtime_ctx`，不是主链证明

所以现在不能再说：

> “先 smoke 一下材料链，过了就可以写 task continuity 规格。”

更准确的是：

> “先分别证明 transport、bridge 本体、canonical main path，以及 tool caller 会不会把文件路径放进 bridge 读取的位置，再进入 task continuity 实施。”

## 6. phase-1 baseline 不变，但前置 gate 更严格

phase-1 baseline 目标链仍然是：

1. `Feishu -> OpenClawBot`
2. `OpenClawBot -> canonical task plane`
3. 分配 `task_id`
4. 在深度工作台推进一轮
5. 写入最小 checkpoint
6. 从 `OpenClawBot` 查状态或继续

但从 `v3` 起，这条 baseline 只有在 `Step 0 B2` 过后才允许进入实施。

## 7. `task_runtime` 的口径不变

这条线仍然不变：

1. phase-1 不把 full `task_runtime` 当作前置
2. continuity carrier 仍优先考虑更轻的实现路径
3. `AgentSessionStore sidecar` 仍只当候选，不升格成最终 task truth

## 8. `publicagentmcp` 的口径不变

这条也不变：

1. phase-1 不再机会主义膨胀
2. 允许只为 MVP 连续性增加最小承重件
3. 不把模型选择、附件判断、快慢交付全部堆回去

## 9. 新的 Next 4

### 9.1 Step 0A

跑 `Feishu/OpenClawBot` 会议材料 transport smoke。

### 9.2 Step 0B1

跑 `openmind-advisor` bridge contract capture smoke。

### 9.3 Step 0B2

跑 OpenClaw canonical main-path capture smoke。

### 9.4 Step 1

只有 `A + B1 + B2` 结果冻结后，才写第一条生产切片实施规格。

## 10. 一句话结论

`v3` 的核心改写是：

> planning 第一阶段继续走 `会议沉淀` 最小生产切片，但 `Step 0` 现在必须先同时证明 `transport`、`bridge 本体` 和 `OpenClaw 主链`，不能再把受控直调 bridge 的 PASS 当成整条链已通。
