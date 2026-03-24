# 产物治理蓝图 v1

日期：2026-03-16
状态：proposal
范围：ChatgptREST / OpenMind / EvoMap / agent runtime

## 1. 目标

建立一套统一的 agent 产物治理体系，使系统满足 4 个目标：

1. 所有运行产物都能被稳定落盘、定位、追溯、复盘。
2. 只有合适的内容进入合适的存储层，避免“什么都塞进知识库”。
3. 整理、归档、评分、晋升、淘汰有固定周期和明确定义。
4. 人类和 agent 都能快速理解某个产物当前处于哪个生命周期阶段。

这份蓝图不是另起炉灶，而是把仓库里已经存在的能力统一成一套制度，并补上目前缺失的 orchestration。

## 2. 当前现状

### 2.1 已有能力

- 作业产物已有稳定落盘面：`artifacts/jobs/<job_id>/`，包含 `request.json`、`answer.md`、`conversation.json`、`events.jsonl`、`result.json` 等。
- 运维证据已有 incident pack：`artifacts/monitor/maint_daemon/incidents/<incident_id>/`。
- Advisor runtime 已接入 `ArtifactRegistry -> KBHub auto-index`、`EventBus -> Memory`、`EventBus -> ActivityIngestService`。
- `MemoryManager` 已支持 `staging / working / episodic / semantic / meta` 五层以及 TTL、审计、去重。
- `ArtifactRegistry` 已支持 `quality_score`、`stability`、`quarantine_weight`。
- EvoMap 已能 ingest `agent.git.commit`、`agent.task.closeout`、`agent activity` 进入 review plane。

### 2.2 现存问题

- 落盘、记忆、KB、EvoMap 是分段实现，不是统一编排。
- 不是所有产物都有统一 `manifest`，跨层追溯仍依赖路径约定和人工推断。
- KB 治理、semantic promotion、graph building、vector flush 虽然有代码，但缺统一定时 runner。
- review-plane / archive-only / active knowledge 的边界已有设计，但没有覆盖所有 ingress。
- 清理和归档存在局部 janitor，缺统一 retention policy。

## 3. 设计原则

- 类型优先：先定义对象类型，再决定落到哪个 store。
- 不混层：证据、记忆、可晋升 claim、活跃知识不能共用一个生命周期。
- 不覆盖：版本化产物不可被 `latest` 指针替代。
- 先审后入：所有知识写入必须先过 domain service 与 policy gate。
- review-plane 优先：执行证据先进入 review plane，不直接晋升为 active knowledge。
- 指针优先于复制：大型原文只保留 canonical path，知识层尽量存引用、摘要、元数据。
- 异步 side effect 走 outbox，不在主路径里直接做不可逆外部动作。

## 4. 统一对象模型

基线采用 ADR-001 / ADR-002 的分层：

| 对象类型 | 定义 | 主存储 | 生命周期 |
|---|---|---|---|
| `profile_memory` | 用户偏好、长期身份事实 | `memory.db` semantic | 持久，直写 |
| `episodic_feedback` | 任务历史、工具结果、运行反馈 | `memory.db` episodic/meta | TTL 过期 |
| `governed_claim` | 需要质量门控和 groundedness 的知识断言 | EvoMap atoms | staged -> candidate -> active |
| `evidence_artifact` | 原始证据文档、报告、对话导出、截图等 | KB registry + FTS | draft/candidate/approved/expired |
| `runtime_evidence` | 作业和 incident 运行证据 | `artifacts/jobs/`、`artifacts/monitor/` | 保留、归档、不可直接晋升 |

关键纪律：

- `runtime_evidence` 不是 `governed_claim`。
- `evidence_artifact` 可以进 KB，但默认不是 active knowledge。
- `governed_claim` 只能通过 review / promotion pipeline 进入 active knowledge。
- shell 和 agent 只能通过 domain service 写入，不允许直接操作底层 DB。

## 5. 目录与命名规范

### 5.1 Runtime Evidence

统一保留在：

- `artifacts/jobs/<job_id>/`
- `artifacts/monitor/<subsystem>/`
- `artifacts/monitor/maint_daemon/incidents/<incident_id>/`

约束：

- 目录名必须有稳定主键：`job_id`、`incident_id`、`trace_id` 或时间戳 + 逻辑 ID。
- `latest.json` 只能是镜像索引或摘要入口，原始内容必须在独立版本目录中。
- 原始 evidence 文件不覆盖，必要时新增 `*_v2` 或时间戳目录。

### 5.2 Review Plane Package

适用于 planning / execution / finbot / review 套件：

- `artifacts/<domain>/inbox/`
- `artifacts/<domain>/inbox/archived/`
- `artifacts/monitor/<plane>/<timestamp>/`

约束：

- review package 只保留用于核验和晋升的材料集合。
- `job_*`、`conversation.json`、`events.jsonl` 作为 `model_run` 证据，只登记 path，不复制正文。

### 5.3 KB Artifact

KB canonical artifact 文件保留在：

- `knowledge/<para_bucket>/`
- 或显式配置的 `OPENMIND_KB_ARTIFACT_DIR`

约束：

- 文件名必须稳定且可反查 `trace_id` 或 `artifact_id`。
- 必须进入 `ArtifactRegistry`，不能只有文件没有 registry row。

## 6. Manifest 契约

所有新产物目录必须包含 `manifest.json` 或等价规范元数据，建议最少字段：

```json
{
  "artifact_id": "",
  "artifact_type": "runtime_evidence|evidence_artifact|governed_claim|review_pack|model_run",
  "trace_id": "",
  "job_id": "",
  "task_ref": "",
  "source_system": "",
  "producer": "",
  "object_role": "analysis|evidence|plan|decision|runbook|delivery",
  "retention_class": "hot|warm|archive_only|review_plane|kb_candidate|active_knowledge",
  "review_status": "raw|verified|rejected|staged|candidate|active|expired|archived",
  "canonical_path": "",
  "related_paths": [],
  "created_at": "",
  "updated_at": "",
  "expires_at": null,
  "content_hash": "",
  "schema_version": "artifact-manifest-v1"
}
```

补充建议：

- `review_status` 表示当前治理状态。
- `retention_class` 表示保留/晋升策略。
- `canonical_path` 始终指向原始权威文件，不允许 review plane 自己变成 source of truth。

## 7. 准入规则

### 7.1 Runtime Evidence 准入

- 所有 job 完成、失败、取消都必须有完整 job dir。
- `verify_job_outputs` 产生的 `verify_report.json|md` 属于 runtime evidence，不直接入 KB。
- incident pack 只引用 job evidence，不在维护路径中制造第二份 canonical 正文。

### 7.2 KB 准入

只有满足下面任一条件的内容允许写入 KB：

- 人类确认过的稳定文档。
- Advisor writeback 输出的交付物。
- 结构化 review 通过的 evidence package。
- 明确标记为 reference 的原始证据文档。

写入顺序固定为：

1. domain service 接收写入
2. policy gate 检查
3. 落盘 canonical file
4. `ArtifactRegistry.register_file()`
5. `KBHub.index_document()`
6. 写入 `EventBus`
7. 根据结果更新 `quality_score / quarantine_weight / stability`

### 7.3 EvoMap 准入

EvoMap 只接两类东西：

- `governed_claim`
- execution / planning / activity 的 review-plane 对象

原则：

- 原始文档不是 Atom。
- closeout / commit / activity 的 ingest 默认是 `promotion_status=staged/candidate`，不是 active knowledge。
- active promotion 必须经过 groundedness / review gate。

### 7.4 Memory 准入

- `profile_memory` 直接进 semantic。
- `episodic_feedback` 进 episodic。
- `route.selected`、`gate.*`、`kb.writeback` 等运行元事件进 meta。
- 不允许客户端直接写 `memory.db`。

## 8. 保留与归档策略

### 8.1 Runtime Evidence

- `hot`：最近 7 天，允许 dashboard / issue / repair 快速访问。
- `warm`：7-30 天，仅保留复盘所需关键文件。
- `archive_only`：30 天后归档，不再作为活跃运行面输入。

保留文件建议：

- 必保留：`request.json`、`result.json`、`events.jsonl`、`answer.md`、`conversation.json`、`manifest.json`
- 可按策略清理：大截图、临时 debug dump、重复中间产物

### 8.2 KB Artifact

- `draft`：刚写入，默认可检索但下调权重
- `candidate`：通过初步 review
- `approved`：可作为稳定引用
- `expired`：长期未命中或质量低
- `archived`：历史留存，不再参与常规召回

### 8.3 Memory

- `working`：会话级，短 TTL
- `episodic`：默认 30 天
- `semantic`：90 天以上或长期
- `meta`：持久，但按聚合键去重

## 9. 定期整理与晋升节奏

### 9.1 T+0 完成时

- 冻结 job 目录
- 写 `manifest.json`
- 跑 `verify_job_outputs`
- 将 closeout / activity 送入 EventBus
- 若是交付物，走 KB writeback

### 9.2 Daily

- queue / issue / stale review janitor
- review inbox 去重并把旧 pending 移到 `archived/`
- 导出 review-plane snapshot
- 检查 `latest.json` 是否指向存在的 canonical artifact

### 9.3 Weekly

- 重算 KB `quality_score`
- 运行 KB stability transition
- 运行 KB pruner
- 运行 episodic -> semantic consolidation
- 处理 staged atoms 的 groundedness / candidate 评审

### 9.4 Monthly

- 归档 30 天以上 runtime evidence
- 对 KB 做 dead-reference check
- 对 review plane 做 reject/archive sweep
- 对 vector index 做 rebuild 或 backfill consistency check

## 10. 需要新增的统一编排器

这是当前最大的缺口。建议新增一个统一治理 runner：

`ops/artifact_governance_daemon.py`

职责：

- 读取 jobdb、registry、memory、evomap、review-plane snapshot
- 执行 daily/weekly/monthly 三套治理规则
- 产出：
  - `artifacts/monitor/artifact_governance/latest.json`
  - `artifacts/monitor/artifact_governance/history_*.jsonl`
  - `artifacts/monitor/artifact_governance/violations.md`

内部阶段：

1. ingest audit
2. manifest backfill
3. stale / duplicate archive
4. KB rescore + transition
5. memory consolidation
6. EvoMap promotion review
7. report + alert

## 11. 与现有模块的映射

可直接复用的现有实现：

- 作业证据：`artifacts/jobs/<job_id>/`
- incident pack：`ops/maint_daemon.py`
- job 核验：`ops/verify_job_outputs.py`
- registry / score / stability：`chatgptrest/kb/registry.py`
- KB writeback：`chatgptrest/kb/writeback_service.py`
- memory：`chatgptrest/kernel/memory_manager.py`
- outbox：`chatgptrest/kernel/effects_outbox.py`
- activity ingest：`chatgptrest/evomap/activity_ingest.py`
- KB pruner：`chatgptrest/evomap/knowledge/pruner.py`
- stale queue/issue janitor：`ops/backlog_janitor.py`

需要补齐的部分：

- 统一 manifest schema 与 backfill
- registry quality/stability 的周期 runner
- semantic promotion runner
- review-plane -> active knowledge 的标准晋升线
- retention class 与 archive policy 的统一配置

## 12. 实施阶段

### Phase 0：定制度，不改行为

- 冻结对象分类和 retention class
- 发布 `artifact-manifest-v1`
- 明确所有新产物必须带 manifest

### Phase 1：把已有链路接齐

- Advisor / maint / finbot / review package 全部补 manifest
- `ArtifactRegistry` 与 `KBHub` 的回调链统一走一个入口
- `verify_job_outputs`、closeout、activity ingest 统一写 identity 字段

### Phase 2：把整理做成定时运行

- daily janitor
- weekly governance
- monthly archive sweep

### Phase 3：打开可控晋升

- staged -> candidate
- candidate -> active
- active -> KB publish

默认仍应保持：

- execution evidence stays review-plane
- active knowledge auto-promotion 默认关闭，先观测再开

## 13. 验收标准

- 任意一个 artifact 都能从 `artifact_id/trace_id/job_id` 追到 canonical path。
- 任意一条活跃知识都能回溯到 review 决策和原始证据。
- 任意一个超过 retention 的 runtime artifact 都能被 janitor 正确归档，而不是静默堆积。
- agent 不需要猜“这个文件该不该进 KB”，而是按 object type 自动走对路径。
- dashboard 可以按 retention class / review_status 展示产物，而不是只显示散乱路径。

## 14. 不该做的事

- 不要把所有 closeout 正文直接写进 KB。
- 不要把所有 evidence 直接变成 Atom。
- 不要把运行时清理逻辑做成 destructive fix。
- 不要靠 shell 脚本绕过 domain service 直接写库。
- 不要用 `latest.*` 覆盖原始历史版本。

## 15. 推荐的下一步落地任务

1. 定义 `artifact-manifest-v1` JSON schema 并实现 backfill。
2. 新建 `artifact_governance_daemon.py`，先做只读巡检。
3. 给 Advisor / maint / finbot / execution review plane 统一补 manifest。
4. 接 weekly governance：KB rescore、stability transition、semantic consolidation。
5. 再做 archive policy 与 dashboard surfaces。

