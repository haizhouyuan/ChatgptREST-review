# 2026-03-15 OpenMind Controller Unification Walkthrough v1

## 背景

当前 OpenMind/OpenClaw 组合的主要问题不是“功能不够多”，而是主热路径仍以路由和单 job 提交为中心，缺少一个可恢复、可编排、可交付的统一 controller。用户体感上会得到很多能力碎片，但得不到一个持续负责结果的执行者。

## 本次改造目标

- 在不推翻现有 `advisor_runs` 和 v3 graph 的前提下，补一层 durable controller ledger。
- 让 `/v2/advisor/advise` 与 `/v2/advisor/ask` 都走统一 controller 入口。
- 让热路径返回“run + delivery + next_action + work_items”这一类工作对象，而不只是路由结果或 job id。
- 保持数据库和既有 API 语义向后兼容，优先做 additive change。

## 主要实现

### 1. 新增 controller 模块

新增目录：

- `chatgptrest/controller/__init__.py`
- `chatgptrest/controller/store.py`
- `chatgptrest/controller/engine.py`

其中：

- `store.py` 提供 durable controller ledger 的读写封装。
- `engine.py` 封装统一 controller 执行入口，负责：
  - 建立或复用 run
  - 写入计划、执行、交付三个阶段的结构化状态
  - 兼容同步 `advise` 与异步 `ask`
  - 把旧 `advisor_runs` 作为兼容锚点保留下来

### 2. 扩展数据库为 durable controller ledger

在 `chatgptrest/core/db.py` 中新增了以下表，全部为 additive change：

- `controller_runs`
- `controller_work_items`
- `controller_checkpoints`
- `controller_artifacts`

用途：

- `controller_runs`：统一保存 run 级状态、route、delivery、next_action
- `controller_work_items`：保存规划、执行、交付等工作项
- `controller_checkpoints`：给后续 human gate / approval 留口
- `controller_artifacts`：给 KB chunk、conversation url、controller snapshot 等产物留结构化记录

同时新增 trace/request/status/job 等索引，避免 controller 查询退化成全表扫描。

### 3. 把 Advisor API 收敛到统一 controller

在 `chatgptrest/api/routes_advisor_v3.py` 中完成了三件事：

- `/v2/advisor/advise` 改为通过 `ControllerEngine.advise(...)` 调用
- `/v2/advisor/ask` 改为通过 `ControllerEngine.ask(...)` 调用
- 新增 `GET /v2/advisor/run/{run_id}` 用于读取 durable controller snapshot

同时做了两个兼容性细节：

- `/v2/advisor/trace/{trace_id}` 在内存 trace 缺失时，回退到 controller ledger
- `advisor_ask` 对 `HTTPException` 单独透传，避免 400 类请求错误被误包成 502

### 4. 扩展测试覆盖 controller 行为

在 `tests/test_advisor_v3_end_to_end.py` 中新增和加强了以下断言：

- `advise` 响应包含 `run_id` 和 `controller_status`
- 相同 auto-idempotent ask 请求可复用同一个 `run_id`
- fake API 不存 trace 时，controller trace fallback 仍可读
- 新增 `/v2/advisor/run/{run_id}` 的读取验证
- ask 返回 controller snapshot 相关字段

## 设计取舍

### 为什么没有直接重写 Advisor v3 graph

因为 graph 目前已经承担 route、kb_probe、intent analysis 的认知前半段。直接重写风险大、收益低。本次改造的重点是把它降级为 controller 的规划/执行输入，而不是直接对用户暴露的终端执行面。

### 为什么没有直接改写现有 `advisor_runs`

GitNexus 对 `init_db` 与 `update_run` 的 blast radius 评估都是 `CRITICAL`。这次改造选择 additive ledger，避免破坏已有 orchestrate、worker、dashboard 与观察工具的假设。

## 风险与后续

当前这次改造把“统一控制面”的骨架立起来了，但还没有把多 lane team dispatch、standing goals、主动后台推进接进 controller 主回路。后续需要继续把 `TeamControlPlane`、lane digest 和 action adapter 真正接到这层 controller 上。

## 验证

已执行并通过：

- `/.venv/bin/python -m py_compile chatgptrest/controller/__init__.py chatgptrest/controller/store.py chatgptrest/controller/engine.py chatgptrest/core/db.py chatgptrest/api/routes_advisor_v3.py tests/test_advisor_v3_end_to_end.py`
- `/.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py`
- `/.venv/bin/pytest -q tests/test_routes_advisor_v3_security.py tests/test_api_startup_smoke.py`

## 提交前范围说明

本次按仓库要求执行了 `gitnexus_detect_changes(scope="all")`。但由于主仓库存在大量与本任务无关的脏改动，GitNexus 输出被污染，显示为整仓级 `critical`，不能直接代表本 worktree 的真实提交范围。

因此本次实际提交范围以当前 clean worktree 的 `git status` / `git diff --name-only` 为准，仅包含：

- `chatgptrest/controller/*`
- `chatgptrest/core/db.py`
- `chatgptrest/api/routes_advisor_v3.py`
- `tests/test_advisor_v3_end_to_end.py`
- 本 walkthrough 与 review packet 文档
