# 生产上线差距分析 + 初始目标未达标清单

> 2026-03-01 | 基于全部文档和代码审计

---

## 一、距离生产上线还差什么

### 1. 必须做（上线阻断项）

| # | 工作项 | 现状 | 需要做什么 | 预估 |
|---|--------|------|-----------|------|
| **B1** | **report_graph 缺少核心节点** | 248行，只有 purpose_identify/evidence_pack/draft/review/finalize 骨架 | 补充 `internal_draft`→`external_draft` 双稿模式、`redact_gate` 脱敏门控、`publish` 发布环节 | 4h |
| **B2** | **funnel_graph 缺少 Gate 评审** | 373行，3段但 Gate A/B/C rubric 评分是 stub | 实现 6维 rubric 评分逻辑、Gate B 异步暂停/恢复机制 | 3h |
| **B3** | **hybrid_search 未实现** | `retrieval.py` 只有 FTS5，无向量检索、无 RRF 融合 | 集成 `vector_store.py` + RRF 融合算法 + fallback 降级 | 3h |
| **B4** | **quick_ask 无文本输出** | S1测试 answer=0字，hybrid 路由返回结构化数据但无文本答案 | 在 `execute_quick_ask` 中调 LLM 生成自然语言答案 | 1h |
| **B5** | **EventBus 未接入 pipeline** | `event_bus.py` 245行完整，但 graph.py 中 0 处调用 | 在 route_decision/writeback/gate 等关键节点 emit 事件 | 2h |
| **B6** | **PolicyEngine 未接入 finalize** | `policy_engine.py` 303行完整，但 graph.py 中 0 处调用 | 在 report finalize + KB writeback + dispatch 前做策略检查 | 2h |
| **B7** | **review_pass 全部返回 False** | 4场景测试中 S2/S3 review_pass=False | 调整 review prompt 或 review 评分阈值 | 1h |
| **B8** | **Langfuse 服务端 env 未持久化** | 凭证在 shell 中 source，nohup 进程未继承 | 用 systemd EnvironmentFile= 或启动脚本 source | 0.5h |
| **B9** | **KB 准入门控 (quarantine)** | `registry.py` 无 quarantine/stability 字段 | 新增 stability 状态机 + quarantine_weight，自动写入设为 draft | 2h |
| **B10** | **错误恢复 / Checkpoint** | graph 无 checkpoint 持久化，进程崩溃数据全丢 | 启用 LangGraph SqliteSaver checkpoint | 1h |

### 2. 应该做（上线前推荐）

| # | 工作项 | 现状 | 需要做什么 | 预估 |
|---|--------|------|-----------|------|
| **R1** | **飞书通知 UX 优化** | feishu_handler 可工作，但卡片无意图重述和确认按钮 | 改造卡片模板，添加意图重述/风险提示/按钮 | 2h |
| **R2** | **hcom Agent Teams 真实派发** | `dispatch.py` 246行有 ProjectCard→Context 组装，实际 hcom 调用是 stub | 接入 hcom CLI/API 真实执行 | 3h |
| **R3** | **OpenClaw KB 数据迁移** | `scripts/migrate_openclaw_kb.py` 存在但未执行 | 导入 1647 文档到 KB Hub，验证 FTS5+向量索引 | 2h |
| **R4** | **Memory → Episodic 记录** | MemoryManager 只记 route_stat 到 Meta | 添加任务结果/研究摘要到 Episodic 层 | 1h |
| **R5** | **ArtifactStore 规范化写回** | 研究/报告写回用 ad-hoc JSON，未走 ArtifactStore | 统一用 ArtifactStore + ArtifactRegistry 管理 | 2h |
| **R6** | **API 认证** | `/v2/advisor/advise` 无认证 | 添加 API Key 或 JWT 认证 | 1h |
| **R7** | **速率限制** | 无请求限流 | 添加基于 IP/用户的限流 | 1h |

### 3. 可以后做（上线后迭代）

| # | 工作项 | 现状 | 说明 |
|---|--------|------|------|
| **L1** | EvoMap Dashboard API | 文件不存在 | Phase 4.2，需要 EvoMap Observer 先积累足够数据 |
| **L2** | Eval Harness (50条金标) | `tests/eval/` 不存在 | Phase 4.4，需要收集真实查询 |
| **L3** | 压力测试 | 无 | Phase 5.4，连续 10 条不同需求 |
| **L4** | KB Doc Version 版本追踪 | registry.py 无 doc_version | Phase 1.4 增强 |
| **L5** | EvoMap 信号可配置化 | observer 硬编码信号类型 | R6 进化策略可配置化 |
| **L6** | 多模型辩论/交叉验证 | LLMConnector 单模型+fallback | D1+D4 需求 |

---

## 二、初始目标 vs 当前达标状况

### 来源：`needs_analysis.md` — 4个核心痛点

| 痛点 | 初始目标 | 当前状态 | 达标？ |
|------|---------|---------|--------|
| **框架不对** — AI 不知道用哪套稿件 | 自动匹配目的矩阵 → 选模块组合 | `purpose_identify` 存在但未集成三套稿体系 | ⚠️ 30% |
| **深度不够** — AI 没有证据包和 KB | 自动 kb_pack → 证据包 | KB probe ✅ 已接入，evidence_pack ✅ 已接入 | ✅ 70% |
| **需求没理解准** — 选错了模块组合 | 目的识别 → 智能选择 | `analyze_intent` 4/4 意图识别正确 | ✅ 80% |
| **多次迭代才能用** — 链条太长 | 端到端自动管线 | 4场景可跑，但 review_pass=False，无自动脱敏/发布 | ⚠️ 50% |

### 来源：`needs_analysis.md` — 6步报告管线

| 步骤 | 目标 | 代码存在？ | 真正工作？ |
|------|------|-----------|-----------|
| 1. 目的识别 | 自动匹配目的矩阵 | ✅ `purpose_identify` | ⚠️ 未对接三套稿体系 |
| 2. 证据装载 | 自动 kb_pack | ✅ `evidence_pack` → KBHub | ✅ 工作 |
| 3. 底稿生成 | 用底稿 prompt + 证据包 | ✅ `internal_draft` | ⚠️ 单一 prompt，未用底稿模板 |
| 4. 外发稿生成 | 用外发 prompt + 底稿结论 | ❌ 无分离的外发稿节点 | ❌ 缺失 |
| 5. Pro 复审 | 调用复审 prompt | ✅ `pro_review` 节点存在 | ⚠️ review_pass 全返回 False |
| 6. 脱敏 + 发布 | kb_redact → dingtalk_publish | ❌ redact_gate 未实现 | ❌ 缺失 |

### 来源：`refactoring_requirements.md` — R1-R9

| 需求 | 描述 | 当前状态 |
|------|------|---------|
| R1 事件总线升级 | EventBusPort 接口 + async | ✅ event_bus.py 存在(245行) | ⚠️ 未接入 graph |
| R2 God Object 拆解 | server.impl.ts 拆分 | ✅ 已拆为 routes + advisor_api + graph |
| R3 Runtime Pipeline 分解 | run.ts 拆结构 | ✅ LangGraph graph 已实现 |
| R4 Route Resolver 优化 | O(1) 查询 | ✅ compute_all_scores + select_route |
| R5 Hook Transform 安全隔离 | TransformRunnerPort | ❌ 未做 (Python 项目，不适用) |
| R6 EvoMap 进化策略可配置化 | Gene Template | ⚠️ observer 存在但策略硬编码 |
| R7 EvoMap 状态持久化 | SignalStorePort | ✅ observer.py 用 SQLite |
| R8 可测试性基建 | InMemoryEventBus 等 | ⚠️ LLMConnector.mock() 存在，其他不足 |
| R9 统一事件 Envelope | EventEnvelope + DiagnosticEvent | ❌ 未做 |

### 来源：`implementation_roadmap.md` — Phase 0-5 (25 Tasks)

| Phase | 任务数 | 已完成 | 部分完成 | 未开始 |
|-------|--------|--------|---------|--------|
| Phase 0: Bug Fix | 4 | 3 | 1 (PipelineRunner LRU未确认) | 0 |
| Phase 1: Kernel | 5 | 3 | 2 (向量混合检索, KB治理增强) | 0 |
| Phase 2: Core | 5 | 4 | 1 (report_graph 双稿) | 0 |
| Phase 3: Integration | 4 | 3 | 1 (hcom 真实派发) | 0 |
| Phase 4: EvoMap+KB | 4 | 1 | 1 (KB迁移脚本存在未执行) | 2 (Dashboard API, Eval) |
| Phase 5: E2E | 4 | 1 (4场景跑通) | 0 | 3 (压力测试, checkpoint恢复) |

**总计: 25 Tasks → 15 完成 / 5 部分完成 / 5 未开始 = 60% 达标**

### 来源：`implementation_roadmap.md` — 7个关键里程碑

| 里程碑 | 目标 | 状态 |
|--------|------|------|
| M1: 基座稳定 | 所有现有测试通过 + critical bugs 修复 | ✅ |
| M2: KB Hub 可用 | FTS5+向量混合检索 <5ms | ⚠️ FTS5 ✅，向量 ❌ |
| M3: 第一份报告 | report_graph 产出完整报告 | ⚠️ 500字但缺双稿分离 |
| M4: 第一个 ProjectCard | funnel_graph 产出 ProjectCard | ✅ funnel_complete |
| M5: API 上线 | POST /v2/advisor/advise 全链路 | ✅ 4/4 场景通过 |
| M6: 飞书集成 | 飞书发消息 → 自动处理 → 返回 | ⚠️ 接收 ✅，卡片 UX ❌ |
| M7: 全量验证 | 5条E2E + eval 50条 ≥80% | ⚠️ 4条 E2E ✅, eval ❌ |

---

## 三、生产上线最小可行清单 (MVP)

如果只做最少的事情让系统能在生产环境工作：

```
必须做 (10项, ~20h):
  B1  report_graph 双稿 + 脱敏         4h
  B3  hybrid_search (FTS5+向量+RRF)    3h
  B4  quick_ask 文本输出               1h
  B5  EventBus 接入 graph              2h
  B6  PolicyEngine 接入 finalize       2h
  B7  review 评分阈值调优              1h
  B8  Langfuse env 持久化             0.5h
  B9  KB quarantine / stability        2h
  B10 Checkpoint 持久化               1h
  B2  funnel Gate rubric 实现          3h
                                    ─────
                             合计   ~19.5h
```

### 优先级建议

```
Day 1 (8h):  B3 + B4 + B5 + B6  → 核心管道补齐
Day 2 (8h):  B1 + B7 + B9       → 报告链路完善
Day 3 (4h):  B2 + B8 + B10      → 漏斗 + 运维
```
