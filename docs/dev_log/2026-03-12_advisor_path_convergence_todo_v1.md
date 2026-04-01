# Advisor Path Convergence Todo v1

**日期**: 2026-03-12  
**分支**: `codex/advisor-path-convergence-20260312`  
**目标**: 收敛 OpenMind advisor 入口、修正 OpenClaw 长任务接入行为、补齐 health 退化信号，并为后续 PR 保留完整开发记忆面。

---

## 范围

- OpenMind advisor API 路径收敛
- OpenClaw `openmind-advisor` 扩展的长任务行为对齐
- health / runtime 退化显式化
- 相关测试、文档、walkthrough、PR 说明

---

## 主 checklist

- [x] 复核目标代码路径并在修改前完成 GitNexus impact
- [x] 明确 `/v2/advisor/advise`、`/v2/advisor/ask`、Feishu WS、OpenClaw extension 的分流关系
- [x] 实现 advisor ask 路由和元数据收敛
- [x] 实现 OpenClaw 长任务等待 / 轮询 / 返回契约改进
- [x] 在 health 中显式暴露 LLM readiness / mock mode / degraded state
- [x] 补 targeted tests
- [x] 补 walkthrough / PR summary
- [ ] 跑 closeout

---

## 工作日志

### 2026-03-12T00:00 初始建档

- 建立独立 worktree，避免当前主工作树脏改动混入本次 PR
- 本任务以“单条可交付主线 PR”为约束，不尝试在一个 PR 内跨仓修复 FinAgent
- FinAgent 相关问题保留在审查文档中，当前实现聚焦 ChatgptREST/OpenMind/OpenClaw 同仓改造

### 2026-03-12T01:00 API/health 第一批收敛

- `routes_advisor_v3.py` 新增 `request_metadata` 回传，覆盖 `advise` / `ask` 成功与错误分支
- `/v2/advisor/ask` 接受显式 `trace_id`，并把 `max_retries` / `quality_threshold` 收进作业参数
- 去掉 `job_creation_failed` 错误返回里的 traceback 暴露，改为结构化 `error_type + degradation`
- `/v2/advisor/health` 显式暴露 `llm` 和 `routing` 子系统，并在 mock LLM 场景返回 `status=degraded`
- 定向验证通过：
  - `python3 -m py_compile chatgptrest/api/routes_advisor_v3.py tests/test_advisor_v3_end_to_end.py tests/test_routes_advisor_v3_security.py`
  - `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py tests/test_routes_advisor_v3_security.py`

### 2026-03-12T02:00 OpenClaw plugin + Feishu WS 收敛

- `openmind-advisor` 插件默认模式改为 `ask`，并新增 `waitForCompletion / pollIntervalSeconds / jobWaitTimeoutSeconds`
- 插件在 `mode=ask` 时可轮询 `/v1/jobs/{job_id}/wait` 并在完成后抓取 `/v1/jobs/{job_id}/answer`
- 插件结果文本补充 `status / trace / conversation`
- Feishu WS 调用 `/v2/advisor/advise` 时补齐 `trace_id / account_id / thread_id / agent_id / context`
- Feishu WS 回包新增 `degradation` 提示和 `trace` footer，便于后续排障
- 定向验证通过：
  - `python3 -m py_compile chatgptrest/advisor/feishu_ws_gateway.py tests/test_feishu_ws_gateway.py tests/test_openclaw_cognitive_plugins.py`
  - `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_openclaw_cognitive_plugins.py tests/test_feishu_ws_gateway.py`
- 额外说明：
  - 当前 worktree 没有本地 `./node_modules/.bin/tsc`，因此本轮未执行 TypeScript 编译检查

---

## 提交日志

- `6e5a73f` `docs: add advisor path convergence worklog`
- `efb5870` `feat: surface advisor request metadata and health degradation`
- `4fcaf7c` `feat: harden openmind advisor plugin async flow`
- 待提交：walkthrough / PR closeout

---

## 备注

- 若后续发现 `/v2/advisor/ask` 与 Feishu WS 的耦合超出单 PR 可控范围，优先保证 API 契约和 OpenClaw 接入一致性，其次再做 Feishu 路径统一。
