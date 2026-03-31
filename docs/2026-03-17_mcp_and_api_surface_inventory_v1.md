# ChatgptREST MCP / API Surface Inventory v1

日期：2026-03-17

## 1. 先给结论

如果只看 **本仓库自己提供的服务面**，当前应当按下面理解：

1. **repo-owned MCP server 有 2 个**
   - `chatgpt-web-mcp`：内部 driver MCP
   - `chatgptrest`：对外 MCP adapter
2. **repo-owned HTTP API app 有 1 个**
   - `chatgptrest-api.service` 提供统一 FastAPI app
3. **Advisor 不是第三个独立 MCP server**
   - Advisor 主要是 HTTP 能力，挂在 `chatgptrest-api.service` 里
   - 同时有一部分 Advisor 能力通过 `chatgptrest-mcp` 暴露成 MCP tools
4. **历史上“Advisor 在 18713”这件事现在不能当成现网事实**
   - 当前 integrated host 的主入口是 `:18711`
   - `:18713` 在这台机上常被别的 MCP 占用，尤其是 GitNexus

一句话版本：

> 现在的主结构是 `internal driver MCP (:18701)` + `ChatgptREST API (:18711)` + `ChatgptREST MCP adapter (:18712)`；Advisor 是 API 能力和 MCP tool group，不是单独的 advisor-mcp service。

## 2. 面的划分

### 2.1 Repo-owned MCP server

| 名称 | 服务/入口 | 默认地址 | 角色 | 谁调用它 |
|---|---|---|---|---|
| `chatgpt-web-mcp` | `chatgptrest-driver.service` / `chatgptrest_driver_server.py` | `http://127.0.0.1:18701/mcp` | 内部 driver MCP，直接做 ChatGPT/Gemini/Qwen Web 自动化 | worker、repair、maint、executors |
| `chatgptrest` | `chatgptrest-mcp.service` / `chatgptrest_mcp_server.py` | `http://127.0.0.1:18712/mcp` | 对外 MCP adapter，薄封装 REST API | Codex / Claude Code / 外部 agent |

### 2.2 Repo-owned HTTP API

| 名称 | 服务/入口 | 默认地址 | 角色 |
|---|---|---|---|
| ChatgptREST API | `chatgptrest-api.service` / `chatgptrest.api.app:create_app` | `http://127.0.0.1:18711` | 统一 FastAPI app，挂载 jobs、advisor、consult、issues、ops、dashboard 等路由 |

### 2.3 不是本仓库自带 server，但经常被混淆的东西

| 名称 | 性质 | 说明 |
|---|---|---|
| 外部 `chatgptMCP` | legacy 外部 MCP | runbook 里仍保留 fallback 说明，但默认不再是主路径 |
| GitNexus MCP | 外部开发工具 MCP | 当前环境里常占 `127.0.0.1:18713`，不要再把它误认成 Advisor 端口 |
| OpenClaw MCP | 外部 MCP | 本仓库只提供 client adapter，调用 `sessions_spawn` / `sessions_send` / `session_status`，并不在本仓库里实现这个 server |
| Dashboard app | HTTP app，不是 MCP | `:8787` 是独立 dashboard control plane |

## 3. Advisor 到底算什么

### 3.1 Advisor 有 HTTP

Advisor 在当前仓里有两套 HTTP 面：

1. **旧 wrapper / v1 风格**
   - `/v1/advisor/advise`
   - `/v1/advisor/runs/...`
2. **OpenMind v3 / v2 路径**
   - `/v2/advisor/advise`
   - `/v2/advisor/ask`
   - `/v2/advisor/health`
   - `/v2/advisor/trace/{id}`
   - 以及 evomap、cc-dispatch、team-control 等附属路由

这些都挂在 `chatgptrest.api.app:create_app()` 里，不需要单独起一个 `advisor-mcp` 才能工作。

### 3.2 Advisor 也有 MCP tools，但挂在 `chatgptrest-mcp` 下面

当前对外 MCP 里与 Advisor 直接相关的主要工具是：

- `chatgptrest_advisor_advise`
- `chatgptrest_advisor_ask`
- `chatgptrest_recall`
- `chatgptrest_consult`
- `chatgptrest_consult_result`

所以更准确的说法应当是：

- **Advisor 有 MCP 暴露面**
- 但 **没有独立的 advisor MCP server**

## 4. Repo-owned MCP #1：内部 driver MCP

### 4.1 这是干什么的

这个 server 的名字是 `chatgpt-web-mcp`。它不是给普通客户端直接调业务 API 用的，而是给 ChatgptREST 内部 executor/repair/maint 调具体 provider 工具的。

它聚合了 4 组 provider 工具：

1. ChatGPT Web
2. Gemini Web
3. Qwen Web
4. Gemini API

### 4.2 工具总数

- ChatGPT Web：20
- Gemini Web：12
- Qwen Web：4
- Gemini API：3
- 合计：39

### 4.3 ChatGPT Web 工具（20）

- `chatgpt_web_rate_limit_status`
- `chatgpt_web_tab_stats`
- `chatgpt_web_idempotency_get`
- `chatgpt_web_wait_idempotency`
- `chatgpt_web_answer_get`
- `chatgpt_web_conversation_export`
- `chatgpt_web_blocked_status`
- `chatgpt_web_clear_blocked`
- `chatgpt_web_self_check`
- `chatgpt_web_capture_ui`
- `chatgpt_web_ask`
- `chatgpt_web_wait`
- `chatgpt_web_refresh`
- `chatgpt_web_regenerate`
- `chatgpt_web_ask_pro_extended`
- `chatgpt_web_ask_deep_research`
- `chatgpt_web_ask_web_search`
- `chatgpt_web_ask_agent_mode`
- `chatgpt_web_ask_thinking_heavy_github`
- `chatgpt_web_create_image`

### 4.4 Gemini Web 工具（12）

- `gemini_web_ask`
- `gemini_web_self_check`
- `gemini_web_capture_ui`
- `gemini_web_ask_pro`
- `gemini_web_ask_pro_thinking`
- `gemini_web_ask_pro_deep_think`
- `gemini_web_generate_image`
- `gemini_web_deep_research`
- `gemini_web_deep_research_export_gdoc`
- `gemini_web_wait`
- `gemini_web_extract_answer`
- `gemini_web_idempotency_get`

### 4.5 Qwen Web 工具（4）

- `qwen_web_self_check`
- `qwen_web_capture_ui`
- `qwen_web_ask`
- `qwen_web_wait`

### 4.6 Gemini API 工具（3）

- `gemini_ask_pro_thinking`
- `gemini_generate_image`
- `gemini_deep_research`

### 4.7 这个 MCP 的定位边界

这个 MCP 更像是：

- provider runtime
- browser automation tool layer
- repair / self-check / evidence tool layer

它不是面向“客户端项目直接提问”的主入口。客户端应该优先走：

- ChatgptREST HTTP API
- 或 ChatgptREST MCP adapter

而不是直接碰 `chatgpt_web_*` / `gemini_web_*`。

## 5. Repo-owned MCP #2：对外 ChatgptREST MCP adapter

### 5.1 这是干什么的

这个 server 的名字是 `chatgptrest`。它是一个 **thin MCP wrapper for the ChatgptREST REST contract**，主要职责是：

- 帮 MCP 客户端调用 `/v1/jobs/*`
- 帮客户端拿答案/result
- 暴露 advisor / consult / repair / issues / ops 的统一工具面

### 5.2 工具总数

- Jobs：11
- Advisor：2
- Ask / Result：9
- Repair / SRE：4
- Ops：9
- Issues：13
- Consult：2
- KB：1
- 合计：51

### 5.3 Jobs 工具（11）

- `chatgptrest_job_create`
- `chatgptrest_job_get`
- `chatgptrest_job_wait`
- `chatgptrest_job_wait_background_start`
- `chatgptrest_job_wait_background_get`
- `chatgptrest_job_wait_background_list`
- `chatgptrest_job_wait_background_cancel`
- `chatgptrest_job_cancel`
- `chatgptrest_job_events`
- `chatgptrest_answer_get`
- `chatgptrest_conversation_get`

### 5.4 Advisor 工具（2）

- `chatgptrest_advisor_advise`
- `chatgptrest_advisor_ask`

说明：

- `chatgptrest_advisor_advise` 更偏 wrapper v1
- `chatgptrest_advisor_ask` 是智能路由入口，自动决定 quick_ask / deep_research / report / funnel

### 5.5 Ask / Result 工具（9）

- `chatgptrest_ask`
- `chatgptrest_result`
- `chatgptrest_followup`
- `chatgptrest_chatgpt_ask_submit`
- `chatgptrest_gemini_ask_submit`
- `chatgptrest_qwen_ask_submit`
- `chatgptrest_gemini_generate_image_submit`
- `chatgptrest_gemini_extract_answer`
- `chatgptrest_chatgpt_extract_answer`

说明：

- `chatgptrest_ask` + `chatgptrest_result` 是当前统一主路径
- `*_ask_submit` 里有一部分是兼容/过渡工具

### 5.6 Repair / SRE 工具（4）

- `chatgptrest_repair_check_submit`
- `chatgptrest_repair_autofix_submit`
- `chatgptrest_sre_fix_request_submit`
- `chatgptrest_repair_open_pr_submit`

### 5.7 Ops 工具（9）

- `chatgptrest_ops_pause_get`
- `chatgptrest_ops_pause_set`
- `chatgptrest_ops_status`
- `chatgptrest_ops_incidents_list`
- `chatgptrest_ops_incident_get`
- `chatgptrest_ops_incident_actions_list`
- `chatgptrest_ops_events`
- `chatgptrest_ops_idempotency_get`
- `chatgptrest_ops_jobs_list`

### 5.8 Issue Ledger 工具（13）

- `chatgptrest_issue_report`
- `chatgptrest_issue_list`
- `chatgptrest_issue_get`
- `chatgptrest_issue_update_status`
- `chatgptrest_issue_link_evidence`
- `chatgptrest_issue_events`
- `chatgptrest_issue_record_verification`
- `chatgptrest_issue_list_verifications`
- `chatgptrest_issue_record_usage`
- `chatgptrest_issue_list_usage`
- `chatgptrest_issue_graph_query`
- `chatgptrest_issue_digest`
- `chatgptrest_issue_auto_link_repair`

### 5.9 Consult / KB 工具（3）

- `chatgptrest_consult`
- `chatgptrest_consult_result`
- `chatgptrest_recall`

### 5.10 这个 MCP 的定位边界

这个 MCP 才是外部 coding agent 最应该用的 MCP 面，因为它表达的是：

- jobs contract
- result contract
- advisor contract
- issues / ops / repair contract

而不是具体浏览器点击细节。

## 6. HTTP API 面：哪些不是 MCP

当前最容易混淆的是：很多能力其实是 HTTP route，不是 MCP tool。

### 6.1 `/v1/jobs/*`

核心 jobs API：

- `POST /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `GET /v1/jobs/{job_id}/wait`
- `GET /v1/jobs/{job_id}/events`
- `GET /v1/jobs/{job_id}/answer`
- `GET /v1/jobs/{job_id}/conversation`
- `GET /v1/jobs/{job_id}/stream`
- `POST /v1/jobs/{job_id}/cancel`

### 6.2 `/v1/advisor/*`

旧 wrapper 风格：

- `POST /v1/advisor/advise`
- `GET /v1/advisor/runs/{run_id}`
- `POST /v1/advisor/runs/{run_id}/reconcile`
- `GET /v1/advisor/runs/{run_id}/events`
- `GET /v1/advisor/runs/{run_id}/replay`
- `POST /v1/advisor/runs/{run_id}/takeover`
- `GET /v1/advisor/runs/{run_id}/artifacts`

### 6.3 `/v2/advisor/*`

OpenMind v3 主入口：

- `POST /v2/advisor/advise`
- `POST /v2/advisor/ask`
- `GET /v2/advisor/health`
- `GET /v2/advisor/trace/{trace_id}`
- `GET /v2/advisor/run/{run_id}`
- `POST /v2/advisor/webhook`
- 以及 `evomap/*`、`cc-*`、`dashboard`、`insights`、`routing-stats` 等附属能力

### 6.4 `/v1/advisor/consult` 和 `/v1/advisor/recall`

虽然名字里带 advisor，但本质上仍是 HTTP route，MCP 只是额外提供了对应包装：

- `POST /v1/advisor/consult`
- `GET /v1/advisor/consult/{consultation_id}`
- `POST /v1/advisor/recall`

### 6.5 Dashboard 也不是 MCP

- `chatgptrest.api.app_dashboard:create_app`
- `http://127.0.0.1:8787`
- 是 read-only dashboard control plane
- 不属于 MCP server

## 7. 其他“和 MCP 有关但不是 MCP server”的代码层

这些东西名字里有 MCP，但它们不是新的 server：

### 7.1 driver backend

- `chatgptrest/driver/backends/mcp_http.py`
- `chatgptrest/driver/backends/embedded.py`
- `chatgptrest/driver/factory.py`

它们只是决定 worker/executor 通过：

- HTTP 调内部/外部 MCP
- 还是直接 embedded 调工具实现

### 7.2 MCP LLM bridge

- `chatgptrest/kernel/mcp_llm_bridge.py`

它是给 routing / advisor 用的统一调用桥，把：

- `chatgpt-web`
- `gemini-web`
- `gemini-cli`

包装成统一 LLM 调用接口。它不是一个 MCP server。

### 7.3 OpenClaw MCP adapter

- `chatgptrest/integrations/openclaw_adapter.py`

它只是一个 **client adapter**，当前直接调用的外部工具是：

- `sessions_spawn`
- `sessions_send`
- `session_status`

这说明系统里还会“消费别人的 MCP”，但这些工具不是本仓库自己实现的。

## 8. 当前推荐的口径

以后如果要对内或对外描述，建议统一成下面这套说法：

### 8.1 最短版

> ChatgptREST 现在有两个 MCP server：内部 driver MCP 和对外 ChatgptREST MCP；另外有一个统一 HTTP API。Advisor 不是单独 MCP，而是 API 能力，并通过 chatgptrest-mcp 暴露了 advisor 相关工具。

### 8.2 端口版

- 内部 driver MCP：`127.0.0.1:18701/mcp`
- ChatgptREST API：`127.0.0.1:18711`
- ChatgptREST MCP adapter：`127.0.0.1:18712/mcp`
- Dashboard：`127.0.0.1:8787`
- `18713` 不应再默认说成 Advisor 端口

### 8.3 客户端接入版

- 普通客户端优先接 `chatgptrest-mcp`
- 需要 HTTP 时接 `chatgptrest-api`
- 不要直接调内部 driver MCP，除非你在做 runtime / repair / provider 级开发

## 9. 这份盘点的直接证据

核心入口文件：

- `chatgptrest_mcp_server.py`
- `chatgptrest_driver_server.py`
- `chatgptrest/mcp/server.py`
- `chatgpt_web_mcp/server.py`
- `chatgpt_web_mcp/_tools_impl.py`
- `chatgpt_web_mcp/tools/gemini_web.py`
- `chatgpt_web_mcp/tools/qwen_web.py`
- `chatgpt_web_mcp/tools/gemini_api.py`
- `chatgptrest/api/app.py`
- `chatgptrest/api/routes_jobs.py`
- `chatgptrest/api/routes_advisor.py`
- `chatgptrest/api/routes_advisor_v3.py`
- `chatgptrest/api/routes_consult.py`
- `ops/start_driver.sh`
- `ops/start_mcp.sh`
- `ops/systemd/chatgptrest-driver.service`
- `ops/systemd/chatgptrest-mcp.service`
- `ops/systemd/chatgptrest-api.service`

辅助校验文档：

- `docs/runbook.md`
- `docs/host_profile_yogas2.md`
- `docs/audits/2026-03-16_pre_launch_baseline_audit_v2.md`
- `docs/reviews/2026-03-16_baseline_audit_independent_review_v1.md`

