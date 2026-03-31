# Unified Agent Memory Closure Follow-up v2

日期：2026-03-28

## 本轮补齐内容

这版 `v2` 不再重复 `v1` 已完成的 `planning role priority / issue_execution live adapter / consult recall explainability`。

这次补的是两条还欠“可执行验收证据”的主链，以及一条缺失的 live status board：

1. `shared cognition status board`
   - 新增 [shared_cognition_scoreboard.py](/vol1/1000/projects/ChatgptREST/chatgptrest/dashboard/shared_cognition_scoreboard.py)
   - `/v2/dashboard/api/status` 不再只是时间戳占位，而是返回：
     - multi-ingress semantic validation 状态
     - `Codex / Claude Code / Antigravity` runtime consumer 状态
     - market candidate lifecycle 状态
     - 四端 live acceptance blocker
   - 新增导出脚本 [run_shared_cognition_status_board.py](/vol1/1000/projects/ChatgptREST/ops/run_shared_cognition_status_board.py)

2. external skill candidate lifecycle 联验证据
   - 新增 [run_skill_market_candidate_lifecycle_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_skill_market_candidate_lifecycle_validation.py)
   - 通过真实 CLI 链路跑通：
     - `register`
     - `evaluate`
     - `promote`
     - `deprecate --reopen-gap`
   - 不再只依赖 `market_gate` 方法级单测

3. runtime consumer live evidence 再落盘
   - 串行执行 `sync` + `status`
   - 当前 8 个 runtime consumer target 全部回读为 `ok`

## 相关提交

- `d2dc9cf` `feat(dashboard): add shared cognition status board`

## 新增产物

- [skill_market_candidate_lifecycle_validation_20260328/report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/skill_market_candidate_lifecycle_validation_20260328/report_v1.json)
- [skill_market_candidate_lifecycle_validation_20260328/report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/skill_market_candidate_lifecycle_validation_20260328/report_v1.md)
- [shared_cognition_status_board_20260328/report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/shared_cognition_status_board_20260328/report_v1.json)
- [shared_cognition_status_board_20260328/report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/shared_cognition_status_board_20260328/report_v1.md)

## 本次实跑结论

### 1. Skill runtime consumers

串行实跑：

```bash
PYTHONPATH=. ./.venv/bin/python ops/sync_skill_platform_frontend_consumers.py sync
PYTHONPATH=. ./.venv/bin/python ops/sync_skill_platform_frontend_consumers.py status
```

结果：

- `codex` 4 个 target：`ok`
- `claude_code` 2 个 target：`ok`
- `antigravity` 2 个 target：`ok`

合计：`8 / 8 ok`

### 2. External skill candidate lifecycle

实跑：

```bash
PYTHONPATH=. ./.venv/bin/python ops/run_skill_market_candidate_lifecycle_validation.py \
  --out-dir docs/dev_log/artifacts/skill_market_candidate_lifecycle_validation_20260328 \
  --db-path /tmp/skill_market_candidate_validation_20260328.db \
  --evomap-db-path /tmp/skill_market_candidate_validation_20260328_evomap.db
```

结果：

- `register` -> `quarantine`
- `evaluate` -> `evaluated`
- `promote` -> `promoted`
- `deprecate --reopen-gap` -> `deprecated`
- lifecycle roundtrip = `True`

### 3. Shared cognition status board

实跑：

```bash
PYTHONPATH=. ./.venv/bin/python ops/run_shared_cognition_status_board.py \
  --out-dir docs/dev_log/artifacts/shared_cognition_status_board_20260328
```

结果：

- `owner_scope_ready = True`
- `system_scope_ready = False`
- remaining blocker only:
  - `four_terminal_live_acceptance_pending`

这意味着：

1. `Phase 2 / 3 / 4 / 5` 的 owner-side 主链与可执行证据已经闭环。
2. 当前不再缺 `skill consumer evidence`、`market candidate lifecycle evidence`、`live scoreboard`。
3. 唯一未闭环的系统级 blocker 变成四端真实终端联合验收。

## 回归

已通过：

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_cognitive_api.py \
  tests/test_advisor_consult.py \
  tests/test_multi_ingress_work_sample_validation.py \
  tests/test_issue_graph_api.py \
  tests/test_memory_tenant_isolation.py \
  tests/test_planning_runtime_pack_search.py \
  tests/test_advisor_runtime.py \
  tests/test_skill_manager.py \
  tests/test_market_gate.py \
  tests/test_controller_engine_planning_pack.py \
  tests/test_sync_skill_platform_frontend_consumers.py \
  tests/test_shared_cognition_scoreboard.py \
  tests/test_skill_market_candidate_lifecycle_validation.py \
  tests/test_dashboard_routes.py
```

## 当前准确口径

### 可以按 owner scope 关单

1. Phase 2 主链
2. Phase 3 skill platform runtime consumer 证据
3. Phase 4 graph / explainability 主链
4. Phase 5 market candidate lifecycle / quarantine gate 证据
5. live shared cognition status board

### 仍不能按 system scope 关单

1. 整体“统一 agent 记忆系统”
2. 四端真实终端联合验收

一句话：这版 `v2` 把 owner-side 最后一批“还缺 live evidence”的口子补齐了，系统级剩余 blocker 收敛为单一项：`four_terminal_live_acceptance_pending`。
