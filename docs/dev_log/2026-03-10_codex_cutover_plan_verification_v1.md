# Codex DB Cutover Plan — Independent Verification

**Date:** 2026-03-10  
**Verifier:** Antigravity  
**Source:** Codex's cutover plan (6 items) + noise analysis  
**Method:** Read every cited file + queried both databases directly

---

## 1. "定 authoritative DB" — ✅ Correct

> `EVOMAP_KNOWLEDGE_DB=/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db`  
> runtime 已经按这条线走。openmind_paths.py#L43 runtime.py#L352

**Verdict: Correct.**

- `openmind_paths.py` L54-64 `resolve_evomap_knowledge_runtime_db_path()` 默认返回 `_CANONICAL_EVOMAP_KNOWLEDGE_DB = REPO_ROOT / "data" / "evomap_knowledge.db"` (L15)
- L14 把 `~/.openmind/evomap_knowledge.db` 显式标记为 `_LEGACY`
- L61 有个 **legacy guard**：即使 `EVOMAP_KNOWLEDGE_DB` env 设置为旧路径，也会主动拒绝、落回 canonical 路径
- 这个 guard 设计得很好，说明代码已经有意识地防止走回旧路径

---

## 2. "改掉仍默认写旧库的入口" — ⚠️ 方向正确但事实有误

Codex 列了 4 个需要改的入口：

| Codex 声称 | 实际情况 | 判定 |
|---|---|---|
| `run_atom_refinement.py#L48` | L49: `_DEFAULT_DB = resolve_evomap_knowledge_runtime_db_path()` — **已经用 resolve 函数** | ❌ 不需要改 |
| `p4_batch_fix.py#L208` (暗示在 ops/) | 实际路径是 `chatgptrest/evomap/knowledge/p4_batch_fix.py`。L17: `_DEFAULT_DB = resolve_evomap_knowledge_runtime_db_path()` — **已经用 resolve 函数** | ❌ 不需要改 |
| `db.py#L231` | L231: `self.db_path = db_path or os.environ.get("EVOMAP_DB_PATH", DEFAULT_DB_PATH)`。`DEFAULT_DB_PATH` = `data/evomap_knowledge.db` (L31-33)。默认已指向 canonical | ⚠️ 有风险但已正确 |
| `relations.py#L84` | L85: `self.db_path = db_path or os.environ.get("EVOMAP_DB_PATH", DEFAULT_DB_PATH)`。`DEFAULT_DB_PATH` = `data/evomap_knowledge.db` (L17-19) | ⚠️ 有风险但已正确 |

**总结：Codex 认为这些入口"仍然默认写旧库"是错误的。** 4 个入口全部已经默认指向 `data/evomap_knowledge.db`。两条 resolve 函数路径已修好（可能是 Codex 看的是更早的 snapshot），两条 `EVOMAP_DB_PATH` fallback 的 DEFAULT 也是 canonical 路径。

**但有一个真实风险 Codex 没准确指出**：`db.py:231` 和 `relations.py:85` 仍使用 `EVOMAP_DB_PATH` 作为 env var 名（而非 `EVOMAP_KNOWLEDGE_DB`）。如果用户在环境里设了 `EVOMAP_DB_PATH=~/.openmind/evomap_knowledge.db`，这两个入口会绕过 legacy guard。这才是真正需要统一的点。

---

## 3. "统一 env 语义" — ✅ 方向正确，但需要补充

Codex 的 env 语义建议：

| Env Var | Codex 建议 | 实际用途验证 |
|---|---|---|
| `EVOMAP_KNOWLEDGE_DB` | 唯一知识库路径 | `openmind_paths.py` L58 只查这个 + legacy guard ✅ |
| `EVOMAP_DB_PATH` | 废弃 | **但 `db.py:231` 和 `relations.py:85` 仍在用这个 env** — 如果废弃需要改代码 |
| `OPENMIND_EVOMAP_DB` | 只给 observer/signals | 没有在知识库路径代码中找到引用 ✅ |
| `OPENMIND_EVO_DB` | legacy alias | 没有在知识库路径代码中找到引用 ✅ |

**真正需要做的修改：** `db.py` L231 和 `relations.py` L85 的 `EVOMAP_DB_PATH` fallback 应改成 `EVOMAP_KNOWLEDGE_DB`，或直接用 `resolve_evomap_knowledge_runtime_db_path()`（这样就自动继承 legacy guard）。

---

## 4. "标记旧库 deprecated" — ✅ 合理

> 移到归档名 + manifest

没有争议。

---

## 5. "保证未来只入主库" — ✅ 方向正确，但噪声数据有误差

### source contract 建议

Codex 说：
> - `documents.source` = extractor/system 名  
> - `documents.project` = 业务域/仓库  
> - 不再出现"project='research' 但 source='planning'"这种混用

**验证：** 主库当前 source 分布：

| source | doc count | atom count |
|---|---|---|
| planning | 3,350 | 40,901 |
| chatgptrest | 2,213 | 2,475 |
| antigravity | 1,113 | 50,783 |
| maint | 446 | 438 |
| md | 6 | 110 |
| agent_activity | 4 | 275 |
| commits | 2 | 44 |
| openclaw | 1 | 1 |
| ops_incident | 1 | 5 |

> [!WARNING]
> **主库里没有 `source='research'` 的任何文档。** Codex 说"research: 951 docs"——这在当前主库中完全不存在。要么 Codex 看的是不同的数据库快照，要么这个数字来自别的来源。

### 噪声分析对比

| Codex 声称 | 实际查询结果 | 判定 |
|---|---|---|
| planning 有 1,101 个 `_review_pack` 文档 | **25 个** | ❌ 偏差 44× |
| research 有 939 个 `archives/` 文档 | **0 个** (research source 不存在) | ❌ 完全错误 |
| planning 有 181 个噪声标题 (answer/MANIFEST/CHANGELOG/VERSION) | **467 个** (364 answer + 103 MANIFEST/CHANGELOG/VERSION) | 方向对但数字不同 |
| research 有 71 个噪声标题 | 不可验证 (无 research 数据) | N/A |

**结论：Codex 的噪声判断方向是对的（planning 里确实有大量 `answer` 标题噪声），但数字严重不准确。** 最大的误差是 `_review_pack` (25 vs 声称的 1101) 和 research 源完全不存在。

---

## 6. "怎么导入" — ⚠️ 需要辩论

Codex 建议"不要从旧库拷贝行，从源材料重建"。

### 支持这个建议的论点

- 保证 provenance 完整（每个 atom 都通过 extractor 路径进入）
- Extractor 会走 scoring contract，保证 quality_auto 一致
- 避免旧库的 promotion_status (active) 直接带入、绕过治理

### 反对这个建议的论点

1. **源材料已不可复原的部分**：scratch 库里 2,700 atoms 来源是 Antigravity 会话。主库已经有 50,783 个 antigravity 源 atoms（同样的会话，不同的提取器跑出来的）。从源材料重新开始不会给你 scratch 库里的那些 **LLM-refined canonical questions** 和 **chain governance 数据** — 这些是额外的 curation 产物，不是原始提取。
   
2. **Chain ID 是唯一有价值的治理数据**：主库 95K atoms 全部 chain_id=空，scratch 库 2,376 chains 是 P1 chain builder 的真实输出。这不是"源材料重建"能得到的 — 除非在主库上重跑 P1 chain builder。

3. **量级问题**：scratch 库只有 2,700 atoms (主库的 2.8%)。即使全量 `INSERT OR IGNORE` + reset promotion，对主库的污染风险极低。而"从源材料重建"意味着重跑所有 antigravity 会话的提取 — 但主库已经有这些。

### 我的建议

**分两条线并行：**
- **旧库的 2,700 unique atoms：** 不做 blind row merge，也不强制走 extractor 重建。而是 **只导入 chain governance 元数据**（chain_id, chain_rank, is_chain_head, canonical_question）到主库中对应的 atoms 上（通过内容匹配而非 atom_id 对齐）。这保留了 curation 价值，不引入 promotion_status 污染。
- **主库 95K atoms：** 等 pipeline 重新启用后，跑 P1 chain builder + P2 groundedness。这是规模化收益最大的路径。

---

## 7. Runtime 只扫 ~/brain + openmind/docs — ✅ Correct

`runtime.py` L584-588:
```python
NoteSectionExtractor(
    evomap_knowledge_db,
    source_dirs=[
        os.path.expanduser("~/brain"),
        os.path.expanduser("/vol1/1000/projects/openmind/docs"),
    ],
).extract_all()
```

**确认：** runtime 的 NoteSectionExtractor 确实只扫这两个目录。planning/research 的大量数据（3,350 planning docs, 40,901 planning atoms）不是 runtime 产生的，而是历史一次性批量导入。Codex 的推断正确。

---

## 8. chat_followup `estimate_value()` 不做真正过滤 — ✅ Correct

`chat_followup.py` L442: `value = estimate_value(job)` 被调用后，只是作为 `doc_value` 输入到 `ScoreComponents` (L457)，最终影响 `quality_auto`。没有地方拿 `estimate_value()` 做硬过滤（如 `if value < threshold: skip`）。

实际的硬过滤只在 `is_execution_only()` (L206-220)：
- `answer_chars < 100` → 跳过
- 非 ask job → 跳过
- 未完成 → 跳过
- 空 question → 跳过

**这意味着：** 只要 answer >= 100 chars，任何 question 都会入库，哪怕是 `天气` / `ping` / `自检建议`。Codex 的判断正确。

---

## 总结评分卡

| 项目 | Codex 判断 | 实际验证 | 评分 |
|---|---|---|---|
| Authoritative DB 选择 | data/ | Correct | ✅ |
| 需要改的脚本入口 | 4 个 | **全部已改好** | ❌ 过时信息 |
| Env 统一 | 方向正确 | `EVOMAP_DB_PATH` 在 db.py/relations.py 仍是风险点 | ⚠️ |
| 旧库归档 | 合理 | 无争议 | ✅ |
| Planning 噪声 (review_pack) | 1,101 | **25** | ❌ |
| Research 文档数 | 951 | **0** (source 不存在) | ❌ |
| 导入方式 (extractor 重建) | 推荐 | 部分合理，但忽略 chain curation 价值 | ⚠️ |
| Runtime scan 范围 | ~/brain + openmind/docs | Correct | ✅ |
| estimate_value 未做 gate | Correct | Correct | ✅ |
| 使用场景总判 | 先收紧边界再批量导入 | **方向正确，但先确认脚本已不需要改** | ✅ 战略正确 |

> [!IMPORTANT]
> Codex 的宏观判断（先定 canonical、收紧边界、再批量导入）是**正确的战略方向**。但微观事实（行号引用、数量级、脚本状态）有多处不准确。建议基于本轮核验结果调整实施文档。
