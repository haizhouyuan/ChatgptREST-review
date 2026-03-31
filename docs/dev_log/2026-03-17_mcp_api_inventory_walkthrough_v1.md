# MCP / API Inventory Walkthrough v1

日期：2026-03-17

## 本次做了什么

新增一份正式盘点文档：

- `docs/2026-03-17_mcp_and_api_surface_inventory_v1.md`

这份文档把 ChatgptREST 当前与 MCP / API 相关的面重新理顺，重点回答了：

1. 仓里到底有几个 repo-owned MCP server
2. ChatgptREST API、driver MCP、对外 MCP adapter 各自是什么
3. Advisor 是不是独立 MCP
4. 还有哪些“名字里带 MCP 但其实不是 server”的组件
5. 两个 repo-owned MCP 分别暴露了哪些工具

## 为什么要补这份文档

最近这套系统里最容易混淆的点有三个：

1. 把内部 driver MCP 和对外 `chatgptrest-mcp` 混成一个东西
2. 把 Advisor 误认为单独的 `advisor-mcp`
3. 继续沿用旧认知，把 `18713` 当成现网 Advisor 入口

这会直接影响：

- 外部 agent 应该接哪一层
- 故障排查时该去查哪个服务
- 文档和 runbook 是否继续传播错误端口/错误边界

## 这次的结论

1. 本仓库自己提供的 MCP server 只有 2 个：
   - 内部 driver MCP：`chatgpt-web-mcp`
   - 对外 adapter MCP：`chatgptrest`
2. Advisor 不是第三个独立 MCP server。
   - 它主要是 HTTP 能力
   - 同时通过 `chatgptrest-mcp` 暴露了一组 advisor 相关工具
3. 统一 API 入口在 `chatgptrest-api.service`，默认 `:18711`
4. `:18713` 不应再默认视为 Advisor 端口；当前环境里它常被 GitNexus MCP 占用

## 本次盘点的直接依据

代码入口：

- `chatgptrest_mcp_server.py`
- `chatgptrest_driver_server.py`
- `chatgptrest/mcp/server.py`
- `chatgpt_web_mcp/server.py`
- `chatgpt_web_mcp/_tools_impl.py`
- `chatgpt_web_mcp/tools/gemini_web.py`
- `chatgpt_web_mcp/tools/qwen_web.py`
- `chatgpt_web_mcp/tools/gemini_api.py`
- `chatgptrest/api/app.py`
- `chatgptrest/api/routes_advisor.py`
- `chatgptrest/api/routes_advisor_v3.py`
- `chatgptrest/api/routes_jobs.py`

运行与运维入口：

- `ops/start_driver.sh`
- `ops/start_mcp.sh`
- `ops/systemd/chatgptrest-driver.service`
- `ops/systemd/chatgptrest-mcp.service`
- `ops/systemd/chatgptrest-api.service`

辅助文档：

- `docs/runbook.md`
- `docs/host_profile_yogas2.md`
- `docs/audits/2026-03-16_pre_launch_baseline_audit_v2.md`
- `docs/reviews/2026-03-16_baseline_audit_independent_review_v1.md`

## 产出建议

以后再写蓝图、runbook、接入文档时，建议统一使用下面这套术语：

- `internal driver MCP`
- `ChatgptREST API`
- `ChatgptREST MCP adapter`
- `Advisor HTTP routes`
- `Advisor tool group in chatgptrest-mcp`

不要再写：

- “advisor-mcp service”
- “advisor 默认在 18713”
- “chatgptweb 和 chatgptrest mcp 是同一个服务”

