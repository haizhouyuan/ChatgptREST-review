# Unified Agent Memory Closure Follow-up v1

日期：2026-03-28

## 本轮目标

把 2026-03-28 之前仍卡住“统一 agent 记忆系统”主链完工判断的几条核心缺口继续收口到 committed code，并把验证证据补齐到可同步 planning 状态板的程度。

## 本轮完成

1. `ContextResolver` 对 `role_id=planning` 增加显式最高优先级：
   - `planning runtime pack` 在 `context/resolve` 中可带 `priority_mode=planning_role_explicit_highest`
   - prompt prefix 会把 `Planning Runtime Pack` 置于前缀最前段
   - 新增 explainability / promotion audit metadata，显式说明该优先级提升来自 planning role
2. `GraphQueryService` 接入 `issue_execution` live adapter：
   - 默认不再是 null adapter
   - 优先走 canonical issue graph
   - canonical 文本匹配 miss 时回退到 legacy token-match query
   - `/v2/graph/query` 现在会返回 `issue_graph` summary、family router explainability、issue graph evidence
3. `routes_consult.py` 的 legacy consult / recall surface 增补 explainability：
   - `POST /v1/advisor/consult` 返回 context injection explainability 与 promotion audit
   - `GET /v1/advisor/consult/{id}` 保留 explainability / promotion audit
   - `POST /v1/advisor/recall` 为每个 hit 增加 explainability，并返回 source explainability / promotion audit
4. 新增本轮 multi-ingress 语义一致性产物：
   - `docs/dev_log/artifacts/phase8_multi_ingress_work_sample_validation_20260328/report_v1.json`
   - `docs/dev_log/artifacts/phase8_multi_ingress_work_sample_validation_20260328/report_v1.md`

## 相关提交

- `7d1eafc` `feat(cognitive): prioritize planning role and live issue graph`
- `b09bd5c` `feat(consult): add explainability to consult and recall`

## 验证

已通过：

```bash
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_cognitive_api.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_advisor_consult.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_multi_ingress_work_sample_validation.py
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_cognitive_api.py \
  tests/test_advisor_consult.py \
  tests/test_issue_graph_api.py \
  tests/test_memory_tenant_isolation.py \
  tests/test_planning_runtime_pack_search.py \
  tests/test_advisor_runtime.py \
  tests/test_skill_manager.py \
  tests/test_market_gate.py \
  tests/test_controller_engine_planning_pack.py
```

## 仍未闭环

1. 四端真实终端联合验收仍未完成。
2. skill platform 的 `Codex / Claude Code / Antigravity` 行为级消费证据仍未补成最终关单口径。
3. external skill candidate 的 quarantine -> candidate -> rollback 联验证据仍未补齐。

结论：本轮把 `planning role weighting`、`issue_execution live adapter`、`consult/recall explainability` 三条主链缺口补到了 committed code + tests；但“统一 agent 记忆系统整体完成”仍不能替代四端 live acceptance。
