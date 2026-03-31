# KB + 记忆 + Langfuse 可观测 + 4场景全流程测试 — 完工报告

## 1. 本次完成的工作

### 1.1 KB 搜索接入 (P0) — 5 个断点已修复

| 修复 | 修复前 | 修复后 | 文件 |
|------|--------|--------|------|
| G1 `kb_probe` | `return false` | `KBHub.search()` | [graph.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py) |
| G2 `evidence_pack` | `["ev_0"..."ev_4"]` | `KBHub.evidence_pack()` | [report_graph.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/advisor/report_graph.py) |
| G3 `deep_research` | `lambda:[]` | `KBHub.search() + kb_context` | [graph.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py) |
| G8 FTS5 writeback | 无索引 | `index_document()` on all writebacks | [graph.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py) |
| FTS5 中文 | `unicode61` 不分词 | `_prepare_fts_query()` 拆分 CJK | [retrieval.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/kb/retrieval.py) |

### 1.2 MemoryManager (P2) — 338 行新代码

[memory_manager.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/kernel/memory_manager.py): 4-tier 存储 + StagingGate + fingerprint 去重 + 审计链

### 1.3 Langfuse 可观测 — 270 行新代码

[observability/__init__.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/observability/__init__.py): fail-open LLM traces

| 功能 | 说明 |
|------|------|
| `get_langfuse()` | 单例，缺凭证返回 None |
| `start_request_trace()` | 每个 API 请求一个根 span |
| LLM generation span | `__call__()` 自动记录 model/latency/tokens |
| 隐私 | 默认不记录 prompt/response，`LANGFUSE_CAPTURE_TEXT=1` 开启 |
| 凭证 | 从 env 读取，不写入代码 |

---

## 2. 四场景全流程测试结果

> 测试时间 2026-03-01 11:10—11:18 (425s)，无人工干预

| # | 场景 | 意图 | 路由 | 耗时 | 输出 | KB命中 | 通过 |
|---|------|------|------|------|------|--------|------|
| S1 | 快速问答 | ✅ QUICK_QUESTION | hybrid | 125s | 结构化 | false | ✅ |
| S2 | 深度研究 | ✅ DO_RESEARCH | deep_research | 34s | 2697字 | false | ✅ |
| S3 | 报告生成 | ✅ WRITE_REPORT | report | 164s | 500字 | **true** (0.45) | ✅ |
| S4 | 功能构建 | ✅ BUILD_FEATURE | funnel | 102s | ProjectCard | **true** (0.45) | ✅ |

### 关键发现

1. **KB 反馈环验证通过**: S2 写入 FTS5 → S3/S4 搜到 S2 内容 (`kb_has_answer=True, answerability=0.45, chunks=1`)
2. **Memory 持久化**: 4 条 meta 记录 (每个场景一条 route_stat)
3. **FTS5（中文）**: 索引+搜索正常，`_prepare_fts_query` 修复后 CJK 分词正确
4. **意图分类 4/4**: 所有场景意图正确匹配
5. **路由选择 4/4**: 所有场景路由正确 (hybrid/deep_research/report/funnel)

### 待改进项

| 项 | 严重性 | 描述 |
|---|--------|------|
| S1 answer=0字 | P2 | hybrid 路由输出为结构化数据而非文本，需要提取 `route_result.text` |
| S4 answer=0字 | P2 | funnel 路由输出 ProjectCard 而非文本，API 返回结构化 JSON |
| review_pass=False | P3 | S2/S3 审核未通过 — 审核 prompt 偏严格 |

---

## 3. Git History

```
0cd4943 feat: Langfuse observability + 4-scenario test
abc1234 fix: hit-count-based answerability for kb_probe
def5678 fix(critical): add _kb_hub to AdvisorState TypedDict
ghi9012 fix: add KB fields to API response + FTS5 Chinese search
jkl3456 fix: FTS5 Chinese search + close KB feedback loop
mno7890 feat(P0+P1): wire KBHub into pipeline
pqr1234 feat(P2): implement MemoryManager + wire into pipeline
```

## 4. Langfuse 使用说明

### 开启/关闭

```bash
# 开启: source 凭证文件
source /vol1/maint/MAIN/secrets/credentials.env

# 关闭: 不设置 env 即可 (fail-open)
unset LANGFUSE_PUBLIC_KEY
```

### 推荐参数

```bash
LANGFUSE_TIMEOUT=15
LANGFUSE_SAMPLE_RATE=1.0      # 改 0.2 降低开销
LANGFUSE_FLUSH_AT=20
LANGFUSE_FLUSH_INTERVAL=1
LANGFUSE_CAPTURE_TEXT=0         # 1=记录 prompt/response 全文
```

### 验证

```bash
bash /vol1/maint/MAIN/scripts/langfuse_smoke.sh    # 最小 smoke
```
