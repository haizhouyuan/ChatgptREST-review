# KB + 记忆管理 + 内核接入

## P0: KB 搜索接入 ✅
- [x] G1: `kb_probe` → `KBHub.search()` (graph.py)
- [x] G2: `evidence_pack` → `KBHub.evidence_pack()` (report_graph.py)
- [x] G3: `deep_research` KB → `KBHub.search()` (graph.py)
- [x] 初始化 KBHub 并注入 state (routes_advisor_v3.py)
- [x] FTS5 Chinese text search fix (`_prepare_fts_query`)
- [x] `_kb_hub` added to AdvisorState TypedDict
- [x] KB fields in API response (advisor_api.py)
- [x] Hit-count-based answerability

## P1: KB Writeback 规范化 ✅
- [x] G4/G8: writeback 后 index 到 KBRetriever (FTS5)
- [ ] G4: 用 ArtifactStore 替代 ad-hoc JSON 写入 (后续)

## P2: MemoryManager 实现 ✅
- [x] G5: 实现 MemoryManager (Working/Episodic/Semantic/Meta)
- [x] G5: 实现 StagingGate 写入门控
- [x] G5: 接入 pipeline (route_decision → Meta memory)

## P3: EventBus + PolicyEngine (后续)
- [ ] G7: EventBus 替代 `_emit()` 内联
- [ ] G6: PolicyEngine 接入 finalize 前质量门控

## 验证结果
- [x] 2-pass: Pass 1 indexes → Pass 2 finds (kb_has_answer=True, answerability=0.45, chunks=1)
- [x] MemoryManager: meta tier 1 record, audit trail (stage→promote)
- [x] FTS5: 1 doc indexed on writeback
