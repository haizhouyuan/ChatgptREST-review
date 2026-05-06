# 2026-04-02 Public Agent MCP Scope and Pruning Review v1

## 1. 问题

这轮只回答两个问题：

1. `consult` 现在是不是还属于 `publicagentmcp` 的合理范围
2. 如果 `publicagentmcp` 的原始目标只是“更好封装 `chatgpt_web.ask` 和 `gemini_web.ask`”，那它现在是否已经超出这个范围

## 2. 结论先说

### 2.1 `consult`

如果以“封装 `chatgpt_web.ask / gemini_web.ask` 的高层 agent 入口”为目标，`consult` 现在已经偏离这个目标。

原因很简单：

1. 它不是单 provider wrapper
2. 它是独立的多模型并行复核编排
3. 当前用户也明确表示它是早期开发的，现在不用

所以它更合理的 posture 不是继续挂在主 public-agent 叙事里，而是：

1. 降级为非默认专项 lane
2. 或进一步进入 prune / retirement backlog

### 2.2 `publicagentmcp`

如果按“只是更好封装 `chatgpt_web.ask` 和 `gemini_web.ask`”来衡量，当前 `publicagentmcp` 已经明显超出了这个边界。

它现在至少同时承载了三类不同职责：

1. 高层 ask lifecycle facade
2. repo cognition / developer helper
3. 其他扩展能力入口（workspace、image、consult、memory capture 等）

所以当前问题不是“它封装错了”，而是“它变成了一个混合面”。

## 3. 代码事实

## 3.1 `publicagentmcp` 现在公开了哪些工具

`chatgptrest/mcp/agent_mcp.py` 当前只有 6 个 MCP tool：

1. `advisor_agent_turn`
2. `advisor_agent_cancel`
3. `advisor_agent_status`
4. `advisor_agent_wait`
5. `repo_bootstrap`
6. `repo_doc_obligations`

证据：

- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L944)
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L1140)
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L1195)
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L1274)
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L1368)
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L1415)

这已经说明它不只是“四个 lifecycle 工具”。

## 3.2 `advisor_agent_turn` 现在实际承载了什么

`advisor_agent_turn` 不只是把用户消息简单包一层再丢给 `chatgpt_web.ask / gemini_web.ask`。

它当前还显式承载：

1. `task_intake`
2. `workspace_request`
3. `contract_patch`
4. `delivery_mode`
5. `attachments`
6. `memory_capture`
7. `role_id / user_id / trace_id`
8. 自动 background watch / resume

证据：

- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L945)
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L995)
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L1016)
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L1023)
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L1049)

## 3.3 `/v3/agent/turn` 现在在路由什么

`publicagentmcp` 背后真实打的是 `/v3/agent/turn`，而 `/v3/agent/turn` 现在不止是 “ChatGPT lane / Gemini lane” 两路。

它至少还包括：

1. `workspace_action / workspace_clarify`
2. `image` -> `gemini_web.generate_image`
3. `consult / dual_review`
4. direct Gemini research lane
5. controller/chatgpt route map
6. memory capture

证据：

- workspace 分支：
  - [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L2508)
  - [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L2611)
- image 分支：
  - [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L3097)
- consult 分支：
  - [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L3184)
- direct Gemini 分支：
  - [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L3266)
- controller/chatgpt route map：
  - [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L3358)

## 3.4 `status / cancel / wait` 是否还合理

这三个工具本身没有明显越界，反而属于一个高层 facade 正常应该有的生命周期能力。

### `advisor_agent_status`

它做的事情主要是：

1. 查 session 状态
2. 尝试恢复 background watch
3. 附加 watch 字段
4. 返回 enriched public session

证据：

- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L1196)

### `advisor_agent_wait`

它做的事情主要是：

1. 先查当前 session
2. 若未终态，则走 stream wait
3. 刷新最终状态
4. 返回 wait 状态、超时信息和 enriched session

证据：

- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L1275)

### `advisor_agent_cancel`

它做的事情主要是：

1. 调 `/v3/agent/cancel`
2. 清理 watch state
3. 写回 canceled 状态

证据：

- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L1141)

所以如果要 prune，优先目标不该是 `status/cancel/wait`，而应该是：

1. `consult`
2. repo cognition helper
3. workspace/image 等是否继续放在同一 public-agent surface

## 4. 最关键的超界点

### 4.1 `repo_bootstrap` 和 `repo_doc_obligations`

这两个工具最明显地超出了“封装 ChatGPT/Gemini ask”的目标。

它们更像：

1. coding-agent repo cognition helper
2. 开发流程 / 变更义务 helper

而不是：

1. ask facade 的核心组成部分

所以如果要收口 `publicagentmcp`，这两个是最优先的裁剪/迁移候选。

### 4.2 `workspace_request`

如果目标是 planning 第一阶段，`workspace` 这条线现在也明显不是“封装 chatgpt/gemini ask”的必需部分。

它是另一种 northbound task surface。

### 4.3 `image`

`image` 分支也不是 ask wrapper 的核心。

它属于“多能力 agent facade”范畴，不属于“better wrapper for chatgpt/gemini ask”的最小闭环。

### 4.4 `consult`

`consult` 是最适合直接降级的对象：

1. 当前用户明确说不用
2. 它属于早期开发历史层
3. 它把 public-agent 叙事从“封装 ask”拉向了“多模型审议平台”

## 5. 如果按原始目标收口，建议怎么裁

如果现在就按“publicagentmcp 只服务于更好封装 `chatgpt_web.ask` / `gemini_web.ask`”来收口，我建议的最小方案是：

### 5.1 保留

1. `advisor_agent_turn`
2. `advisor_agent_status`
3. `advisor_agent_cancel`
4. `advisor_agent_wait`

因为这四个构成了一个完整高层 lifecycle facade。

### 5.2 在 `turn` 内继续保留

1. ChatGPT/controller lane
2. direct Gemini lane
3. delivery/background handoff
4. attachments / task_intake / contract_patch

这些仍然属于“高层 ask facade”的合理范围。

### 5.3 优先降级 / 外迁 / prune backlog

1. `consult`
2. `repo_bootstrap`
3. `repo_doc_obligations`
4. `workspace_request`
5. `image`

其中最优先可以先冻成 backlog 的是：

1. `consult`
2. `repo_bootstrap`
3. `repo_doc_obligations`

## 6. 一句话结论

如果把 `publicagentmcp` 的原始目标定义为“更好封装 `chatgpt_web.ask` 和 `gemini_web.ask`”，那它现在确实已经长胖了。

最明显超界的不是 `status/cancel/wait`，而是：

1. `consult`
2. `repo_bootstrap`
3. `repo_doc_obligations`
4. `workspace`
5. `image`

换句话说，`publicagentmcp` 现在已经不只是 ask facade，而是一个混合的 public-agent surface。若要裁剪，应该先从这些超界能力下手。
