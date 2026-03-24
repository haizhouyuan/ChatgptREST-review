# ChatgptREST (OpenMind v3) 全量代码评审报告

**审核：CC 深度评审**
**日期：2026-03-01**
**版本**：c1d7ebd

---

## 一、评审范围

| 模块 | 文件 | 行数 | 状态 |
|------|------|------|------|
| Advisor Graph | `advisor/graph.py` | 943 | ✅ 已读 |
| Report Graph | `advisor/report_graph.py` | 360 | ✅ 已读 |
| Funnel Graph | `advisor/funnel_graph.py` | 375 | ✅ 已读 |
| LLM Connector | `kernel/llm_connector.py` | 410 | ✅ 已读 |
| EventBus | `kernel/event_bus.py` | 246 | ✅ 已读 |
| API Routes | `api/routes_advisor_v3.py` | 509 | ✅ 已读 |
| Feishu Handler | `advisor/feishu_handler.py` | ~300 | ✅ 已读 |
| KB 模块 | `kb/*.py` | ~1000 | ⚠️ 概览 |

---

## 二、严重问题（阻断上线）

### 2.1 测试断裂

| 问题 | 位置 | 说明 |
|------|------|------|
| **T1** | `tests/test_report_graph.py` | ImportError：测试 import `draft` 节点，但 report_graph 已重构为 `internal_draft`/`external_draft`，导致测试无法运行 |
| **T2** | 缺少 E2E 集成测试 | 只有单元测试，缺少完整的 advisor_graph E2E 测试 |

**影响**：CI 不可用，回归测试失效

---

### 2.2 依赖声明不完整

| 问题 | 位置 | 说明 |
|------|------|------|
| **D1** | `pyproject.toml` | 未声明 `langgraph`、`langchain-core`、`numpy` 等 v3 核心依赖 |
| **D2** | `api/app.py` | 存在 `"langgraph not installed"` 的 fallback 分支，但依赖缺失 |

**影响**：干净环境 `pip install` 后 v3 功能静默失效

---

### 2.3 配置管理风险

| 问题 | 位置 | 说明 |
|------|------|------|
| **C1** | 多个 `os.environ.get()` | 配置分散在代码中，无统一配置管理 |
| **C2** | 凭证硬编码风险 | `QWEN_API_KEY`、`MINIMAX_API_KEY` 等需要明确写入 `credentials.env` 模板 |
| **C3** | 路径默认值为 `~/.openmind/` | 多处硬编码，应统一到配置 |

---

## 三、高优先级问题

### 3.1 KB 向量检索未完成

| 问题 | 位置 | 说明 |
|------|------|------|
| **K1** | `kb/hub.py` | `vector_store` 存在但未真正接入 search 流程 |
| **K2** | `kb/retrieval.py` | 只有 FTS5，无 RRF 融合算法 |
| **K3** | `graph.py:kb_probe` | 只返回 FTS5 结果，向量召回缺失 |

**影响**：长问句/同义改写检索不稳，知识库会退化为关键词检索

---

### 3.2 报告发布链路不完整

| 问题 | 位置 | 说明 |
|------|------|------|
| **P1** | `report_graph.py:redact_gate` | 只做"检测+阻断"，未实现"脱敏执行+回写" |
| **P2** | `graph.py:_kb_writeback_and_record` | 有 KB 写回，但发布到飞书/钉钉未形成显式节点 |
| **P3** | `policy_engine` | `audience` 和 `security_label` 口径存在混用风险 |

**影响**：报告无法自动发布，需要人工复制粘贴

---

### 3.3 Funnel Gate B 缺少人在环

| 问题 | 位置 | 说明 |
|------|------|------|
| **F1** | `funnel_graph.py:rubric_b` | 注释写 "interrupt_before in prod"，但实现仍是同步判定 |
| **F2** | 缺少 resume API | 没有提供 `POST /v2/advisor/resume/{trace_id}` 接口 |

**影响**：Gate B 无法真正做到人工确认后才能继续

---

### 3.4 飞书集成配置缺失

| 问题 | 位置 | 说明 |
|------|------|------|
| **FH1** | `FEISHU_WEBHOOK_SECRET` | 需要在飞书开发者后台配置回调 URL 并获取 |
| **FH2** | 凭证未迁移 | OpenClaw 有 2 个飞书 bot（main/research），ChatgptREST 需配置 |

---

## 四、中等问题

### 4.1 事件系统双写

| 问题 | 位置 | 说明 |
|------|------|------|
| **E1** | EventBus vs EvoMapObserver | graph 同时写两套事件系统，但 observer 未真正 subscribe EventBus |
| **E2** | 统计口径漂移 | route.selected 在 graph 记录一次，在 simple_routes 又记录一次 |

---

### 4.2 错误处理不一致

| 问题 | 位置 | 说明 |
|------|------|------|
| **ERR1** | 多处 `except Exception as e: logger.warning` | 错误被吞掉，无法追溯根因 |
| **ERR2** | `llm_connector.py:ask()` | 失败后可能抛出 RuntimeError，但调用方未统一处理 |

---

### 4.3 安全风险

| 问题 | 位置 | 说明 |
|------|------|------|
| **S1** | API 无 IP 白名单 | 只有 API Key + 速率限制 |
| **S2** | Webhook 无 IP 限制 | 飞书回调未验证来源 IP |
| **S3** | 敏感日志 | `graph.py` 日志可能打印用户消息内容 |

---

### 4.4 性能隐患

| 问题 | 位置 | 说明 |
|------|------|------|
| **PERF1** | SqliteSaver checkpoint | 每个请求都写 checkpoint，可能成为瓶颈 |
| **PERF2** | 内存泄漏 | `_ServiceRegistry` 是单例，服务重启才释放 |
| **PERF3** | KB 写入阻塞 | `index_document` 同步执行，大文档会阻塞 |

---

## 五、低优先级问题

### 5.1 代码质量

| 问题 | 说明 |
|------|------|
| Q1 | 大量 `TODO`、`FIXME` 注释未清理 |
| Q2 | `_noop_llm` mock 函数散落多处，应统一到 `conftest.py` |
| Q3 | 类型注解不完整，很多 `Any` |

### 5.2 文档缺失

| 问题 | 说明 |
|------|------|
| D1 | 缺少 API 接口文档（OpenAPI/Swagger） |
| D2 | 缺少部署手册 |
| D3 | 缺少运维手册（备份、监控、报警） |

---

## 六、功能达成度

### 6.1 4 场景 E2E

| 场景 | 路由 | 预期结果 | 实际结果 |
|------|------|----------|----------|
| S1 | QUICK_QUESTION | 文本答案 | ✅ answer_len=981 |
| S2 | DO_RESEARCH | 研究报告 | ✅ review_pass=true |
| S3 | WRITE_REPORT | 完整报告 | ⚠️ review_pass=false |
| S4 | BUILD_FEATURE | ProjectCard | ⚠️ answer_len=0 |

### 6.2 6 步报告管线

| 步骤 | 目标 | 状态 |
|------|------|------|
| 1. 目的识别 | 匹配目的矩阵 | ⚠️ LLM 识别，未对接规则 |
| 2. 证据装载 | kb_pack | ✅ |
| 3. 底稿生成 | 内部底稿 | ✅ |
| 4. 外发稿生成 | 外发沟通稿 | ✅ |
| 5. Pro 复审 | 审核闭环 | ⚠️ S3 needs_revision |
| 6. 脱敏+发布 | 自动发布 | ❌ 缺执行 |

---

## 七、上线前必须修复清单

### P0（必须修复）

```
[x] T1: 修复 test_report_graph.py ImportError
[x] D1: 补齐 pyproject.toml 依赖声明
[x] C2: 提供 credentials.env 模板
[ ] FH1: 配置飞书 Webhook（从 OpenClaw 迁移）
[ ] C3: 统一路径配置管理
```

### P1（强烈建议）

```
[ ] K1-K3: 完成 KB 向量检索 + RRF 融合
[ ] P1-P3: 完成报告发布链路
[ ] F1-F2: Funnel Gate B 人在环 + resume API
[ ] E1-E2: 统一事件系统口径
[ ] ERR1: 统一错误处理
```

### P2（上线后迭代）

```
[ ] S1-S3: 安全加固
[ ] PERF1-PERF3: 性能优化
[ ] Q1-Q3: 代码清理
[ ] D1-D3: 文档补齐
```

---

## 八、总结

| 维度 | 评估 |
|------|------|
| **代码完成度** | ~70% |
| **测试覆盖** | ~40%（测试断裂） |
| **上线就绪度** | ~50% |
| **核心风险** | 测试断裂、依赖缺失、KB 向量未完成、发布链路缺失 |

**建议**：先修复 P0 清单（测试+依赖+配置），再完成 P1 清单中的 KB 向量和发布链路，然后可以灰度上线。

---

**报告生成时间**：2026-03-01
**审核人**：CC 深度评审
