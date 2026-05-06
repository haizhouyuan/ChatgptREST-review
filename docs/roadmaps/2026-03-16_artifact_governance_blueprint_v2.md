# 产物治理蓝图 v2

日期：2026-03-16
状态：proposal
基于：

- v1 蓝图：`docs/roadmaps/2026-03-16_artifact_governance_blueprint_v1.md`
- 独立评审：`docs/reviews/2026-03-16_artifact_governance_blueprint_review_v1.md`

## 1. 本版修订重点

v2 吸收了 v1 评审中的 5 个有效点：

1. Phase 0 不再要求全量 14 字段 manifest，只冻结最小必填 schema。
2. 明确 `staging` 不是对象类型，而是 Memory 写入闸门。
3. weekly governance 不再抽象成“以后有个 daemon 就行”，而是先列出可直接调用项与需补 wrapper 项。
4. `artifact_governance_daemon` 改为分阶段独立执行，不设计成单体串行巨石。
5. retention 不再只有日历驱动，还增加目录数量与磁盘预算驱动。

## 2. 目标

建立一套统一的 agent 产物治理体系，使系统具备 4 个能力：

1. 任意产物都能稳定落盘、检索、追溯。
2. 任意内容都能进入正确层，而不是“统统进 KB”。
3. 整理、归档、评分、晋升、淘汰有固定周期和明确执行器。
4. 人类与 agent 都能快速看懂某个产物当前所处生命周期。

## 3. 当前诊断

### 3.1 已有基础

- 作业产物稳定落盘到 `artifacts/jobs/<job_id>/`
- 维护证据稳定落盘到 `artifacts/monitor/...`
- Advisor runtime 已接入 `ArtifactRegistry -> KBHub auto-index`
- `MemoryManager` 已支持 `staging / working / episodic / semantic / meta`
- `ActivityIngestService` 已能 ingest closeout / commit / activity 到 EvoMap review plane
- `ArtifactRegistry` 已支持 `quality_score / stability / quarantine_weight`
- 仓库已有多个 review-plane manifest 生成器与 acceptance pack 生成器

### 3.2 真正缺口

最大的缺口不是“没有模块”，而是“没有统一编排”：

- manifest 没有统一契约
- weekly governance 没有稳定 runner
- retention 没有统一 enforcement
- knowledge promotion 仍依赖局部脚本和人工流程

## 4. 对象模型

对象类型沿用 ADR-001：

| 对象类型 | 主存储 | 说明 |
|---|---|---|
| `profile_memory` | `memory.db` semantic | 用户偏好、长期身份事实 |
| `episodic_feedback` | `memory.db` episodic/meta | 执行反馈、任务历史、工具结果 |
| `governed_claim` | EvoMap atoms | 需要 quality / groundedness / promotion 的知识断言 |
| `evidence_artifact` | KB registry + FTS | 文档、报告、导出、截图、证据包 |
| `runtime_evidence` | `artifacts/jobs` / `artifacts/monitor` | 运行面证据与审计留痕 |

关键边界：

- `runtime_evidence` 不是 `governed_claim`
- `evidence_artifact` 可以进 KB，但默认不是 active knowledge
- `governed_claim` 需要经过 review / promotion pipeline

## 5. Memory 写入路径

v1 容易让人误读成“profile_memory 直接写 semantic”。v2 明确如下：

```text
profile_memory / episodic_feedback / meta_signal
  -> domain service
  -> MemoryManager.stage()
  -> StagingGate 校验
  -> promote(target tier)
```

因此：

- `staging` 是写入闸门，不是一个需要长期消费的业务对象类型
- object type 决定“目标层”
- `staging` 决定“到目标层前是否允许写入”

## 6. 目录与产物层

### 6.1 Runtime Evidence Layer

- `artifacts/jobs/<job_id>/`
- `artifacts/monitor/<subsystem>/`
- `artifacts/monitor/maint_daemon/incidents/<incident_id>/`

规则：

- 原始 evidence 不覆盖
- `latest.json` 只作为入口或镜像
- job/incident 主目录必须可通过主键回查

### 6.2 Review Plane Layer

- `artifacts/<domain>/inbox/`
- `artifacts/<domain>/inbox/archived/`
- `artifacts/monitor/<plane>/<timestamp>/`

规则：

- 只存 review / decision / queue / pack 相关对象
- 大段正文不重复复制
- `job_* / conversation.json / events.jsonl` 以 pointer 方式进入 `model_run`

### 6.3 KB Artifact Layer

- `knowledge/<para_bucket>/`
- 或 `OPENMIND_KB_ARTIFACT_DIR`

规则：

- 必须有 registry row
- 必须可回溯到 canonical source_path
- 未经治理的 artifact 默认为 `draft`

### 6.4 Active Knowledge Layer

- EvoMap `active` atoms
- 或经明确发布门槛进入的 KB artifact

规则：

- 只允许 governed_claim 进入
- execution evidence 默认停留在 review plane

## 7. Manifest 契约

### 7.1 Phase 0 最小必填字段

为了先定制度、不阻塞现有入口，v2 将必填字段缩到 5 个：

```json
{
  "artifact_id": "",
  "artifact_type": "",
  "canonical_path": "",
  "created_at": "",
  "schema_version": "artifact-manifest-v1"
}
```

### 7.2 Phase 1 扩展字段

以下字段作为 optional/backfill 扩展：

- `trace_id`
- `job_id`
- `task_ref`
- `source_system`
- `producer`
- `object_role`
- `retention_class`
- `review_status`
- `related_paths`
- `updated_at`
- `expires_at`
- `content_hash`

### 7.3 兼容策略

- 现有 job dir 里的 `request.json + result.json` 可视为 de facto manifest source
- backfill 脚本从这些文件抽取信息生成 `manifest.json`
- 不要求所有历史目录一次性补齐

## 8. 准入规则

### 8.1 Runtime Evidence

- 完成、失败、取消的 job 必须保留完整 job dir
- `verify_report.json|md` 仍属于 runtime evidence
- incident pack 引用 job evidence，不制造第二份 canonical answer

### 8.2 KB Artifact

必须走固定顺序：

1. domain service 收到写入
2. policy gate
3. 落盘 canonical file
4. `ArtifactRegistry.register_file()`
5. `KBHub.index_document()`
6. `EventBus` 记录
7. 根据策略调整 `quality_score / quarantine_weight / stability`

### 8.3 EvoMap

- 只接 `governed_claim`
- execution / planning / activity 先进入 review plane
- active promotion 需要 groundedness / review gate

### 8.4 Memory

- `profile_memory` 目标是 semantic
- `episodic_feedback` 目标是 episodic 或 meta
- 所有写入先过 staging gate

## 9. 保留策略

### 9.1 Runtime Evidence

- `hot`: 0-7 天
- `warm`: 7-30 天
- `archive_only`: 30 天以后

必须保留：

- `request.json`
- `result.json`
- `events.jsonl`
- `answer.md`
- `conversation.json`
- `manifest.json` 或等价源

### 9.2 KB Artifact

- `draft`
- `candidate`
- `approved`
- `expired`
- `archived`

### 9.3 Memory

- `working`: 短 TTL
- `episodic`: 默认 30 天
- `semantic`: 90 天以上
- `meta`: 持久但按聚合键去重

## 10. Retention Enforcement

v1 只定义了时间窗口，v2 补上 enforcement 机制。

### 10.1 时间驱动

- daily：处理 stale queue / inbox 归档
- weekly：KB 治理
- monthly：archive sweep

### 10.2 预算驱动

当满足任一条件时，提前触发 archive / cleanup：

- `artifacts/jobs/` 目录数超过阈值
- 单个 subsystem artifact root 超过磁盘预算
- 某类 artifact 连续 N 天无访问却持续增长

### 10.3 Enforcement 输出

所有清理动作必须写：

- `artifacts/monitor/artifact_governance/latest.json`
- `artifacts/monitor/artifact_governance/enforcement_actions.jsonl`

## 11. 周期治理

### 11.1 T+0

- 冻结 job dir
- 生成 minimal manifest
- 跑 `verify_job_outputs`
- 将 closeout / activity 送入 EventBus
- 若属于交付物，则进入 KB writeback

### 11.2 Daily

- stale queue / stale issue janitor
- review inbox 去重与 archive
- latest pointer 完整性检查

### 11.3 Weekly

- KB quality rescore
- KB stability transition
- KB pruner
- episodic -> semantic consolidation
- staged atoms 的 groundedness / candidate review

### 11.4 Monthly

- archive-only 迁移
- dead-reference check
- review-plane reject/archive sweep
- vector rebuild / backfill consistency check

## 12. Readiness Checklist

在启动 weekly governance 前，必须明确哪些 primitive 可直接调用，哪些必须先包一层 batch wrapper。

### 12.1 可直接调用

- `ArtifactRegistry.update_quality()`
- `ArtifactRegistry.transition_stability()`
- `KBPruner.run()`

### 12.2 需要补 wrapper

- 批量枚举并筛选需要 transition 的 artifact
- episodic -> semantic consolidation 批处理
- review-plane -> active knowledge 的候选集筛选
- runtime evidence -> archive_only 的批量搬运与 pointer 修正

### 12.3 必须先回答的问题

- 谁负责调度 weekly governance
- 每一步失败后是否影响其他步骤
- 是否允许只读 dry-run
- 是否允许按 subsystem 单独重跑

## 13. 统一治理执行器

v2 不再设计成单体串行巨石，而是分阶段执行。

建议新建：

`ops/artifact_governance_daemon.py`

内部拆成独立 stage：

1. `manifest_audit`
2. `retention_enforcement`
3. `kb_governance`
4. `memory_consolidation`
5. `review_plane_governance`
6. `promotion_readiness`

每个 stage：

- 独立输入
- 独立输出
- 独立 `ok/error/skipped`
- 独立写状态到 `latest.json`

这样即使 EvoMap DB lock，也不阻断 manifest audit 和 retention enforcement。

## 14. 与现有实现的映射

可直接复用：

- `ops/verify_job_outputs.py`
- `ops/backlog_janitor.py`
- `chatgptrest/kb/registry.py`
- `chatgptrest/kb/writeback_service.py`
- `chatgptrest/kernel/memory_manager.py`
- `chatgptrest/kernel/effects_outbox.py`
- `chatgptrest/evomap/activity_ingest.py`
- `chatgptrest/evomap/knowledge/pruner.py`
- `ops/maint_daemon.py` 的 incident manifest 机制
- execution review plane 现有各类 manifest builder

要新增的不是底层 primitive，而是：

- minimal manifest schema
- backfill 脚本
- batch wrappers
- stage-based governance runner

## 15. 实施顺序

### Phase 0

- 冻结 minimal manifest schema
- 文档化 staging gate

### Phase 1a

- 新增 weekly governance batch wrappers
- 不引入 daemon，只做可手动运行脚本

### Phase 1b

- 对现有 job dirs / review packs 做 manifest backfill

### Phase 2

- 上线 stage-based governance daemon
- 默认只读 dry-run

### Phase 3

- 打开 controlled promotion
- 仍保持 execution evidence stays review-plane 为默认值

## 16. 验收标准

- 任意 artifact 都能从 `artifact_id / trace_id / job_id` 回到 canonical path
- 任意 active knowledge 都能追到 review 决策和证据源
- retention 超限时能自动触发 archive，而不是无限堆积
- 周治理每个 stage 都能单独 dry-run / 重跑
- agent 不需要猜“该不该进 KB / EvoMap / memory”

## 17. 下一步任务

1. 定义 `artifact-manifest-v1` 最小 JSON schema
2. 实现 `manifest_backfill.py`
3. 实现 weekly governance batch wrappers
4. 实现 `artifact_governance_daemon.py --dry-run`
5. 最后再接 dashboard surfaces

