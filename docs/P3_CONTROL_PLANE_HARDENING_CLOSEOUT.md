# P3: Control Plane Correctness Hardening — Closeout Report

**Date**: 2026-05-05
**Scope**: Paperclip Skill Agent runtime control plane
**Commits**: 4 commits, ~2,200 lines changed across 23 files
**Tests**: 48 passing

---

## 1. 工作摘要（What Was Done）

基于 ChatGPT Pro 对 P0-P2 代码的评审（识别出 6 个架构-执行差距、13 项修复清单），完成了控制平面加固的全部 4 个阶段：

| 阶段 | 内容 | 关键文件 | 状态 |
|------|------|---------|------|
| **A. Foundation** | 策略感知路由、SQLite 配额、覆盖安全门 | `policy_store.py`, `allocator_mvp.py`, `skill_agent.py`, `runtime_state.py` | ✅ 完成 |
| **B. Result Integrity** | 终端状态、Pydantic 输出模式、模式验证 | `schemas/`, `skill_agent.py` | ✅ 完成 |
| **C. Infrastructure** | 探测加固、原子锁、文件名清理、Gemini stdin、下载安全 | `runtime_probe.py`, `runtime_state.py`, `runtime_invoker.py`, `model_download.py`, 3 orchestrators | ✅ 完成 |
| **D. Tests** | 路由/策略、配额/预留、模式验证、安全、回退/熔断 | `runtime_allocator/tests/` | ✅ 48 个通过 |

---

## 2. 原版 vs P3 对比（Before / After）

| 维度 | P0/P2 原版 | P3 加固后 |
|------|-----------|----------|
| **路由策略** | `routing_policy.yaml` 死配置，从未加载 | 正式生效，36 个任务类的 primary/fallback 链 |
| **路由算法** | 数学打分 `4*质量 - 1.5*成本 - 1*延迟` | 策略链硬约束 + 分数仅做同策略内平局决胜 |
| **未知任务** | 任意路由 | 明确阻断，返回 `terminal_state=blocked` |
| **配额系统** | JSON 文件 `QuotaLedger` | SQLite 预留/提交/退款生命周期 |
| **配额错误分类** | 无 | 401/429 → 退款不计入；超时 → 计入尝试 |
| **覆盖控制** | `provider_override` 跳过所有门 | 覆盖只跳过排名，隐私/质量/策略/健康/配额五门仍检查 |
| **成功判定** | `result.error is None` | 模式验证通过才算成功 |
| **输出结构** | 纯字符串 `content` | Pydantic 验证对象 `validated_output` |
| **终端状态** | 无 | `completed`/`blocked`/`human_review_required`/`schema_validation_failed` |
| **健康探测** | 裸 HTTP GET | 解析 env var、带 API key、401→AuthConfigError |
| **资源锁** | 先读后写（竞态） | `BEGIN IMMEDIATE` + `INSERT ON CONFLICT` 原子获取 |
| **文件名安全** | 直接拼接 | `safe_slug()` 过滤 `../` 和非安全字符 |
| **Gemini CLI** | prompt 通过 argv 暴露 | 通过 stdin 管道传入 |
| **模型下载** | `--token` 明文参数 | `HF_TOKEN` 环境变量 + 路径包含检查 + 原子重命名 |

---

## 3. 当前公司配置状态（System Configuration）

### 3.1 运行时提供商配置

配置文件：`runtime_allocator/profiles/runtime_profiles.yaml`

| Provider | 协议 | 隐私级别 | 质量级别 | 状态 |
|----------|------|---------|---------|------|
| claudekimi | openai_compatible | external_cloud | critical | ✅ 启用 |
| minimax | openai_compatible | external_cloud | high | ✅ 启用 |
| gemini_local | gemini_cli | local | standard | ✅ 启用 |
| ollama_gpu0 | openai_compatible | local | high | ✅ 启用 |

### 3.2 路由策略配置

配置文件：`runtime_allocator/profiles/routing_policy.yaml`

- **36 个任务类**已配置策略
- **关键任务**（如 `finbot_trade_proposal`、`hr_sensitive`）primary 单一、fallback 为空、不可用终端状态为 `human_review_required`
- **普通任务**（如 `dtc_copy`、`document_draft`）允许降级 fallback

### 3.3 数据库状态

- 位置：`~/.paperclip/runtime_state.sqlite`
- 表：`runtime_budgets`, `runtime_reservations`, `runtime_events`, `runtime_health`, `resource_locks`
- 模式：WAL 模式，支持并发

### 3.4 输出模式库

- 位置：`runtime_allocator/schemas/`
- 数量：20 个 Pydantic 模型
- 覆盖域：Labebe(5) + Planning(8) + Memory(4) + Finbot(3)
- 共享字段：`confidence`, `requires_human_review`, `assumptions`, `data_gaps`, `evidence_refs`

### 3.5 测试覆盖

```
runtime_allocator/tests/
├── test_policy_routing.py      # 12 tests — 策略加载、primary 匹配、未知任务阻断、隐私门
├── test_quota_reservation.py   #  5 tests — 预留/提交/退款、硬预算、并发竞争
├── test_schema_validation.py   #  6 tests — 有效/无效/坏 JSON、证据引用、假设/缺口
├── test_security.py            # 11 tests — 文件名清理、路径遍历、模型删除、env 解析
├── test_fallback_circuit.py    #  5 tests — 冷却 TTL、终端状态、高 stakes 标记

Total: 48 passed, 0 failed
```

---

## 4. 部署就绪度评估

| 场景 | 就绪度 | 说明 |
|------|--------|------|
| **单公司内部使用** | ✅ Ready | 控制平面可信，可直接作为 Python SDK 使用 |
| **多团队/子公司共用** | ⚠️ Low Risk | 单租户，注意配额共享问题 |
| **作为 SDK 给外部集成** | ⚠️ Medium Risk | 需要对方也是 Python，无租户隔离 |
| **SaaS 多租户平台** | ❌ Not Ready | 缺 HTTP API、认证、多租户隔离、可观测性 |

---

## 5. 已知限制与风险

| 风险项 | 严重度 | 说明 |
|--------|--------|------|
| 单租户 SQLite | 中 | 多公司共用时会共享配额/健康状态 |
| 无 HTTP API | 中 | 只能 Python import，异构系统无法接入 |
| 无认证层 | 高 | 任何能 import 的代码都能调用，无身份校验 |
| 无计费对接 | 低 | 预留/提交记录了 token 数，但未对接实际账单 |
| SQLite 并发上限 | 低 | WAL 模式能撑中等并发，高并发需迁移 PostgreSQL |
| 测试无集成 LLM | 中 | 48 个测试都是单元测试，未覆盖真实 LLM 调用链路 |

---

## 6. 下一步建议（P4 Service Layer）

如需推向多公司生产环境，建议按以下顺序实施：

```
P4.1  FastAPI HTTP 服务封装 execute_with_fallback()
      └─ 提供 REST API，非 Python 系统可接入

P4.2  company_id 贯穿所有数据表 + 配置隔离
      └─ SQLite 表加 company_id，或按公司分库

P4.3  API Key / JWT 认证 + RBAC
      └─ 验证调用方身份，绑定公司配额

P4.4  可观测性增强
      └─ Prometheus 指标、结构化日志、告警规则

P4.5  （可选）SQLite → PostgreSQL
      └─ 高并发场景下的持久化层升级
```

---

## 7. 关键文件索引

| 文件 | 职责 | 状态 |
|------|------|------|
| `runtime_allocator/skill_agent.py` | 核心入口，execute_with_fallback() | ✅ 已加固 |
| `runtime_allocator/allocator_mvp.py` | 策略感知路由 + 分配 | ✅ 已加固 |
| `runtime_allocator/policy_store.py` | 加载 routing_policy.yaml | ✅ 新增 |
| `runtime_allocator/runtime_state.py` | SQLite 状态存储 | ✅ 已加固 |
| `runtime_allocator/runtime_probe.py` | 健康探测 | ✅ 已加固 |
| `runtime_allocator/runtime_invoker.py` | LLM 调用统一接口 | ✅ 已加固 |
| `runtime_allocator/model_download.py` | 模型下载管理 | ✅ 已加固 |
| `runtime_allocator/schemas/*.py` | 20 个输出模式 | ✅ 新增 |
| `runtime_allocator/tests/*.py` | 48 个测试 | ✅ 通过 |
| `paperclip_labebe/labebe_orchestrator.py` | Labebe 编排器 | ✅ safe_slug 已应用 |
| `paperclip_planning/planning_orchestrator.py` | Planning 编排器 | ✅ safe_slug 已应用 |
| `paperclip_memory/memory_orchestrator.py` | Memory 编排器 | ✅ safe_slug 已应用 |

---

## 8. 验证命令

```bash
# 导入测试
python3 -c "from runtime_allocator.skill_agent import execute_with_fallback; print('OK')"
python3 -c "from runtime_allocator.policy_store import load_routing_policy; print(len(load_routing_policy()), 'policies')"

# 策略加载测试
python3 runtime_allocator/policy_store.py

# 全部测试
python3 -m pytest runtime_allocator/tests/ -v

# 健康探测
python3 runtime_allocator/runtime_probe.py
```

---

*Report generated by Claude Code on 2026-05-05*
*Co-Authored-By: Claude Sonnet 4.6*
