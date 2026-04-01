# Artifact Governance Blueprint Walkthrough v1

日期：2026-03-16

## 本轮产出

- 新增蓝图文档：
  - `docs/roadmaps/2026-03-16_artifact_governance_blueprint_v1.md`

## 为什么要做

当前仓库已经有：

- 作业产物落盘
- KB writeback
- MemoryManager
- EvoMap activity ingest
- incident pack

但这些能力是分散接线的，缺统一治理蓝图。用户要求的是“agent 产物落盘管理应该怎么做、如何定期整理和入知识库”，因此这轮目标不是补一个脚本，而是先把统一制度写清楚。

## 这份蓝图做了什么

- 统一对象模型：
  - `profile_memory`
  - `episodic_feedback`
  - `governed_claim`
  - `evidence_artifact`
  - `runtime_evidence`
- 定义了目录层次、manifest 契约、保留策略、准入规则
- 明确了 T+0 / daily / weekly / monthly 四个治理周期
- 指出当前系统最大缺口是缺统一 orchestration runner
- 给出后续分阶段落地计划

## 依赖的现有基础

- `docs/contracts/ADR-001-state-model.md`
- `docs/contracts/ADR-002-ingress.md`
- `docs/dev_log/2026-03-10_kb_architecture_deep_audit_v2.md`
- `chatgptrest/kb/writeback_service.py`
- `chatgptrest/kernel/memory_manager.py`
- `chatgptrest/evomap/activity_ingest.py`
- `ops/maint_daemon.py`

## 独立判断

现在系统已经有 70% 的零件，但没有统一制度和调度器。

这份蓝图的核心价值是：

- 先把“什么该进哪里”定死
- 再把“何时整理、何时晋升、何时归档”定死
- 最后再补统一 runner

否则继续局部修补，只会让 artifacts / memory / KB / EvoMap 的边界越来越乱。

## 下一步建议

优先做：

1. `artifact-manifest-v1` schema
2. `artifact_governance_daemon.py` 只读巡检版
3. manifest backfill
4. weekly KB governance runner

