# ChatgptREST Entrypoint Matrix v1

> 日期: 2026-03-25
> 状态: docs-only classification
> 目的: 明确 primary / admin-only / maintenance-only / legacy fallback / retired 入口，不改任何运行时判断

## 1. 分类口径

本文件只回答两个问题：

1. 当前默认入口是什么
2. 哪些入口不该被新 agent 当默认入口使用

本轮不做：

- 改入口行为
- 改脚本判断分支
- 改 service 指向

## 2. 入口矩阵

| 分类 | 名称 | 路径 / 地址 | 当前用途 | 对新 agent 的口径 |
|---|---|---|---|---|
| Primary | Public advisor-agent MCP | `http://127.0.0.1:18712/mcp` | coding-agent 默认 northbound surface | 默认从这里进 |
| Primary | ChatgptREST API | `http://127.0.0.1:18711` | 统一 FastAPI app | 运行/状态/API 主入口 |
| Internal | Internal driver MCP | `http://127.0.0.1:18701/mcp` | worker / repair / maint 内部工具层 | 不给普通 agent 当默认入口 |
| Admin-only | Admin MCP | `http://127.0.0.1:18715/mcp` | ops / debug broad surface | 仅内部运维/调试 |
| Maintenance-only | Legacy jobs mode | `chatgptrestctl --maintenance-legacy-jobs` | 受控维护场景 | 不是常规入口 |
| Legacy fallback | External `chatgptMCP` | `/vol1/1000/projects/chatgptMCP` | 外部 fallback | 默认不作为主系统 |
| Retired | Legacy `chatgptrest-*` orch topology | 见 runbook retired 章节 | 历史拓扑 | 只读理解，不继续推广 |

## 3. 对 coding agent 的默认口径

默认应教：

- public advisor-agent MCP
- `advisor_agent_turn`
- `advisor_agent_status`
- `advisor_agent_cancel`

默认不应教：

- `/v1/jobs kind=*web.ask`
- `/v3/agent/*` 裸 REST
- legacy bare MCP tools
- external `chatgptMCP`

## 4. 常见误区

### 4.1 把 `/v3/agent/*` 当默认 northbound surface

不推荐。

它是 backend ingress，不是普通 coding agent 的默认入口。

### 4.2 把 `/v1/jobs kind=chatgpt_web.ask|gemini_web.ask|qwen_web.ask` 当默认入口

不推荐。

对 coding agent，这条路径已经被策略收口，不应继续教学为默认用法。

### 4.3 把 admin MCP 当普通 agent 工具面

不推荐。

admin MCP 保留给 ops/debug broad surface，不是新 agent 的默认连接目标。

### 4.4 把 external `chatgptMCP` 当主系统

不推荐。

它现在只应被理解成 legacy fallback。

## 5. 本轮动作边界

本轮针对 entrypoint 只做两件事：

1. 写清矩阵
2. 在 maintainer 文档和 README/AGENTS 中做显式跳转

本轮明确不做：

- 改任何 runtime condition
- 改 wrapper 分支
- 改 service / port / topology

## 6. 一句话结论

> 对新维护 agent，唯一应该默认教学的 northbound 入口是 public advisor-agent MCP；其他入口都必须带上 admin-only、maintenance-only、legacy fallback 或 retired 的语义标签。
