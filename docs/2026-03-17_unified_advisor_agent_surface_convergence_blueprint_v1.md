# 2026-03-17 Unified Advisor Agent Surface Convergence Blueprint v1

## 1. 目标

把当前分散的 `jobs` / `advisor` / `mcp` / OpenClaw plugin / wrapper CLI 入口，收敛成一个真正的 **advisor-agent interaction model**：

- 客户端只表达意图，不直接编排 `submit -> wait -> answer -> retry`
- 服务端负责路由、附件预处理、会话续接、恢复、自愈、结果整形
- Codex / Claude Code / Antigravity / OpenClaw 默认都只面对一个高层入口
- 低层工具和低层 REST 契约继续保留，但降级为 internal/admin/debug surface

这份蓝图不要求一次性推翻现有实现。原则是：**复用已有 controller + advisor + jobs 底座，新建 public facade，逐步迁移客户端**。

## 2. 现状盘点

### 2.1 当前真实对外/对客户端入口

| Surface | 位置 | 当前语义 | 主要使用方 | 当前问题 |
|---|---|---|---|---|
| REST jobs v1 | `/v1/jobs/*` | 低层作业队列 | wrappers, ops, power users | 需要客户端自己理解 job/wait/answer 状态机 |
| Advisor wrapper v1 | `/v1/advisor/advise` | 旧 advisor wrapper | 历史兼容 | 语义老、不是主要未来入口 |
| Advisor v2 advise | `/v2/advisor/advise` | graph/controller 热路径 | Feishu/OpenMind integration | 与 ask 语义并存，名字接近但契约不同 |
| Advisor v2 ask | `/v2/advisor/ask` | route + execution in one call | MCP/OpenClaw/plugin clients | 仍暴露 job/route/provider 语义，不够 agent-like |
| ChatgptREST MCP | `chatgptrest-mcp.service` | 51 个工具的薄封装 | Codex / Claude Code / Antigravity | 工具太多，暴露层级过低 |
| OpenClaw plugin `openmind-advisor` | `openclaw_extensions/openmind-advisor/index.ts` | `advise` / `ask` 双模式 + 可选 wait/answer | OpenClaw shell | 同一个 advisor 概念分成两套后端路径 |
| OpenClaw memory / graph plugin | `openmind-memory`, `openmind-graph` | 辅助 recall/graph | OpenClaw | 本身没错，但不应成为默认对话入口 |
| CLI | `chatgptrest/cli.py` | jobs/advisor/issues/ops CLI | 运维、脚本 | 偏低层，应继续保留但不做默认入口 |
| Wrapper CLI | `skills-src/chatgptrest-call/scripts/chatgptrest_call.py` | provider-first wrapper | 冷客户端、外部脚本 | 直接暴露 provider/preset，绕开 advisor 语义 |

### 2.2 关键代码事实

1. `chatgptrest.mcp.server` 当前同时暴露：
   - `chatgptrest_advisor_ask`
   - `chatgptrest_ask`
   - `chatgptrest_followup`
   - `chatgptrest_consult`
   - `chatgptrest_gemini_generate_image_submit`
   - 一整套 jobs / issues / repair / ops 工具
2. `openmind-advisor` 插件并不是单一 contract：
   - `mode=advise` 打 `/v2/advisor/advise`
   - `mode=ask` 打 `/v2/advisor/ask`
   - `waitForCompletion=true` 时还会再打 `/v1/jobs/{job_id}/wait` 和 `/answer`
3. `skills-src/chatgptrest-call/scripts/chatgptrest_call.py` 不是 advisor-first wrapper，而是 provider-first wrapper：
   - 先选 `chatgpt|gemini|qwen`
   - 再组装 `kind` / `preset`
   - 最终通过 `chatgptrest.cli jobs run` 走 `/v1/jobs`
4. `ControllerEngine` 已经把 `/v2/advisor/advise` 与 `/v2/advisor/ask` 统一到 durable controller 视图上，这意味着收敛不需要另起 orchestration 内核。

### 2.3 结构性问题

| ID | 问题 | 影响 |
|---|---|---|
| P1 | public surface 太多且层级不一致 | 客户端必须学习底层实现细节 |
| P2 | “advisor” 概念同时对应 `advise`、`ask`、MCP tool、OpenClaw plugin | 同名不同义，难以推广统一用法 |
| P3 | wrapper CLI 直接暴露 provider/preset | 用户心智回到“我在手工选模型”，而不是“我在跟 agent 交互” |
| P4 | ChatgptREST MCP 把 internal/admin/debug tool 全部暴露给普通客户端 | Codex/Claude Code 工具列表噪声过高 |
| P5 | OpenClaw 默认 slow-path 入口仍是双后端 contract | OpenClaw/OpenMind 无法自然成为统一 agent shell |
| P6 | 低层 jobs 契约与高层 advisor 契约没有显式主从关系 | 新客户端不知道应该从哪一层开始接入 |

## 3. 设计原则

1. **Public facade only**
   - 给普通客户端一个高层入口，不再默认暴露 provider/preset/job/wait 细节。
2. **Reuse, do not rewrite**
   - 复用 `ControllerEngine`、`standard_entry_pipeline()`、`/v2/advisor/ask`、`/v1/jobs`、repair lanes。
3. **Dual-surface model**
   - public surface 面向 agent 客户端
   - internal/admin surface 面向 ops/debug/manual power users
4. **Deterministic first**
   - 路由、提示词增强、附件检查、重试、自愈优先走确定性逻辑
   - 不要每 turn 再额外调用一个昂贵 LLM planner
5. **Additive migration**
   - 旧接口先兼容，不做一刀切删除
   - 新客户端先迁移到 facade，再逐步去文档化旧入口

## 4. 目标架构

### 4.1 Public HTTP surface

新增一个 canonical agent endpoint：

- `POST /v3/agent/turn`
- `GET /v3/agent/session/{session_id}`
- `POST /v3/agent/cancel`

推荐不要把这个新 contract 命名成新的 `advisor/ask` 变体。原因：

- `advise` / `ask` 历史包袱已经很重
- 新入口的职责是“对话式 agent turn”，不是旧意义上的 ask wrapper
- 用 `v3/agent/*` 能把 public facade 和内部 advisor graph 区分开

### 4.2 Public MCP surface

新增一个独立的 public MCP server，例如：

- service: `chatgptrest-agent-mcp.service`
- transport endpoint: `http://127.0.0.1:18714/mcp`

只暴露 2 到 3 个工具：

- `advisor_agent_turn`
- `advisor_agent_cancel`
- 可选 `advisor_agent_status`

这套 public MCP 只调用新的 `/v3/agent/*` contract。

现有 `chatgptrest-mcp.service` 继续保留，但明确降级为：

- internal/admin/debug MCP
- 运维、修复、手工编排使用
- 不再推荐普通客户端接入

### 4.3 OpenClaw / OpenMind public path

`openmind-advisor` 插件继续保留一个工具即可，但其后端 contract 必须收敛到同一个 agent facade：

- `openmind_advisor_ask` 作为兼容工具名保留
- 内部统一改打 `/v3/agent/turn`
- 移除当前插件内的 `ask|advise` 双分支概念
- 移除插件自己拼 `/v1/jobs/{id}/wait`、`/answer` 的逻辑

`openmind-memory` 与 `openmind-graph` 的定位：

- 继续保留为 OpenMind substrate/expert tools
- 不纳入默认聊天入口
- 在 OpenClaw 中仍可作为辅助能力存在

### 4.4 CLI path

CLI 分成两层：

1. admin CLI 保留
   - `chatgptrest jobs ...`
   - `chatgptrest advisor ...`
   - `chatgptrest issues ...`
2. public agent CLI 新增
   - `chatgptrest agent turn`
   - `chatgptrest agent status`
   - `chatgptrest agent cancel`

`skills-src/chatgptrest-call/scripts/chatgptrest_call.py` 的 fate：

- 继续保留文件路径，避免外部文档立即全部失效
- 但内部实现改为 agent-first wrapper
- provider/preset 参数降级为 expert override，而不是默认主路径

### 4.5 Internal execution substrate

以下能力不再作为普通客户端的 primary contract，而是由 agent facade 内部决策：

- `/v2/advisor/ask`
- `/v2/advisor/advise`
- `/v1/jobs/*`
- `chatgptrest_consult`
- `gemini_web.generate_image`
- `repair.check` / `repair.autofix` / `sre.fix_request`

它们仍然存在，但职责变成：

- facade 的内部执行 lane
- admin/operator tools
- debugging / replay / evidence retrieval

## 5. 新 public contract 建议

### 5.1 `POST /v3/agent/turn`

请求体建议：

```json
{
  "message": "评审这个代码库的 dashboard UX",
  "session_id": "optional-session-id",
  "attachments": ["/abs/path/repo.zip"],
  "goal_hint": "code_review",
  "depth": "standard",
  "context": {
    "repo": "ChatgptREST"
  },
  "client": {
    "name": "claude-code",
    "instance": "host-user-shell"
  }
}
```

字段说明：

- `message`: 用户自然语言意图
- `session_id`: 客户端会话锚点。为空时服务端创建
- `attachments`: 统一附件入口，内部再映射到 `file_paths`
- `goal_hint`: 可选高层 hint，如 `code_review|research|image|report|repair`
- `depth`: `light|standard|deep`
- `context`: 附加结构化上下文
- `client`: 追踪信息，不暴露内部 provider 细节

响应体建议：

```json
{
  "ok": true,
  "session_id": "agent_sess_xxx",
  "run_id": "run_xxx",
  "status": "completed",
  "answer": "...",
  "delivery": {
    "format": "markdown",
    "answer_chars": 4210
  },
  "artifacts": [
    {
      "kind": "conversation_url",
      "uri": "https://..."
    }
  ],
  "provenance": {
    "route": "dual_review",
    "provider_path": ["chatgpt_pro", "gemini_deepthink"],
    "final_provider": "chatgpt"
  },
  "next_action": {
    "type": "followup",
    "safe_hint": "可以继续追问或要求改写成 PR review"
  },
  "recovery_status": {
    "attempted": true,
    "final_state": "clean"
  }
}
```

核心原则：

- 返回用户能消费的答案和可继续会话的标识
- provenance 保留高层可解释性
- 不要求普通客户端理解 job_id / wait / answer chunk

### 5.2 `GET /v3/agent/session/{session_id}`

只做 fallback，不作为主要使用方式。

返回：

- 当前 session 最新 run
- 最近 answer 摘要
- terminal / in_progress 状态
- 推荐下一动作

### 5.3 `POST /v3/agent/cancel`

面向长任务取消，不暴露底层 `/v1/jobs/{id}/cancel` 细节。

## 6. Agent facade 内部策略

### 6.1 Routing

优先复用：

- `standard_entry_pipeline()`
- `ControllerEngine.ask(...)`
- 现有 advisor route decision

补充一个 facade-level capability resolver，把高层目标映射到内部 lane：

| High-level intent | Internal lane |
|---|---|
| quick answer | KB direct or quick_ask |
| code review | advisor ask + optional consult |
| dual model review | consult |
| deep research | advisor ask route=deep_research |
| image generation | `gemini_web.generate_image` |
| repair/fix request | `sre.fix_request` / repair lane |

### 6.2 Attachment handling

统一在 facade 层做：

- 路径规范化
- 允许目录检查
- zip/text bundle 预检
- provider compatibility tagging

具体 provider 细节仍由 provider-owned execution code 决定，不把 Gemini/ChatGPT 特例硬编码在 public contract。

### 6.3 Session continuity

服务端维护：

- facade `session_id`
- `run_id`
- provider conversation lineage
- high-level delivery history

客户端只需要传回 `session_id`，不用管理 provider conversation URL。

### 6.4 Recovery / self-heal

facade 在内部可复用：

- background wait
- cooldown / blocked / needs_followup 处理
- `repair.check`
- `repair.autofix`
- `sre.fix_request`

但 public contract 只暴露：

- `recovery_status`
- `next_action.safe_hint`

不要把 raw `needs_followup` 直接塞给普通客户端，除非确实需要人工登录/权限修复。

## 7. 各入口的目标归宿

| Current entry | Target fate |
|---|---|
| `chatgptrest-mcp` | internal/admin MCP，继续保留 |
| `/v1/jobs/*` | internal/admin REST，继续保留 |
| `/v2/advisor/advise` | internal controller lane，继续保留 |
| `/v2/advisor/ask` | internal smart execution lane，继续保留 |
| `openmind_advisor_ask` | 兼容工具名保留，内部改打 `/v3/agent/turn` |
| `openmind-memory` / `openmind-graph` | 保留为 expert substrate tools |
| `chatgptrest.cli jobs/*` | 保留为 admin CLI |
| `chatgptrest.cli advisor/*` | 保留为 admin/compat CLI |
| `chatgptrest_call.py` | 改成 agent-first compat wrapper |

## 8. 推荐实施批次

### Batch A: Public facade foundation

目标：把单一 public contract 立住，不先清理旧入口。

实现内容：

1. 新增 `/v3/agent/turn`
2. 新增 `/v3/agent/session/{session_id}`
3. 新增 `/v3/agent/cancel`
4. 新增 public response schema
5. 复用 `ControllerEngine` 输出 `delivery / next_action / artifacts`
6. 增加 facade-level provenance / recovery fields
7. 新增核心 API tests

Definition of Done:

- 普通客户端可以不理解 `job_id` 也拿到最终答案
- 同一个 `session_id` 可以继续 follow-up
- provider/job 细节只在 provenance 中做弱暴露，不要求客户端消费

### Batch B: Public MCP server

目标：解决 Codex / Claude Code / Antigravity “工具暴露过多”的问题。

实现内容：

1. 新增 `chatgptrest-agent-mcp` server entrypoint
2. 新增 `advisor_agent_turn`
3. 新增 `advisor_agent_cancel`
4. 可选 `advisor_agent_status`
5. 新增启动脚本和 systemd unit 模板
6. 保留 `chatgptrest-mcp` 不变

Definition of Done:

- 指向 public MCP 的客户端只看到 2 到 3 个工具
- 现有 admin/debug 使用方不受影响

### Batch C: OpenClaw / CLI convergence

目标：把 OpenClaw plugin 和 wrapper CLI 从 fragmented routes 收到 facade。

实现内容：

1. `openmind-advisor` 改打 `/v3/agent/turn`
2. 去掉插件里的 `ask|advise` 双分支和手写 wait/answer 拼接
3. `chatgptrest.cli` 新增 `agent` 子命令组
4. `chatgptrest_call.py` 改为 agent-first wrapper
5. 更新 runbook / client docs / OpenClaw integration docs

Definition of Done:

- OpenClaw 默认 slow-path 入口与 Codex/Claude Code 入口 contract 一致
- wrapper CLI 默认不再要求用户先思考 provider/preset

### Batch D: Deprecation and rollout

目标：让新入口成为默认接入规范。

实现内容：

1. 文档中把 `/v1/jobs`、`chatgptrest_ask`、`chatgptrest_consult` 降级为 advanced/internal
2. 客户端登记簿和客户端接入文档全部同步
3. 增加 metrics：
   - public facade traffic
   - legacy jobs traffic
   - legacy MCP low-level tools traffic
4. 视情况为 low-level MCP tools 增加明显 deprecation hints

## 9. 不建议做的事

1. 不建议直接把 `chatgptrest_ask(auto_wait=True)` 改成 public agent contract
   - 旧 tool 已有明确语义和兼容面
2. 不建议把 public facade 直接 built into 现有 51-tool MCP server
   - 这样无法真正减少客户端可见工具数
3. 不建议删除 `/v1/jobs/*`
   - 这会伤到 ops/debug/manual replay
4. 不建议把 OpenClaw memory/graph 也硬并进单工具
   - 它们是 substrate/expert capability，不是默认聊天入口

## 10. 推荐首个开发任务范围

建议 CC 第一轮直接做 **Batch A + Batch B + Batch C**，但以“additive, compatibility-first”方式实现：

- 新增 `/v3/agent/*`
- 新增 `chatgptrest-agent-mcp`
- OpenClaw advisor plugin 改走新 endpoint
- CLI / wrapper 默认改走新 endpoint
- 旧入口先保留

原因：

- 只做 Batch A 还解决不了“客户端看到太多工具”
- 只做 Batch B 又没有统一后端 contract
- 只改 OpenClaw 不改 Codex/Claude Code，依然会分裂

## 11. 交付验收标准

### 功能

- Codex / Claude Code / Antigravity 可只通过 `advisor_agent_turn` 完成常见 ask/review/research/image/follow-up
- OpenClaw `openmind_advisor_ask` 背后 contract 与 public agent facade 一致
- wrapper CLI 默认走 agent facade

### 兼容

- `/v1/jobs/*`、`/v2/advisor/ask`、`/v2/advisor/advise` 仍可工作
- `chatgptrest-mcp` 仍可工作

### 观测

- run / session / provenance / recovery 在 artifacts 和 API 响应里可追踪
- 新旧入口流量可区分

### 文档

- `runbook.md`
- `contract_v1.md` 或新增 `contract_v3_agent.md`
- `client_projects_registry.md`
- OpenClaw integration docs
- fresh client quickstart

## 12. 最终结论

这次收敛的关键不是“再做一个更聪明的 ask wrapper”，而是建立明确的 **public advisor-agent facade**：

- public 面只谈 `turn / session / cancel`
- internal 面继续保留 `jobs / advisor / consult / repair`
- OpenClaw / Codex / Claude Code / Antigravity 统一到同一个高层 contract

这样既能保住现有底座，也能真正把客户端体验从“调用一堆工具”收成“在和一个 agent 对话”。
