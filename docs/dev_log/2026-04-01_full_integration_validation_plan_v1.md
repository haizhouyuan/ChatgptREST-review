# 2026-04-01 全量集成测试与修复计划 v1

更新时间：2026-04-01
适用分支：`ccrunner/full-integration-validation-20260401`
基线提交：`f2283ae4`

## 目标

在最新 `origin/master` 的统一快照上，对最近已合并的四条主线做一次严格的全量集成验证，并在发现问题时立即修复，直到验收集合全部通过：

1. Task Runtime / Agent Harness foundation
2. Repo cognition / bootstrap / obligations / closeout
3. opencli / CLI-Anything integration
4. 这三条线与现有 delivery / promotion / CLI / MCP / finbot 相关面的相容性

## 原则

- 不接受“局部测试绿了但联合回归未跑”。
- 不接受“Claude 自报通过”作为验收依据，必须留下命令、日志与结果文档。
- 不接受“测试失败先跳过”；若失败，优先修代码或修测试环境，直到同一套验收集合通过。
- 不接受扩大口径；如果某一层只做到 foundation / runtime tranche，就按真实完成范围描述。
- 不接受污染主工作树；所有修复与验证只在本隔离 worktree 内进行。

## 验收范围

### A. 主线联合回归

必须跑通以下测试集合：

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_task_runtime.py \
  tests/test_task_runtime_harness.py \
  tests/test_promotion_engine.py \
  tests/test_execution_delivery_gate.py \
  tests/test_api_provider_delivery_gate.py \
  tests/test_public_agent_effects_delivery_validation.py \
  tests/test_finbot.py \
  tests/test_llm_connector.py \
  tests/test_opencli_policy.py \
  tests/test_opencli_executor.py \
  tests/test_cli_anything_market_manifest.py \
  tests/test_routes_agent_v3_opencli_lane.py \
  tests/test_import_skill_market_candidates.py \
  tests/test_repo_cognition_gitnexus_adapter.py \
  tests/test_repo_cognition_runtime.py \
  tests/test_chatgptrest_bootstrap.py \
  tests/test_doc_obligations.py \
  tests/test_chatgptrest_closeout.py \
  tests/test_health_probe.py \
  tests/test_agent_mcp.py \
  tests/test_cli_chatgptrestctl.py
```

### B. API / 服务级关键路径验证

必须验证以下真实路径，而不是只看单元测试：

1. `/v1/tasks/{task_id}/finalize` 路由存在
2. 服务级正向：
   - `PROMOTED -> PUBLISHED -> DISTILLED -> COMPLETED`
   - `delivery_projection_ref` / `memory_distillation_ref` 均落库
3. API 级正向：
   - `POST /v1/tasks/{task_id}/finalize` 返回 `200`
   - 最终状态为 `completed`
4. 负向 fail-closed：
   - outcome 缺少 summary 时，finalize 失败
   - 任务保持 `promoted`

### C. CLI / 运行面 smoke

至少重跑并记录：

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python scripts/chatgptrest_bootstrap.py --task 'Fix public MCP ingress drift' --goal-hint public_agent --runtime quick
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python -m chatgptrest.cli --output json repo doc-obligations --changed-files chatgptrest/mcp/agent_mcp.py AGENTS.md
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python -m chatgptrest.cli --output json opencli doctor --no-live
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python -m chatgptrest.cli --output json opencli smoke
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python scripts/chatgptrest_closeout.py --json --skip-doc-check --agent test-agent --status completed --summary "full integration validation smoke"
```

## 修复策略

如果任一验收项失败，Claude Code 必须按以下顺序处理：

1. 先定位最小根因
2. 只修与失败直接相关的代码或测试
3. 补对应回归测试
4. 先重跑失败子集
5. 再重跑整套验收集合
6. 更新 walkthrough / todo / closeout 文档

## 不允许的捷径

- 不允许删除测试来换绿
- 不允许把真实失败改成 skip/xfail，除非有明确环境性理由且我事先认可
- 不允许在测试中通过手工 DB 写入伪造端到端成功来替代 runtime path
- 不允许用浏览器人工观察代替 CLI / API 验证
- 不允许把 `foundation` 写成 `best-practice complete harness`

## 交付物

Claude Code 完成后，至少要留下：

1. 修复提交（若发生代码修改）
2. 一份本轮联测 walkthrough
3. 一份更新后的 todo / closeout 记录
4. 明确列出：
   - 跑了哪些命令
   - 哪些测试通过
   - 是否发生修复
   - 还剩哪些真实边界

## 通过标准

只有同时满足以下条件，才允许我合并或宣告闭环：

- A/B/C 三类验收全部通过
- 若有修复，相关回归已补
- walkthrough 口径与代码现状一致
- worktree 干净，除了明确保留的审计文档外没有临时残留
