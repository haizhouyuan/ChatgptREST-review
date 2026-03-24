# Production Readiness Fix Review — PR #122 (ChatgptREST) + PR #11 (OpenClaw)

**Reviewer**: Antigravity  
**Date**: 2026-03-11  
**Branches**: `codex/prod-readiness-fixes-20260311`  
**Scope**: All code changes in both PRs —逐项审查

---

## 总结

| 类别 | 条目数 |
|------|--------|
| 🔴 必须修复 (HIGH) | 4 |
| 🟡 建议修复 (MEDIUM) | 5 |
| 🟢 可选改进 (LOW) | 3 |

---

## 🔴 HIGH — 必须修复

### H1. cc-control 访问控制绑到所有 `/v2/advisor` 路由上了

**文件**: `chatgptrest/api/routes_advisor_v3.py`  
**问题**: `_require_cc_control_access` 作为全局 `dependencies` 注入到整个 `/v2/advisor` router：

```python
router = APIRouter(
    prefix="/v2/advisor",
    dependencies=[Depends(_require_openmind_auth), Depends(_require_openmind_rate_limit), Depends(_require_cc_control_access)],
)
```

虽然 `_require_cc_control_access` 内部有 `if not path.startswith("/v2/advisor/cc-"): return` 提前退出，但这意味着 **每个 `/v2/advisor` 请求都要跑这个 dependency**。问题不在于性能（成本微乎其微），而在于：

1. **函数依靠路径字符串匹配做门控**——如果以后有人加一个路径恰好以 `cc-` 开头但不是 control plane（如 `/v2/advisor/cc-summary`），会被意外拦截。
2. **更严重的是 `get_client_ip` 在 TestClient 下行为不确定**。当没有 `OPENMIND_CONTROL_API_KEY` 时，cc 路由回退到 loopback 检测，但 `get_client_ip(request)` 在 TestClient / ASGI 内存传输下返回的 `client.host` 通常是 `testclient` 或 `None`，不是 `127.0.0.1`。测试 `test_cc_routes_default_to_loopback_only` 通过恰恰是因为 TestClient 不是 loopback，所以被拦截了——但这也意味着 **生产环境从 localhost curl 时，必须确保 `request.client.host` 确实返回 `127.0.0.1`**。如果跑在反向代理后面且信任了 `X-Forwarded-For`，`get_client_ip` 可能返回外部 IP 而打开了 cc-control 的安全口。

**建议**: 
- 把 `_require_cc_control_access` 只挂在实际的 `cc-*` 路由上（每个路由单独 `dependencies=[Depends(...)]`），而不是 router 全局。
- 或者把 cc-control 路由拆进独立的 sub-router。
- 对 loopback fallback 做 hardening：保证 `get_client_ip` 在无 control key 时, 对 cc- 路由不走 trusted proxy 剥离，直接用 `request.client.host` raw 值。

---

### H2. advisor `/v2/advisor/ask` 自动幂等键包含 `context` 但 context 可变

**文件**: `chatgptrest/api/routes_advisor_v3.py` — `_advisor_ask_auto_idempotency_key`  
**问题**: 自动生成的幂等键依赖 `context` dict 的 JSON hash，但 context 是调用方自由传入的。如果 OpenClaw plugin 每次在 context 中注入不同的 `session_key`（它确实会这样做——参看 `index.ts` 中 `buildIdempotencyKey` 也包含 context），那么 **同一个问题 + 不同的 context → 不同的幂等键 → 不再具有去重能力**。

这在以下场景会出问题：

- OpenClaw plugin 自己算了 `idempotency_key` 并传入 `body.idempotency_key`——没问题，不走 auto。
- 但如果有 **非 OpenClaw 的直接 API client**（如 MCP tool `chatgptrest_advisor_ask`），不传 `idempotency_key`，且 context 里包含时间戳/trace_id 等动态值，则去重完全失效。

**建议**: 
- 在 auto key 中排除已知的高频变化字段（如 `session_key`, `agent_id`, `trace_id`），或只用 `question + role_id + user_id + minute_bucket` 做关键指纹。
- 文档明确要求：如果 context 包含动态字段，client **必须** 自行传入 `idempotency_key`。

---

### H3. OpenClaw `normalizeTrustedProxyEntry` 对非单主机 CIDR 静默丢弃

**文件**: `openclaw/src/gateway/net.ts`  
**问题**: `normalizeTrustedProxyEntry` 在发现不是 `/32` 或 `/128` 时返回 `undefined`，而 `isTrustedProxyAddress` 中 `normalizeTrustedProxyEntry(proxy) === normalized` 会变成 `undefined === "127.0.0.1"` 即 `false`。

这意味着 **如果用户在 `openclaw.json` 中配置了 `trustedProxies: ["10.0.0.0/8"]`，这个 CIDR 会被完全忽略，不会有任何警告或错误**。这是一个安全决策——故意只接受单主机——但完全静默，没有 log 也没有启动时 warning。如果运维人员从旧版本升级，之前能工作的 CIDR 配置会悄无声息失效，导致 `X-Forwarded-For` 不再被信任→客户端 IP 全部变成代理 IP→鉴权逻辑破坏。

**建议**: 
- 在 `normalizeTrustedProxyEntry` 返回 `undefined` 的 broad CIDR 分支中加 `console.warn` / logger。
- 或者在 OpenClaw 启动时校验 config 并报告哪些 trusted proxy 条目被忽略了。

---

### H4. OpenClaw plugin identity 透传中 `agentAccountId` 默认回退到 `"openclaw"`

**文件**: `openclaw_extensions/openmind-advisor/index.ts`  
**问题**: 

```typescript
const userId = String(ctx?.agentAccountId ?? ctx?.agentId ?? "openclaw").trim() || "openclaw";
```

如果 `ctx` 存在但 `agentAccountId` 和 `agentId` 都是空字符串，`String("")` → `""` → `.trim()` → `""` → `|| "openclaw"` → `"openclaw"`。这个逻辑是对的。

但 **`userId` 被直接传到 ChatgptREST `/v2/advisor/ask` 的 `user_id` 字段**，进而用于：
- Langfuse 追踪
- 幂等键生成
- EvoMap 信号
- KB writeback 审计

如果多个 OpenClaw agent 都回退到 `"openclaw"` 这个 userId，它们的请求可能因为同一分钟内问同一个问题而产生 **幂等键冲突**（因为 `buildIdempotencyKey` 也用了 `userId`，但两个不同 agent 都是 `"openclaw"` + 同样的问题 → 同样的 key → 第二个请求会被吞掉）。

**建议**: 
- 当 `userId` 回退到 `"openclaw"` 时，拼上 `sessionId` 或 `agentId` 的非空部分做区分。例如 `"openclaw:" + (agentId || sessionId.slice(0,8) || "anon")`。

---

## 🟡 MEDIUM — 建议修复

### M1. `readyz` 端点没有 auth

**文件**: `chatgptrest/api/routes_jobs.py`  
**问题**: `/readyz` 注册在 `make_router(cfg)` 返回的 router 中，走 `app.py` 里的全局 bearer auth middleware。但 `/readyz` 是标准的 K8s 探针端点——需要 unauthenticated 访问。如果运维配置了 `CHATGPTREST_API_TOKEN`，kubelet 调 `/readyz` 会被 401 拒绝。

当前 `/healthz` 和 `/health` 也存在同样问题。

**建议**:
- 在 `_is_global_bearer_auth_exempt_path` 中添加 `/healthz`、`/readyz`、`/health` 的豁免。
- 或者把探针路由直接注册到 app 上而不是走 auth router。

---

### M2. guardian `_chatgptrest_auth_headers` 仅按 URL 路径前缀选 token，没有 fallback

**文件**: `ops/openclaw_guardian_run.py`  
**问题**: 当只设置了 `CHATGPTREST_OPS_TOKEN` 没设 `CHATGPTREST_API_TOKEN` 时，非 `/v1/ops/` 路径（如 `/healthz`, `/v1/issues`）会用空的 `api_token`，fallback 到 `ops_token`。这个 fallback 逻辑本身是对的。

但如果 **两个 token 都没设**，`_chatgptrest_auth_headers` 返回空 dict，请求不带 auth。而 API 侧如果配了 token 就会 401。这时 guardian 的 `_http_json` 会返回 `(False, error)`，但 guardian 不会 crash——只是报告检查失败。这是可接受的降级行为，但 **缺少明确的启动时 warning**。

**建议**: guardian `_collect_report` 开头加一行 `if not os.environ.get("CHATGPTREST_API_TOKEN") and not os.environ.get("CHATGPTREST_OPS_TOKEN"): log.warning(...)`。

---

### M3. OpenClaw idempotencyKey 的 `minuteBucket` 与 ChatgptREST 的 `int(time.time()) // 60` 可能不一致

**文件**: `openclaw_extensions/openmind-advisor/index.ts` + `chatgptrest/api/routes_advisor_v3.py`  
**问题**: OpenClaw plugin 用 `Math.floor(Date.now() / 60000)` 生成 minuteBucket，ChatgptREST  auto key 用 `int(time.time()) // 60`。如果两个进程的系统时钟存在几秒偏差，在分钟边界附近，OpenClaw 算出来的 bucket N 对应 ChatgptREST 侧的 bucket N-1 或 N+1，导致 **幂等键不匹配→OpenClaw 认为是同一分钟的重复，ChatgptREST 认为是新请求**。

实际影响有限（因为 OpenClaw 自己算了 key 传过去，ChatgptREST 不会用 auto key），但如果将来有人从 OpenClaw 发请求时不传 `idempotency_key`，这个不一致会暴露。

**建议**: 文档注明 OpenClaw plugin **始终必须**生成 `idempotency_key`，不能依赖服务端 auto。

---

### M4. `openclaw_adapter.py` 环境变量名拼写 `CHATGPTREST_OPENCLOW` (少了一个 A)

**文件**: `chatgptrest/integrations/openclaw_adapter.py`  
**问题**: 

```python
os.environ.get("CHATGPTREST_OPENCLOW_ALLOW_REMOTE_MCP_URL")
os.environ.get("CHATGPTREST_OPENCLOW_MCP_URL")
```

`OPENCLOW` 而不是 `OPENCLAW`。这看起来像 typo，但可能是遗留命名。如果是刻意的——需要文档化。如果是 typo——会导致用户设了正确的 `CHATGPTREST_OPENCLAW_*` 但没生效。

**建议**: 确认是否是 typo。如果是，修正所有环境变量引用并保留旧名作为 deprecated alias。

---

### M5. OpenClaw session tool gating 新增了 `sessionId`/`agentAccountId` 但传播路径不完整

**文件**: `openclaw/src/plugins/types.ts`, `src/agents/tools/sessions-*-tool.ts`  
**问题**: `PluginHookToolContext`, `PluginHookAgentContext`, `PluginHookToolResultPersistContext` 都加了 `sessionId` 和 `agentAccountId`，但从 diff 中看，实际的 tool 调用代码（如 `sessions-spawn-tool.ts`）传入的 context 是否包含这两个字段取决于上游（pi-tools.ts 等）是否填充了它们。如果上游没传，这些字段就是 `undefined`。

从 diff 中 `src/agents/pi-tools.before-tool-call.ts` 和 `src/agents/pi-tools.ts` 只加了对新 context 字段的 `+` 行但不带实际赋值逻辑——需要确认运行时 context 是否真的被正确填充。

**建议**: 加一个 integration test 确认 plugin context 中 `sessionId` 和 `agentAccountId` 不是 undefined。

---

## 🟢 LOW — 可选改进

### L1. `_stable_json_hash` 用 SHA-256 生成指纹但 OpenClaw 用 SHA-1

ChatgptREST 侧用 `hashlib.sha256`，OpenClaw `buildIdempotencyKey` 用 `createHash("sha1")`。不影响正确性（各自用各自的），但不一致增加维护负担。

### L2. guardianrunner 多处拼接 URL 可提取到公共函数

guardian 中 `f"{base_url.rstrip('/')}/v1/issues/{...}/status"` 模式重复了 4+ 次，建议提取 `_api_url(base_url, path)` helper。

### L3. OpenClaw config compat test 直接 import `validateConfigObject` 而不是通过 public API

test 中 `await import("./config.js")` 直接引用内部函数，如果 `config.ts` 重构导出名会导致 test 崩溃。但这是 test 惯例，不严重。

---

## 已确认正确的改动

| 改动 | 判定 |
|------|------|
| `/v2/` 路径豁免全局 bearer auth（`app.py`） | ✅ 正确——v2 有独立的 OpenMind auth |
| `openclaw_mcp_url` loopback 限制（`openclaw_adapter.py`） | ✅ 安全加固正确 |
| advisor ask 捕获 `IdempotencyCollision` 返回 409（`routes_advisor_v3.py`） | ✅ 正确 |
| advisor ask `input_obj` 丰富化（fingerprint, user_id, session_id 等） | ✅ 审计可追溯性改善 |
| guardian 所有 HTTP 调用加 auth header（`openclaw_guardian_run.py`） | ✅ 生产必需 |
| OpenClaw trusted proxy 只接受单主机 CIDR（`net.ts`） | ✅ 安全正确，但需要加 warning（见 H3） |
| OpenClaw plugin session context 透传（`plugins/types.ts`） | ✅ 方向正确 |
| 新增 Zod schema 字段兼容生产 config（`zod-schema*.ts`） | ✅ 正确 |
| acpx + diffs plugins 恢复 | ✅ 正确（bundled plugins 归位） |
| readyz 端点（DB 连接 + driver port 探测） | ✅ 实现正确（auth 问题见 M1） |
| 所有新增测试 | ✅ 覆盖了核心逻辑 |

---

## 优先级排序

| 序号 | 修复项 | 预估工作量 |
|------|--------|------------|
| 1 | M1: readyz/healthz auth 豁免 | 5 分钟 |
| 2 | H3: trusted proxy 静默丢弃加 warning | 10 分钟 |
| 3 | H1: cc-control dependency 范围收窄 | 15 分钟 |
| 4 | M4: OPENCLOW typo 确认/修复 | 5 分钟 |
| 5 | H2: auto idempotency key context 过敏 | 15 分钟 |
| 6 | H4: `"openclaw"` userId 去重碰撞 | 10 分钟 |
| 7 | M2: guardian 启动时无 token warning | 5 分钟 |
| 8 | M3: minuteBucket 一致性文档 | 5 分钟 |
