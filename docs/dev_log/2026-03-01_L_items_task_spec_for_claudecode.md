# OpenMind v3 — L1-L9 延期项任务规格书

> 发给 Claude Code (Agent Teams) 执行

---

## 项目上下文

- **仓库**: `/vol1/1000/projects/ChatgptREST`
- **虚拟环境**: `.venv/bin/python` (Python 3.11)
- **框架**: FastAPI + LangGraph + SQLite
- **启动方式**: AGENTS.md 已描述完整运维体系
- **现状**: B1-B10 + R1-R7 全部完成, 4/4 场景 E2E 测试通过
- **KB**: 813 文档已索引 FTS5, 代码零 stub/TODO
- **核心代码路径**:
  - 路由 API: `chatgptrest/api/routes_advisor_v3.py`
  - 图管线: `chatgptrest/advisor/graph.py`
  - 报告管线: `chatgptrest/advisor/report_graph.py`
  - KB 模块: `chatgptrest/kb/` (hub.py, retrieval.py, registry.py, scanner.py, vector_store.py)
  - 内核: `chatgptrest/kernel/` (event_bus.py, memory_manager.py, policy_engine.py, effects_outbox.py)
  - 观测: `chatgptrest/observability/__init__.py`
  - 架构: `chatgptrest/advisor/` (funnel.py, evomap.py, dispatch.py, feishu_handler.py)
  - 契约: `chatgptrest/contracts/schemas.py`

---

## L1: EvoMap Dashboard API

**目标**: 暴露 EvoMap 演化信号为 REST API，供前端展示

**文件变更**:
- [NEW] `chatgptrest/api/routes_evomap.py` — FastAPI router
- [MODIFY] `chatgptrest/api/app.py` — 注册 evomap router
- [MODIFY] `chatgptrest/advisor/evomap.py` — 添加 signal 持久化 + 查询方法

**API 设计**:
```
GET  /v2/evomap/signals          → 最近 N 条信号 (type, value, timestamp)
GET  /v2/evomap/trends           → 按天聚合的趋势数据
GET  /v2/evomap/config           → 当前配置参数
POST /v2/evomap/config           → 更新配置参数 (需 API Key)
```

**实现约束**:
- EvoMap 信号已有 `_signal_log` 列表，需要持久化到 SQLite
- 查询支持 `?since=<datetime>&type=<signal_type>&limit=100`
- 认证: 复用 `routes_advisor_v3.py` 中的 `X-Api-Key` 模式

**验收标准**:
- `pytest tests/test_routes_evomap.py` 通过
- curl 能查到最近信号

---

## L2: Eval Harness 评估框架

**目标**: 标准化评估管线, 可对比不同 prompt/模型的输出质量

**文件变更**:
- [NEW] `chatgptrest/eval/harness.py` — 评估核心
- [NEW] `chatgptrest/eval/datasets.py` — 测试数据集管理
- [NEW] `chatgptrest/eval/scorers.py` — 评分器 (rouge, semantic_sim, llm_judge)
- [NEW] `chatgptrest/eval/__init__.py`
- [NEW] `scripts/run_eval.py` — CLI 入口
- [NEW] `eval_datasets/` — 存放 gold-standard 数据集

**核心类**:
```python
class EvalHarness:
    def __init__(self, dataset: EvalDataset, scorers: list[Scorer])
    def run(self, advisor_fn) -> EvalReport
    def compare(self, report_a, report_b) -> ComparisonReport

class EvalDataset:
    items: list[EvalItem]  # (input, expected_intent, expected_route, reference_answer)

class Scorer(ABC):
    def score(self, prediction: str, reference: str) -> float
```

**验收标准**:
- 包含至少 10 个 EvalItem 的默认数据集
- 支持 RougeScorer + LLMJudgeScorer
- `python scripts/run_eval.py --dataset default` 能输出 JSON 评分报告

---

## L3: 压力测试

**目标**: 并发负载 + 长时间稳定性测试

**文件变更**:
- [NEW] `tests/load/locustfile.py` — Locust 负载脚本
- [NEW] `tests/load/k6_script.js` — k6 负载脚本 (可选)
- [NEW] `scripts/run_stress_test.sh` — 一键压测脚本
- [NEW] `scripts/memory_leak_check.py` — 内存泄漏检测

**场景**:
- Quick ask: 40% 权重
- Deep research: 20% 权重
- Report: 20% 权重
- Build feature: 20% 权重

**指标**:
- P50/P95/P99 延迟
- QPS 峰值
- 内存增长曲线 (tracemalloc)
- 错误率

**验收标准**:
- `locust -f tests/load/locustfile.py --headless -u 5 -r 1 --run-time 5m` 可执行
- 脚本输出 JSON 报告 (latency, error_rate, memory_growth)

---

## L4: KB 文档版本管理

**目标**: FTS5 文档支持版本追踪、变更历史、rollback

**文件变更**:
- [MODIFY] `chatgptrest/kb/hub.py` — 添加 version tracking
- [NEW] `chatgptrest/kb/versioning.py` — 版本管理核心
- [MODIFY] `chatgptrest/kb/retrieval.py` — 搜索结果带版本号

**数据模型**:
```sql
CREATE TABLE kb_versions (
    doc_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    author TEXT DEFAULT 'system',
    change_note TEXT,
    PRIMARY KEY (doc_id, version)
);
```

**核心方法**:
```python
class KBVersionManager:
    def create_version(self, doc_id, content, author, change_note) -> int
    def get_version(self, doc_id, version=None) -> KBVersion  # None=latest
    def list_versions(self, doc_id) -> list[KBVersion]
    def diff(self, doc_id, v1, v2) -> str  # unified diff
    def rollback(self, doc_id, version) -> KBVersion
```

**验收标准**:
- `pytest tests/test_kb_versioning.py` 通过
- 文档更新自动创建新版本
- rollback 能还原 FTS5 索引

---

## L5: 可配置 EvoMap 信号

**目标**: EvoMap 信号类型/阈值通过配置文件调整

**文件变更**:
- [NEW] `config/evomap_signals.yaml` — 信号配置
- [MODIFY] `chatgptrest/advisor/evomap.py` — 从 YAML 加载配置
- [NEW] `chatgptrest/advisor/evomap_config.py` — 配置加载器

**配置格式**:
```yaml
signals:
  route_distribution:
    enabled: true
    threshold: 0.3
    window_size: 50
  response_quality:
    enabled: true
    min_score: 5.0
  latency_trend:
    enabled: true
    p95_warning: 60.0  # seconds
```

**验收标准**:
- 修改 YAML 后重启服务, 信号行为改变
- 删除/空 YAML → 使用默认值 (fail-safe)

---

## L6: 多模型辩论

**目标**: 同一问题发给多个 LLM, 对比/融合回答

**文件变更**:
- [NEW] `chatgptrest/advisor/debate.py` — 辩论核心
- [MODIFY] `chatgptrest/advisor/graph.py` — debate 路由选项
- [NEW] `chatgptrest/contracts/debate_schemas.py` — 辩论数据契约

**核心类**:
```python
class ModelDebate:
    def __init__(self, models: list[str], judge_model: str)
    async def debate(self, question: str, n_rounds: int = 1) -> DebateResult

class DebateResult:
    responses: dict[str, str]  # model_name -> response
    scores: dict[str, float]   # model_name -> score
    consensus: str             # 融合后的最终回答
    judge_reasoning: str
```

**实现约束**:
- 使用 `LLMConnector` 的多模型支持 (`chatgptrest/kernel/llm_connector.py`)
- 并发调用 (asyncio.gather), 不串行等待
- 默认 judge 用 qwen3-coder-plus
- 成本预估: 每次辩论 3x 单次 LLM 成本

**验收标准**:
- `pytest tests/test_debate.py` 通过
- API 支持 `{"mode": "debate", "models": ["qwen3-coder-plus", "deepseek-v3"]}` 参数

---

## L7: 飞书 Rich Card 增强

**目标**: 报告/研究结果推送飞书 Rich Card，支持折叠/展开

**文件变更**:
- [MODIFY] `chatgptrest/advisor/feishu_handler.py` — 增强 `FeishuCard`
- [NEW] `chatgptrest/advisor/feishu_cards/` — 卡片模板

**新增卡片功能**:
- 研究报告卡片: 摘要 + "展开全文" 折叠区
- 意图确认卡片: 已有（R1 完成），优化样式
- 进度通知卡片: 长任务的进度百分比 + 中间结果
- 错误通知卡片: 异常时推送简洁的错误摘要

**验收标准**:
- `FeishuCard.to_card_json()` 支持 `card_type` 参数区分类型
- 飞书 API 能接收并正确渲染

---

## L8: 用户偏好学习

**目标**: 根据历史交互调整路由偏好和输出风格

**文件变更**:
- [NEW] `chatgptrest/kernel/preference_engine.py` — 偏好学习核心
- [MODIFY] `chatgptrest/advisor/graph.py` — route 节点参考偏好
- [MODIFY] `chatgptrest/kernel/memory_manager.py` — 偏好数据存取

**核心逻辑**:
```python
class PreferenceEngine:
    def record_feedback(self, user_id, route, score, feedback_type)
    def get_preference(self, user_id) -> UserPreference
    def suggest_route_boost(self, user_id) -> dict[str, float]  # route -> boost factor
```

**数据来源**:
- 飞书卡片"确认/修改/拒绝"的反馈 (R1 已有)
- review pass/fail 的历史
- 路由统计 (meta memory: route_stat)

**验收标准**:
- 10+ 次同类型请求后, route boost 可观测变化
- 偏好数据持久化到 memory.db

---

## L9: 多租户支持

**目标**: 不同用户/团队独立的 KB、memory、config

**文件变更**:
- [NEW] `chatgptrest/kernel/tenant.py` — 租户管理
- [MODIFY] `chatgptrest/kb/hub.py` — per-tenant FTS5
- [MODIFY] `chatgptrest/kernel/memory_manager.py` — per-tenant memory
- [MODIFY] `chatgptrest/api/routes_advisor_v3.py` — tenant 路由

**核心设计**:
```python
class TenantManager:
    def get_or_create(self, tenant_id: str) -> TenantContext
    def list_tenants(self) -> list[str]

class TenantContext:
    kb_hub: KBHub           # tenant-specific KB
    memory: MemoryManager   # tenant-specific memory
    config: dict            # tenant-specific config overrides
```

**实现约束**:
- 默认租户: `default` (向后兼容)
- 租户 ID 从 API header `X-Tenant-Id` 获取
- 每个租户独立的 SQLite 文件: `~/.openmind/tenants/{tenant_id}/`

**验收标准**:
- 不传 `X-Tenant-Id` → 使用 default tenant (向后兼容)
- 不同 tenant 的 KB 搜索结果互相隔离

---

## 执行建议

1. **并行分组**: L1+L5 (EvoMap), L2+L3 (测试), L4 (KB), L6 (LLM), L7+L8 (UX), L9 (架构)
2. **优先级**: L1 > L4 > L2 > L7 > L5 > L6 > L3 > L8 > L9
3. **每个 L 完成后**: 提交 git commit, 运行 `pytest -q`, 不要破坏现有 4/4 场景测试
4. **测试文件**: 每个新模块必须有对应的 `tests/test_*.py`
5. **代码规范**: 遵循现有 fail-open 模式, 新功能缺配置不致命

## 约束

- 不要修改 `/vol1/maint/MAIN/secrets/` 下的任何文件
- 不要输出密钥内容
- 不要重启非 chatgptrest 相关的服务
- 保持现有 4/4 场景测试能通过
