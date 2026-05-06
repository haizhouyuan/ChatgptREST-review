# Planning Agent Knowledge Architecture — Independent Audit v2

> **审计人**: Antigravity (independent, 原子级读代码)
> **日期**: 2026-04-02
> **基线**: ChatgptREST `master` HEAD
> **与 v1 的关系**: v1 包含多处错误推断（见附录）。本文档是在 v1 所有错误被逐一纠正后的重新审计，每个结论都附有代码行号或运行时证据。

---

## 0. 勘误：v1 和 review packet 中的错误

**以下是我在 v1 中犯的错误，此处公开纠正：**

| # | v1 错误声称 | 实际事实（代码证据） |
|---|---|---|
| 1 | "`_ensure_rescored()` 阻塞 pack search 热路径 (P0)" | `search_planning_runtime_pack()` 根本不调用 `_ensure_rescored()`。它使用自己的 `_fetch_db_rows()` → raw `sqlite3.connect()` (planning_runtime_pack_search.py:93)，跳过整个 retrieval pipeline |
| 2 | "`_ensure_rescored()` 在 102K atom DB 上会卡分钟级" | 当前 DB 中 zero-quality 占比仅 6.8% (6956/102720)，远低于 50% 触发阈值。`_ensure_rescored()` 根本不会触发 (retrieval.py:48) |
| 3 | "数据平面断连 (P0 BLOCKER)" (v1 初始版本) | 查询了错误的 DB (`~/.openmind/`)。`resolve_evomap_knowledge_read_db_path()` 明确拒绝 legacy 路径 (openmind_paths.py:95)，正确指向 `data/evomap_knowledge.db` (102K atoms) |
| 4 | "只有 4 条 golden query 的验收覆盖" | 实际有 29 个 planning 相关测试文件（如 `test_planning_runtime_pack_search.py`, `test_audit_planning_runtime_pack_sensitivity.py` 等），覆盖搜索、审计、bundle 构建、review cycle 等 |

---

## 1. 策略验证结论

> **"补齐优先，不重构" 策略正确。** 架构基本健全，核心组件生产可用。

代码层面证据：

| 组件 | 状态 | 证据 |
|---|---|---|
| `search_planning_runtime_pack()` | ✅ 生产可用，5-15ms | 7 个 query 全部返回 5 条命中，promotion=active, groundedness=1.0 |
| `WorkMemoryManager.build_active_context()` | ✅ 生产可用 | 4 个 category (active_project, decision_ledger, post_call_triage, handoff) 全部实现 (work_memory_manager.py:59-64) |
| `ContextAssembler` planning 集成 | ✅ 生产可用 | planning_pack 映射到 "knowledge" 类型 (context_service.py:30)，role=planning 时 priority=0 最高优先级 (context_service.py:890) |
| `PromotionEngine` | ✅ 完整实现 | 生命周期 staged→candidate→active→superseded→archived，groundedness gate ≥0.7 (promotion_engine.py:32-38, 71) |
| `_ensure_rescored()` | ✅ 安全 | 仅在 `retrieve()` 路径调用 (retrieval.py:271)，不影响 pack search；当前 DB 不触发 |

---

## 2. 核心事实发现

### 2.1 运行时数据库状态

```
总 atoms: 102,720
┌─────────────┬────────┬───────┐
│ 状态         │ 数量   │ 占比  │
├─────────────┼────────┼───────┤
│ staged      │101,951 │ 99.3% │
│ archived    │   542  │  0.5% │
│ active      │   202  │  0.2% │
│ candidate   │    25  │  0.0% │
└─────────────┴────────┴───────┘

Quality 分布:
  0.50-0.80: 89.0%  (91,435)   — 主体，质量尚可
  0.15-0.50:  2.3%  ( 2,325)
  0.80-1.00:  2.0%  ( 2,004)   — 高质量
  zero:       6.8%  ( 6,956)   — 未评分

通过运行时发布门禁的 atoms (active + quality≥0.15 + groundedness≥0.5): 201
```

**代码路径证据**：
- DB 路径解析: `openmind_paths.py:88-107` → `resolve_evomap_knowledge_read_db_path()` 优先 `REPO_ROOT/data/evomap_knowledge.db`，明确拒绝 `~/.openmind/` 的 legacy 路径
- Runtime gate: `planning_runtime_pack_search.py:124-134` → `_passes_runtime_gate()` 检查 promotion_status ∈ allowed, stability ∉ excluded, quality ≥ 0.15, groundedness ≥ 0.5

### 2.2 Pack Bundle 状态

```
最新就绪 bundle: 20260311T110948Z
Pack atoms: 226 (retrieval_pack.json 中的 atom_ids)
Pack 年龄: ~528 小时 (~22 天)
Manifest mtime: 2026-03-11T19:09:48
```

**代码路径证据**：
- Bundle 解析: `planning_runtime_pack_search.py:39-52` → `_latest_ready_bundle()` 扫描 `DEFAULT_RELEASE_BUNDLE_ROOT`，按目录名倒序取第一个 `ready_for_explicit_consumption=True` 的
- Pack 消费: `planning_runtime_pack_search.py:159` → `_fetch_pack_rows()` 读 TSV 文件 + `retrieval_pack.json` 的 `atom_ids` 集合

### 2.3 两条检索路径对比

| 维度 | Pack Search 路径 | EvoMap Retrieve 路径 |
|---|---|---|
| 入口函数 | `search_planning_runtime_pack()` | `retrieve()` |
| DB 访问方式 | raw `sqlite3.connect()` (planning_runtime_pack_search.py:93) | `KnowledgeDB.connect()` (retrieval.py:274) |
| 是否调用 `_ensure_rescored()` | ❌ 不调用 | ✅ 调用 (retrieval.py:271) |
| 搜索方式 | 内存 token 匹配 (planning_runtime_pack_search.py:77-79) | FTS5 全文索引 (retrieval.py:278-288) |
| 候选池 | TSV 文件中 226 个 atom_ids | DB 中 102,720 全量 atoms |
| 运行时门禁 | `_passes_runtime_gate()` — cfg 默认 allowed=(active, staged) | promotion filter — USER_HOT_PATH 只允许 active |
| 当前命中 | 5-15ms, 每查询返回 ≥5 条 | 112-140ms, 返回 **0 条** (USER_HOT_PATH) |

**关键发现**：EvoMap retrieve 在 `USER_HOT_PATH` 返回 0 条是因为 FTS5 搜到的结果全是 `staged`，而 `USER_HOT_PATH` 只允许 `active`（`retrieval.py:116`）。这不是 bug，是设计意图——只有被审核通过的 active atoms 才能出现在用户热路径。

### 2.4 Context Service 集成路径

完整调用链（context_service.py）：

```
ContextService.resolve()
  → _LocalOnlyContextAssembler(kb_hub=..., evomap_db=...)     # line 143-156
    → assembler.build()                                        # line 157
      → [1] Working Memory                                     # line 758-768
      → [2] Episodic Memory                                    # line 769-790
      → [3] Captured Memory                                    # line 791-835
      → [4] Semantic Memory                                    # line 837-860
      → [5] Planning Pack Search (import + call)               # line 862-905
      → [6] KB Hub Search                                      # line 907-923
      → [7] EvoMap Retrieve (if graph requested)               # line 925-959
    → filter sources by requested_sources                       # line 170-196
    → build Active Context (WorkMemoryManager)                  # line 200-221
    → compose_prompt_prefix (planning block placement)          # line 464-495
```

Planning pack 在 prompt 中的位置：
- role_id == "planning" → `priority=0`，在 prompt **最前方** (context_service.py:482-483)
- 其他 role → 在 base prompt **之后** (context_service.py:489-490)

### 2.5 Promotion 生命周期

```
staged → candidate → active → superseded → archived
```

**代码证据** (promotion_engine.py:32-38):
- `staged → candidate`: 唯一出路
- `candidate → active`: 需要通过 groundedness gate (≥0.7)
- `candidate → staged`: 可回退（如 groundedness 失败）
- `active → superseded | archived`: 降级路径

**Bootstrap 入活机制** (planning_review_plane.py:1242-1467):
- `apply_bootstrap_allowlist()` 按 allowlist 的 doc_ids 选择
- 每个 doc 取 top 2 atoms (quality ≥ 0.58, 有 canonical_question)
- 先提升到 candidate，只有 `service_candidate` bucket 且有 runtime grounding anchors 且通过 groundedness gate (≥0.6) 才能到 active
- **这是手动操作，没有定时任务或自动化调度**

**P4 batch fix** (p4_batch_fix.py:41-94):
- `promote_eligible_atoms()` 只从 `candidate → active` (quality ≥ 0.3, groundedness ≥ 0.7)
- 当前 DB 只有 25 个 candidate，所以提升空间极小
- **也是手动操作 (`python -m chatgptrest.evomap.knowledge.p4_batch_fix`)**

---

## 3. 真实问题清单

### P1: 无自动化 promotion/refresh 管线

**严重度**: P1 (不是 P0——系统可用，但会持续退化)

**事实**:
- 22 个 ops 脚本存在 (`ops/run_planning_review_cycle.py`, `ops/run_planning_review_refresh.py` 等)，但**没有 systemd timer、cron 或任何自动调度**
- Pack 已 22 天未刷新 (最后 bundle: 2026-03-11)
- 99.3% atoms 停留在 `staged`，需要人工 bootstrap 才能进入 `candidate → active`

**影响**:
- 新的知识（新文档、新决策）无法自动进入 runtime pack
- 已有 staged atoms 不会自动升级

**建议方案**:
- 不需要重构。只需添加一个 systemd timer 定期运行 `ops/run_planning_review_cycle.py` + `ops/build_planning_runtime_pack_release_bundle.py`

### P2: EvoMap retrieve 路径对 planning 角色无效

**严重度**: P2 (有替代路径，不阻塞)

**事实**:
- `USER_HOT_PATH` 只允许 `active` atoms (retrieval.py:116)
- FTS5 搜到的结果全是 `staged` (99.3%)
- 因此 `evomap_retrieve()` 在 context_service.py:935-941 始终返回空

**影响**:
- Planning role 的上下文实际只靠 pack search (226 atoms) 和 KB hub
- 101K+ staged atoms 中的知识无法被热路径访问

**不建议的做法**: 不要把 EvoMap retrieve 的 surface 改成 DIAGNOSTIC_PATH（会把未审核的 staged atoms 直接推给用户）

**建议方案**:
- 扩大 bootstrap allowlist 覆盖面 → 更多 atoms 进入 active
- 或在 pack search 的 RetrievalConfig 默认值中加入 staged（它已经有自己的 groundedness gate）

### P2: "统一逻辑任务层" 仅存在于设计文档

**严重度**: P2 (当前系统可用，但不支持跨 session 任务连续性)

**事实**:
- 设计文档: `docs/reviews/2026-04-02_planning_unified_logical_task_layer_v1.md`
- `logical_task_id` 在 `TelemetryEventInput` 中作为纯字符串字段存在 (telemetry_service.py:29)
- 用于 memory source attribution (memory_capture_service.py:277, telemetry_service.py:184)
- **没有 `LogicalTask` runtime 对象类的实现**

**影响**:
- 无法跨入口/跨会话追踪同一任务
- 不影响当前的 planning pack search 或 work memory

### P3: Pack 使用 token 匹配而非 FTS5

**严重度**: P3 (功能可用，但精度有限)

**事实**:
- `search_planning_runtime_pack()` 使用 `_tokenize()` + `_score()` (planning_runtime_pack_search.py:72-79) 做简单的 token 匹配
- 匹配逻辑: `sum(1 for token in query_tokens if token in haystack)` — 纯字符串子串匹配
- 不走 DB 的 FTS5 索引

**影响**:
- 对于 226 个 atoms 的小集合，性能不是问题 (5-15ms)
- 但精度不如 FTS5 (没有 BM25 排名、没有语言分析)
- 当 pack 扩大到 1000+ atoms 时可能需要升级

---

## 4. 体系架构健康度评估

| 维度 | 评分 | 依据 |
|---|---|---|
| 核心搜索管线 | ✅ 健康 | 7 queries × 5 hits, 5-15ms, all active+grounded |
| 数据完整性 | ✅ 健康 | 102K atoms 结构完整, 93.2% 已评分 |
| Promotion 机制 | ✅ 代码完整 | Engine + bootstrap + P4 batch + 审计追踪 |
| 自动化程度 | ⚠️ 需补齐 | 22 个脚本就绪但**零自动调度** |
| 上下文集成 | ✅ 健康 | 7 层 source 正确排序, planning role 优先级 0 |
| 测试覆盖 | ✅ 良好 | 29 个 planning 相关测试文件 |
| 新鲜度 | ⚠️ 退化中 | Pack 22 天未刷新, 但 DB 结构和数据仍可用 |

---

## 5. 优先行动建议

### 第一优先 (P1): 自动化 refresh + promotion

**目标**: 让 pack 自动刷新，不再依赖手动触发

**具体步骤**:
1. 创建 systemd timer (每日/每周) 运行:
   ```
   ops/run_planning_review_cycle.py → ops/build_planning_runtime_pack_release_bundle.py
   ```
2. 扩大 `apply_bootstrap_allowlist()` 的 doc_ids 覆盖面
3. 运行 `p4_batch_fix.py` 把当前 25 个 candidate 提升为 active

### 第二优先 (P2): 扩大 active atom 池

**目标**: 从 202 → 500+ active atoms

**具体步骤**:
1. 分析现有 101K staged atoms 的 quality/groundedness 分布
2. 对 quality ≥ 0.7 且有 canonical_question 的 staged atoms 执行 bootstrap
3. 建立 groundedness 批量检查管线

### 第三优先 (P2): Logical Task Layer 实现

只在跨会话任务连续性成为明确痛点后再做，不要提前实现。

---

## 附录 A: 运行时验证记录

### A1. Pack Search 7 组 golden query 测试

```
Query: 2026预算 关键数字    → 5 hits, 7ms,  top score=0.726
Query: 市场规模 两轮车      → 5 hits, 5ms,  top score=0.362
Query: 竞争对手 分析        → 5 hits, 6ms,  top score=0.382
Query: 组织架构 事业部      → 5 hits, 5ms,  top score=0.342
Query: 鹿小明 整机代工      → 5 hits, 15ms, top score=0.764
Query: 关节模组 BOM         → 5 hits, 7ms,  top score=0.368
Query: 预算 利润率          → 5 hits, 7ms,  top score=0.363
```

所有结果: promotion_status=active, groundedness=1.0

### A2. EvoMap Retrieve 路径验证

```
USER_HOT_PATH:   retrieve() 140ms → 0 hits (FTS5 results all staged)
DIAGNOSTIC_PATH: retrieve() 112ms → 0 hits (FTS5 results all staged, matching query tokens不足)
```

### A3. _ensure_rescored() 触发条件验证

```
Total atoms: 102,720
Zero quality: 6,956 (6.8%)
Trigger threshold: >50%
Would trigger: False
```

### A4. 测试覆盖验证

29 个 planning 相关测试文件，包括:
- `test_planning_runtime_pack_search.py` — 搜索逻辑 + runtime gate
- `test_audit_planning_runtime_pack_sensitivity.py` — 敏感信息审计
- `test_build_planning_runtime_pack_release_bundle.py` — bundle 构建
- `test_check_planning_runtime_pack_release_readiness.py` — 发布就绪检查
- `test_planning_review_plane.py` — review plane 全链路
- `test_planning_review_refresh.py` — 刷新管线
- `test_controller_engine_planning_pack.py` — 控制引擎集成
- `test_business_flow_planning_lane.py` — 业务流集成
- 等 21 个其他测试文件

### A5. 代码路径关键行号索引

| 模块 | 关键符号 | 行号 |
|---|---|---|
| `planning_runtime_pack_search.py` | `search_planning_runtime_pack()` | 137-249 |
| `planning_runtime_pack_search.py` | `_fetch_db_rows()` | 90-121 |
| `planning_runtime_pack_search.py` | `_passes_runtime_gate()` | 124-134 |
| `planning_runtime_pack_search.py` | `resolve_ready_planning_runtime_pack_bundle()` | 55-69 |
| `openmind_paths.py` | `resolve_evomap_knowledge_read_db_path()` | 88-107 |
| `openmind_paths.py` | `_is_legacy_evomap_knowledge_db()` | 22-26 |
| `retrieval.py` | `_ensure_rescored()` | 31-53 |
| `retrieval.py` | `retrieve()` — 调用 _ensure_rescored | 271 |
| `retrieval.py` | `RetrievalSurface.USER_HOT_PATH` | 69, 116 |
| `context_service.py` | `_SOURCE_KIND_MAP["planning_pack"]` | 30 |
| `context_service.py` | planning pack search integration | 862-905 |
| `context_service.py` | evomap retrieve integration | 925-959 |
| `context_service.py` | planning role priority=0 | 890 |
| `context_service.py` | prompt composition order | 476-495 |
| `promotion_engine.py` | `ALLOWED_TRANSITIONS` | 32-38 |
| `promotion_engine.py` | groundedness gate threshold | 71 |
| `planning_review_plane.py` | `apply_bootstrap_allowlist()` | 1242-1467 |
| `p4_batch_fix.py` | `promote_eligible_atoms()` | 41-94 |
| `work_memory_manager.py` | `_ACTIVE_CONTEXT_CATEGORIES` | 59-64 |
| `work_memory_manager.py` | `build_active_context()` | 258-321 |
| `telemetry_service.py` | `logical_task_id` field | 29 |
