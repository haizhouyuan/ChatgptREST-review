# ChatgptREST RCA: 外部取消 + Gemini Deep Think 不可用（2026-02-24）

## 1) 结论

- 两条 ChatGPT Pro 任务（`06b7a2f8...`、`d3bcb676...`）均为**外部主动取消**，非 worker 自动终态。
- Gemini `deep_think` 失败（`f9418cf3...`）是**UI 变体/能力可用性漂移**导致：工具匹配不到 `Deep Think`，但页面存在 `Thinking with 3 Pro` 变体信号。
- `Gemini Pro` 兜底任务（`59a13af1...`）可正常完成，说明基础链路可用，问题聚焦在 deep_think 选择与降级策略。

## 2) 关键证据

### 2.1 ChatGPT Pro 两条任务被外部取消

- `06b7a2f8a4214047a7a2fbf015d7b259`
  - 事件链：`prompt_sent -> phase=wait -> conversation_exported -> cancel_requested -> canceled`
  - `cancel_requested.by.headers`：
    - `user_agent=chatgptrest-mcp/0.1.0`
    - `x_client_name=chatgptrest-mcp`
    - `x_client_instance=YogaS2-pid3399683`
    - `x_request_id=chatgptrest-mcp-3399683-19c8df1e56b-397-ae86d086`
- `d3bcb676c2034b0eb33ec770b60e3714`
  - 事件链：`in_progress(send) -> cancel_requested -> canceled`
  - 同一调用源：`x_client_instance=YogaS2-pid3399683`

### 2.2 Gemini Deep Think 失败原因

- `f9418cf3befe42a29f1246a7c223cd49`
  - `status=error`
  - `reason_type=GeminiDeepThinkToolNotFound`
  - `reason=Gemini tool not found: (Deep\\s*Think|深度思考|深入思考)`
- Debug 文本快照显示页面为 Gemini 首页且可见：
  - `工具`
  - `Pro`
  - 同时 HTML 中可检索到 `Thinking with 3 Pro` 文案（变体信号）。

### 2.3 复发性

- issue：`iss_7aa84dae56e647509e1dc7ab4eeff88c`
  - 指纹：`geminideepthinktoolnotfound`
  - 非首次，曾自动缓解后再次复发（`reopened=true`）。

## 3) 根因归纳

- 根因 A（取消）：上游客户端在执行中显式调用了 `/cancel`，非 ChatgptREST 自发取消。
- 根因 B（Deep Think）：Gemini UI/文案与能力入口有漂移，`Deep Think` 选择器过于固定，且失败时缺少“自动降级到 Pro”闭环。

## 4) 已实施修复

### 4.1 取消护栏（防误取消）

- API 新增 `/cancel` 专用 allowlist：
  - `CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST`
  - 路由：`chatgptrest/api/routes_jobs.py`
- 保留既有“mcp down 才允许 fallback 客户端”的逻辑。
- 运行配置已落地：
  - `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env`
  - `CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST=chatgptrestctl`

### 4.2 Deep Think 选择与降级增强

- 扩展 Deep Think 标签匹配，支持变体：
  - `Deep Think`
  - `Thinking with 3 Pro`
  - `深度思考/深入思考`
- 当 `deep_think` 出现不可用类错误（如 `GeminiDeepThinkToolNotFound`）时，自动降级到 `pro`（可配置，默认开启）。

## 5) 验证结果

- 单测：
  - `tests/test_gemini_deep_think_overloaded.py`：通过（新增 deep_think-unavailable 降级覆盖）
  - `tests/test_gemini_mode_selector_resilience.py`：通过（新增 `Thinking with 3 Pro` 匹配覆盖）
  - `tests/test_client_name_allowlist.py`：通过（新增 cancel allowlist 行为覆盖）
  - `tests/test_cancel_attribution.py`、`tests/test_mcp_trace_headers.py`：通过
- 运行态：
  - API/worker(send)/worker(wait) 已重启并 active。
  - `/cancel` 护栏验证：
    - `X-Client-Name: chatgptrest-mcp` -> `cancel_client_not_allowed`
    - `X-Client-Name: chatgptrestctl`（MCP up）-> `client_not_allowed`（仅 mcp down fallback）

## 6) 避免再发（制度化）

- 对取消操作执行“最小权限”：
  - `/cancel` 独立 allowlist，不再与“提交权限”共用。
- 对 Deep Think 执行“失败即降级”：
  - 不可用/入口漂移时自动走 Pro，避免整任务失败。
- 对证据执行“强追踪”：
  - 统一保留 `x_client_instance + x_request_id`，用于一跳定位。

## 7) 未决项

- 在线验证作业 `40f758a266974e0c9b05ee392e64ab14` 处于 `queued`（foreground wait 已禁用，后台 watch 模式）。
- 若需立即清理该验证作业，可在维护窗口按允许客户端策略执行取消。

