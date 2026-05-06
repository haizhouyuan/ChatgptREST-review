# 2026-03-22 Phase 5 Knowledge Runtime Rebalance Review Walkthrough v1

## 我做了什么

1. 确认当前 `HEAD` 在 `8b4c01f`，worktree 干净
2. 核对了实现提交 `7598dd7` 和阶段文档范围
3. 逐段检查了这些 live 文件：
   - `chatgptrest/advisor/graph.py`
   - `chatgptrest/cognitive/ingest_service.py`
   - `chatgptrest/cognitive/context_service.py`
   - `chatgptrest/api/routes_cognitive.py`
4. 复跑了 Phase 5 指定回归与 `py_compile`
5. 额外直打了一次 `/v2/knowledge/ingest`，检查公开 response 形状

## 关键核验结果

### 主链成立

- advisor graph 最终产物写回现在都走 `KnowledgeIngestService`
- graph 上层消费到的 `kb_writeback` 已能区分 `knowledge_plane` / `write_path`
- `kb.writeback` telemetry 带 plane/path
- `/v2/context/resolve` 已能解释 `source_planes` 和 `retrieval_plan`

### 发现的问题

公开 `/v2/knowledge/ingest` response 还没完全 flatten：

- 顶层 item 返回 `ok` / `accepted` / `message`
- `knowledge_plane` / `write_path` 还在 `graph_refs`
- 顶层没有 `success`

这和阶段文档写的“返回值显式带这些字段”相比，口径偏强了一步。

## 复跑记录

```bash
./.venv/bin/pytest -q \
  tests/test_advisor_graph.py \
  tests/test_report_graph.py \
  tests/test_funnel_kb_writeback.py \
  tests/test_cognitive_api.py \
  tests/test_substrate_contracts.py

python3 -m py_compile \
  chatgptrest/advisor/graph.py \
  chatgptrest/cognitive/ingest_service.py \
  chatgptrest/cognitive/context_service.py \
  tests/test_advisor_graph.py \
  tests/test_cognitive_api.py
```

结果：

- `pytest` 全通过
- `py_compile` 通过

## 定向 API 复现

使用开放认证直打：

```bash
OPENMIND_AUTH_MODE=open ./.venv/bin/python - <<'PY'
from fastapi.testclient import TestClient
from chatgptrest.api.app import create_app
...
resp = client.post('/v2/knowledge/ingest', json={...})
print(resp.json())
PY
```

实际返回结构确认：

- `results[0].accepted = true`
- `results[0].graph_refs.knowledge_plane = canonical_knowledge`
- `results[0].graph_refs.write_path = canonical_projected`
- `results[0]` 没有顶层 `success`

## 落盘原因

这轮不是代码修复，而是阶段核验与质量评审。需要把“主链通过，但公开 ingest response contract 还差半步”单独落档，避免后续把 Phase 5 误认成已经全 surface 收口。
