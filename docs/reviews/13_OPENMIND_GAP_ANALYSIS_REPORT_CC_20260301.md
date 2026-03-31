# OpenMind 项目上线差距分析评审报告

**审核：CC 审核**
**日期：2026-03-01**

---

## 一、项目全景回顾

### 1.1 架构设计

```
User Request → Advisor Graph → [Quick Ask | Deep Research | Funnel Graph] → KB ↔ EvoMap
```

### 1.2 技术栈

| 组件 | 选择 |
|------|------|
| Workflow Engine | LangGraph |
| Vector DB | Qdrant |
| Embedding | fastembed |
| Full-text Search | SQLite FTS5 + jieba |
| REST API | FastAPI |
| Observability | TraceEvent EventBus (SQLite) |
| Agent Execution | OpenClaw MCP |

### 1.3 已实现的核心模块

- `openmind/kernel/artifact_store.py` — 内容寻址存储（含 provenance 追踪）
- `openmind/kernel/event_bus.py` — TraceEvent 事件总线（SQLite 持久化）
- `openmind/kernel/policy_engine.py` — 策略引擎（6 个质量门检查器）

---

## 二、生产上线差距分析

### 2.1 核心模块缺失（阻断性）

| 模块 | 状态 | 说明 |
|------|------|------|
| `model_router` | ❌ 未实现 | docs 指定需实现 `openmind/integrations/model_router.py` + providers/ |
| `advisor/` | ⚠️ 空目录 | Advisor Graph 核心路由逻辑缺失 |
| `workflows/` | ⚠️ 空目录 | Quick Ask / Deep Research / Funnel Graph 工作流未实现 |
| `kb/` | ⚠️ 空目录 | 知识库检索模块缺失 |
| `evomap/` | ⚠️ 空目录 | EvoMap 演进映射模块缺失 |
| `contracts/` | ⚠️ 空目录 | 契约/接口定义缺失 |
| `integrations/` | ⚠️ 空目录 | 外部集成占位符 |

### 2.2 模型路由通道（关键功能）

#### 2.2.1 需实现的 provider

| Provider | 状态 | 说明 |
|----------|------|------|
| `openai_compatible.py` (Coding Plan) | ❌ 未实现 | 阿里百炼 OpenAI 兼容通道 |
| `anthropic_compatible.py` (MiniMax) | ❌ 未实现 | MiniMax Anthropic 兼容通道 |
| `cli_bridge.py` | ❌ 未实现 | codex/gemini/claude CLI 桥接 |
| `chatgptrest_bridge.py` | ❌ 未实现 | ChatGPT/Gemini Deep Research 通道 |

#### 2.2.2 接口未实现

```python
# 文档定义的接口（docs_model_routing_for_antigravity_2026-02-28.md）
class RouteRequest(BaseModel):
    intent: str
    risk_level: str = "low"
    latency_budget_ms: int = 30000
    require_tool_calling: bool = False

class RouteDecision(BaseModel):
    primary: str
    fallback: list[str]
    reason: str

class ModelRouter:
    def route(self, req: RouteRequest) -> RouteDecision: ...
    def invoke(self, route: RouteDecision, prompt: str) -> dict: ...
```

### 2.3 验证清单未完成

| 验证项 | 状态 |
|--------|------|
| `qwen3.5-plus` HTTP 200 | ❌ 未验证 |
| `qwen3-coder-plus` HTTP 200 | ❌ 未验证 |
| `kimi-k2.5` HTTP 200 | ❌ 未验证 |
| `glm-5` HTTP 200 | ❌ 未验证 |
| `MiniMax-M2.5` HTTP 200 | ❌ 未验证 |
| 主路由故障 fallback 生效 | ❌ 未验证 |
| 401 错误不会无限重试 | ❌ 未验证 |
| 关键日志进入 EventBus/ArtifactStore | ❌ 未验证 |

---

## 三、初期目标 vs 现状差距

### 3.1 目标回顾（来自需求文档）

根据 `docs_model_routing_for_antigravity_2026-02-28.md` 定义的交付要求：

| 目标 | 期望 | 现状 | 差距 |
|------|------|------|------|
| 静态路由 + fallback 可运行版 | ✅ 完整实现 | ❌ 尚未开始 | 100% |
| provider 读取环境变量 | ✅ 不允许明文 key 入仓 | ⚠️ 模块不存在 | N/A |
| 支持 OpenAI 兼容 | ✅ Coding Plan | ❌ 未实现 | 100% |
| 支持 Anthropic 兼容 | ✅ MiniMax | ❌ 未实现 | 100% |
| CLI 通道插件 | ✅ 可选插件 | ❌ 未实现 | 100% |
| ChatgptREST 通道 | ✅ 支持 pro_extended/deep_research | ❌ 未实现 | 100% |
| 输出一份 `route_decision_log.jsonl` | ✅ 供后续优化 | ❌ 未实现 | 100% |

### 3.2 AIOS 需求回顾（来自 code review/03_AIOS_REQUIREMENTS_BACKGROUND.md）

| 场景 | 目标 | 现状 |
|------|------|------|
| A2 写报告 | 三套稿体系 + prompt 模板 → 编排器串接 | 仅 kernel 基础就绪，workflows 未实现 |
| A3 做调研 | 自动生成调研报告 | workflow 未实现 |
| A4 项目规划 | 自动生成规划报告 | advisor + workflows 未实现 |
| D1+D4 多模型 | 辩论与交叉验证机制 | model_router 未实现 |

---

## 四、待完成工作清单

### 4.1 第一阶段：核心路由层（优先级 P0）

- [ ] 实现 `openmind/integrations/model_router.py`
  - [ ] RouteRequest / RouteDecision 数据模型
  - [ ] ModelRouter 主类（route + invoke 方法）
- [ ] 实现 `openmind/integrations/providers/`
  - [ ] `openai_compatible.py` — Coding Plan 通道
  - [ ] `anthropic_compatible.py` — MiniMax 通道
  - [ ] `cli_bridge.py` — CLI 桥接（codex/gemini/claude）
  - [ ] `chatgptrest_bridge.py` — Deep Research 通道

### 4.2 第二阶段：工作流引擎（优先级 P1）

- [ ] 实现 `advisor/` 模块
  - [ ] Advisor Graph 路由逻辑
  - [ ] 意图识别（intent classification）
- [ ] 实现 `workflows/`
  - [ ] Quick Ask 工作流
  - [ ] Deep Research 工作流
  - [ ] Funnel Graph 工作流

### 4.3 第三阶段：知识层（优先级 P2）

- [ ] 实现 `kb/` 模块
  - [ ] Qdrant 向量检索
  - [ ] SQLite FTS5 全文检索
  - [ ] jieba 中文分词
- [ ] 实现 `evomap/` 模块
  - [ ] 演进映射逻辑

### 4.4 第四阶段：集成与验证（优先级 P3）

- [ ] 实现 `contracts/` 模块
  - [ ] 接口契约定义
- [ ] 连通性测试
  - [ ] 5 个模型 HTTP 200 验证
  - [ ] fallback 机制验证
  - [ ] 401 错误处理验证
  - [ ] EventBus 日志集成验证

---

## 五、风险评估

| 风险项 | 级别 | 缓解措施 |
|--------|------|----------|
| model_router 复杂度高 | 🔴 高 | 分步实现，先做静态路由 |
| 多模型通道兼容性 | 🔴 高 | 优先验证 5 个核心模型连通性 |
| 工作流编排逻辑复杂 | 🟡 中 | 复用 LangGraph 官方示例 |
| 环境变量配置管理 | 🟡 中 | 使用 pydantic-settings 统一管理 |

---

## 六、结论

### 6.1 整体进度评估

- **代码实现**：约 15%（仅 kernel 三个模块）
- **模块覆盖**：约 30%（7 个模块中 3 个有实质代码）
- **验证完成度**：0%

### 6.2 上线前置条件

要达到生产可上线状态，需要完成：

1. **必须完成（P0）**：model_router + providers 核心路由层
2. **必须完成（P一个 workflow（1）**：至少建议 Deep Research）
3. **建议完成（P2）**：kb 模块（检索是核心能力）
4. **验证必须通过**：5 个模型连通性测试

### 6.3 建议路径

```
当前状态 → model_router 基础版 → Deep Research workflow → kb 集成 → 验证 → 上线
```

---

**报告生成时间**：2026-03-01
**审核人**：CC 审核
