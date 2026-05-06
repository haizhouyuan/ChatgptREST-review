# Advisor Path Convergence Walkthrough v1

**日期**: 2026-03-12  
**分支**: `codex/advisor-path-convergence-20260312`  
**目标**: 收敛 OpenMind advisor 请求元数据、显式暴露 runtime degraded 状态、把 OpenClaw `openmind-advisor` 插件调整为更适合长任务的 async 契约，并补上 Feishu WS trace/context 透传。

---

## 做了什么

### 1. 收敛 `/v2/advisor/advise` 与 `/v2/advisor/ask` 的 request metadata

在 `chatgptrest/api/routes_advisor_v3.py` 中新增统一的 `request_metadata` 回传：

- `trace_id`
- `session_id`
- `account_id`
- `thread_id`
- `agent_id`
- `role_id`
- `user_id`
- `intent_hint`
- `idempotency_key`
- `request_fingerprint`
- `timeout_seconds`
- `max_retries`
- `quality_threshold`

影响：

- `advise` 成功与错误响应都可直接看到请求元数据
- `ask` 的 KB direct、job submitted、idempotency collision、routing error、job creation failure 全部带统一 metadata echo
- `ask` 支持显式 `trace_id`

### 2. 显式暴露 advisor runtime degraded 状态

在 `/v2/advisor/health` 中新增：

- `subsystems.llm`
- `subsystems.routing`
- `degradation`

当前策略：

- 当 runtime 使用 mock LLM（`QWEN_API_KEY` 未配置，走 KB-only stub）时，`health.status=degraded`
- degraded 信息结构化返回，便于监控和运维面消费

### 3. 收口 `/v2/advisor/ask` 的错误暴露

对 `job_creation_failed` 等错误分支：

- 保留 `error` 和 `error_type`
- 去掉原始 traceback 回传
- 改为结构化 `degradation` 信息

### 4. OpenClaw `openmind-advisor` 插件改为 async-first

在 `openclaw_extensions/openmind-advisor/index.ts` 中：

- 默认 `defaultMode` 从 `advise` 改为 `ask`
- 新增 `waitForCompletion`
- 新增 `pollIntervalSeconds`
- 新增 `jobWaitTimeoutSeconds`
- `mode=ask` 时可轮询 `/v1/jobs/{job_id}/wait`
- 任务完成后会继续抓取 `/v1/jobs/{job_id}/answer`
- 结果文本补充 `status / trace / conversation`

这使插件不再只适配“立即同步返回”的路径，更适合 report / deep research / 长时任务。

### 5. Feishu WS 入口补 trace/context

在 `chatgptrest/advisor/feishu_ws_gateway.py` 中：

- 向 `/v2/advisor/advise` 透传 `trace_id`
- 透传 `account_id / thread_id / agent_id`
- 追加 `context.channel / context.chat_id / context.message_id`
- 回包显示 `trace`
- 若 advisor 返回 `degradation`，会在 Feishu 文本中显式提示

---

## 为什么这样做

本轮不追求“大一统重构”，而是优先解决审查里最影响交付的三类问题：

1. 入口不一致：不同入口返回的 metadata 不统一，排障成本高  
2. 健康口径偏乐观：mock LLM 与 degraded runtime 没有显式暴露  
3. OpenClaw 插件不适合长任务：默认同步模式 + ask 不等待，导致使用体验和契约都不稳定

因此这条 PR 的策略是：

- 不大拆架构
- 尽量只加字段、不改主字段语义
- 通过 additive contract 把调试/观测/长任务体验先补平

---

## 提交记录

- `4bcb489` `docs: add advisor path convergence worklog`
- `b73e00e` `feat: surface advisor request metadata and health degradation`
- `4eefcf6` `feat: harden openmind advisor plugin async flow`

---

## 验证

执行过的验证：

- `python3 -m py_compile chatgptrest/api/routes_advisor_v3.py tests/test_advisor_v3_end_to_end.py tests/test_routes_advisor_v3_security.py`
- `python3 -m py_compile chatgptrest/advisor/feishu_ws_gateway.py tests/test_feishu_ws_gateway.py tests/test_openclaw_cognitive_plugins.py`
- `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py tests/test_routes_advisor_v3_security.py`
- `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_openclaw_cognitive_plugins.py tests/test_feishu_ws_gateway.py`
- `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py tests/test_routes_advisor_v3_security.py tests/test_openclaw_cognitive_plugins.py tests/test_feishu_ws_gateway.py`

结果：

- 全部通过
- 有 `lark_oapi / websockets` 的上游 deprecation warnings，但本轮未新增失败

---

## 已知限制

- 当前 worktree 没有本地 `./node_modules/.bin/tsc`，因此本轮没有跑 TypeScript 编译检查
- 这条 PR 解决的是“契约收敛 + 入口硬化”，不是完整的 runtime 统一重构
- FinAgent 相关问题保留在审查文档，不在本 PR 范围内
