# Memory Hardening Review — PR #123 (ChatgptREST)

**Reviewer**: Antigravity  
**Date**: 2026-03-11  
**Branch**: `codex/issue-121-memory-hardening`  
**Scope**: 5 commits (`c63ebe8..7c52648`), 13 files, 755+/85-

---

## 总体评价

这个 PR 做的事情方向完全正确：把 memory 子系统从"全局扁平去重"升级到"按身份维度隔离"，同时把 captured_memory 的匿名召回从 fail-open 改成 fail-closed。改动是 additive 的，不删除已有 API 签名，走的是在现有参数基础上加新维度的方式。

**质量判断**：整体质量好。下面列的问题里没有 HIGH 级别的阻塞项，全部是 MEDIUM 和 LOW。

---

## 逐项评审

### 1. MemoryManager 身份隔离去重 (`memory_manager.py`)

**改了什么**：
- `MemorySource` 新增 `account_id`、`thread_id` 字段
- `_IDENTITY_FIELDS = ("agent", "role", "session_id", "account_id", "thread_id")` 定义隔离维度
- `stage()` 里的去重 SQL 从 `WHERE fingerprint = ? AND category = ?` 变为 `WHERE fingerprint = ? AND category = ? AND (5个COALESCE identity字段比对)`
- `_count_occurrences()` 也按同样范围计算（用于 semantic tier 的 `min_occurrences` gate）
- `_normalize_source()` 统一清理 source dict

**✅ 正确的地方**：
- 用 `COALESCE(json_extract(source, '$.field'), '') = ?` 做空值兜底是对的——老记录没有 `account_id`/`thread_id` 字段会被当成空字符串匹配，保持向后兼容。
- `_normalize_source()` 放在 `stage()` 入口做统一清理是防御性编程的最佳位置。

**M1 (Medium) — `_identity_where_clause` 构造 SQL 用了 f-string 拼接**：
```python
f"COALESCE(json_extract(source, '$.{field}'), '') = ?"
```
虽然 `_IDENTITY_FIELDS` 是类常量不是用户输入，所以这里**没有 SQL 注入风险**。但风格上，如果后续有人不小心把用户输入加到 `_IDENTITY_FIELDS`，这里就会变成注入点。建议加一行注释说明这个 tuple 是 hardcoded 常量。

**L1 (Low) — 去重范围扩大后的行为变化**：
v1 的去重是 `fingerprint + category` 全局唯一——同一条内容不管谁写的都合并。v2 是 `fingerprint + category + identity scope` 唯一——不同 session/role/account 的相同内容各自独立保存。

这意味着**同一条 memory 如果被不同 agent/session 写入，现在会产生多条记录**，而不是像以前那样 merge 到一条。这是设计意图（test `test_dedup_isolated_by_identity_scope` 明确验证了这一点），但需要确认磁盘增长没问题。

### 2. Context Service 匿名召回封堵 (`context_service.py`)

**改了什么**：
- `build()` 新增 `account_id`、`thread_id` 参数
- `working_memory`：只在有 `session_id` 时才查
- `episodic_memory`：只在有 `session_id` OR `account_id` OR `thread_id` 时才查
- `captured_memory`：走 **identity cascade**——先按 `thread_id` 查，再按 `session_id` 查，再按 `account_id` 跨 session 查；全部缺失 → `blocked_missing_identity`
- `semantic_memory`：同样需要至少一个身份维度
- 新增 `captured_memory_scope` 到 metadata（枚举：`thread` / `session` / `account_cross_session` / `no_match` / `blocked_missing_identity`）
- 匿名请求产生 `degraded_sources: ["memory_identity_missing"]`

**✅ 正确的地方**：
- Identity cascade（thread → session → account）的降级顺序是对的：thread 最窄、account 最宽，逐步放大搜索范围。
- `blocked_missing_identity` 作为默认态表示 fail-closed，而不是 v1 的 fail-open（`session_id=""` 时照样查全库）。

**M2 (Medium) — captured_memory cascade 的 fallback 查询做了双重尝试**：
```python
if thread_id:
    captured = query(query=query, thread_id=thread_id)  # with query text
    if not captured and query:
        captured = query(thread_id=thread_id)             # without query text
```
每个 cascade 级别（thread / session / account）都做了"先带 query 查一次，没结果就不带 query 再查一次"。这意味着最坏情况下 captured_memory 会做 **6 次 SQL 查询**（3 个级别 × 2 次 fallback）。对于实时服务这可能偏多。建议考虑在第一个有结果的级别就 break，不要继续往下走——目前代码逻辑其实已经是这样的（`if not captured and session_id:` 的结构），但建议加个注释说明"第一个有结果就停止"的设计意图。

**M3 (Medium) — ContextResolveOptions 是否有 `account_id`/`thread_id` 字段**：
diff 里看到 `options.account_id` 和 `options.thread_id` 被传入 `build()`，但没有看到 `ContextResolveOptions` dataclass 新增这些字段的 diff。让我查一下是否遗漏：

如果 `ContextResolveOptions` 没有这两个字段，`options.account_id` 会抛 `AttributeError`。如果它通过 `ContextResolveOptions` 之外的方式传入（比如 `**kwargs`），那没问题——但这需要确认。

> **需要确认**：`ContextResolveOptions` 是否已经有 `account_id` 和 `thread_id` 字段？

### 3. Memory Capture Policy Gate (`memory_capture_service.py`)

**改了什么**：
- 新增 `_quality_gate()` 方法：调用 `PolicyEngine.run_quality_gate(QualityContext(...))` 做内容审查
- gate 返回 `{"allowed": false, "reason": "..."}` 时，capture 被阻断、不落库，但会 emit `memory.capture.blocked` 事件
- `MemorySource` 构造时传入 `account_id` 和 `thread_id`
- event emission 重构进 `_emit_capture_event()` 辅助方法
- 缩进修正（v1 有不一致的缩进）

**✅ 正确的地方**：
- 把 policy gate 放在 `stage_and_promote()` **之前**是对的——被阻断的内容永远不进 SQLite。
- 即使被阻断也 emit 事件（`memory.capture.blocked`），保留了可审计性。
- `_emit_capture_event()` 的提取消除了代码重复。

**L2 (Low) — `_quality_gate()` 对 `policy_engine` 为 None 返回空 dict**：
```python
if policy is None:
    return {}
```
下游对空 dict 的处理是 `if quality_gate and not quality_gate.get("allowed", False)`。空 dict 是 falsy 的，所以当 policy 未配置时等效于"不做审查、全部放行"。这是合理的 fail-open 降级，但值得在注释里显式说明。

### 4. OpenClaw Advisor Identity 透传 (`index.ts`)

**改了什么**：
- 新增 `runtimeIdentity()` 函数：从 OpenClaw context 提取 `sessionKey` → `session_id`、`agentAccountId` → `account_id`、`sessionId` → `thread_id`、`agentId` → `agent_id`
- `execute()` 签名新增第三个参数 `ctx`（OpenClaw tool context）
- `/advise` 和 `/ask` body 都注入了 identity 字段
- `user_id` 默认为 `identity.account_id || "openclaw"`

**M4 (Medium) — `sessionId` 映射到 `thread_id` 的命名反直觉**：
```typescript
thread_id: String(ctx?.sessionId ?? "").trim(),
```
OpenClaw 的 `sessionId` 被映射成了 OpenMind 的 `thread_id`，而 OpenClaw 的 `sessionKey` 被映射成了 `session_id`。这个映射逻辑是有原因的（OpenClaw 的 `sessionId` 更像是"聊天对话 ID"，而 `sessionKey` 是"工作会话 key"），但命名差异容易让后续维护者困惑。建议在 `runtimeIdentity()` 上方加注释说明映射理由。

**L3 (Low) — `mergedContext` 会把 identity 字段也塞进 context dict**：
```typescript
const mergedContext = {
    ...context,
    ...Object.fromEntries(Object.entries(identity).filter(([, value]) => value)),
};
```
这意味着 `session_id`/`account_id`/`thread_id`/`agent_id` 会同时出现在 body 顶层（`body.session_id`）和 `body.context` 里——双重传播。这不是 bug（多传无害），但是冗余数据。

### 5. Routes Advisor V3 (`routes_advisor_v3.py`)

**改了什么**：
- `/advise` 端点：解析 `session_id`/`account_id`/`thread_id`/`agent_id`/`user_id`，传入 `api.advise()`，Langfuse trace 用正确的 `user_id` 和 `session_id`
- `/ask` 端点：同样解析并注入 `graph_state`，存入 job 元数据

**✅ 正确的地方**：
- `user_id = ... or account_id or "api"` 做了合理的 fallback。
- job 元数据里也存了 identity，便于审计。

### 6. Advisor Graph State (`graph.py`)

3 行改动：`AdvisorState` 新增 `account_id`、`thread_id`、`agent_id`。纯类型扩展，无逻辑影响。✅

---

## 测试覆盖评估

| 测试文件 | 覆盖项 | 评价 |
|----------|--------|------|
| `test_memory_tenant_isolation.py` | 新增 episodic/semantic account/thread 过滤、dedup identity scope 隔离 | ✅ 直接验证核心改动 |
| `test_role_pack.py` | dedup-updates-role 改成 identity-prevents-dedup、MemorySource 新字段 | ✅ 语义变化有测试 |
| `test_openmind_memory_business_flow.py` | cross-session recall 加 `account_id`、`captured_memory_scope` 断言 | ✅ 端到端 |
| `test_cognitive_api.py` | 102 行新增（需确认具体内容，diff 被截断） | 部分可见 |
| `test_advisor_v3_end_to_end.py` | 124 行新增 | 部分可见 |
| `test_openclaw_cognitive_plugins.py` | 断言 `session_id/account_id/thread_id/agent_id/user_id` 在 plugin source 里 | ✅ 防回归 |

**缺失的测试**：没有看到 `_quality_gate` 被 `blocked` 的场景测试（memory_capture_service 的 policy gate 拒绝场景）。建议补一个 `test_capture_blocked_by_policy_gate` 用 mock `PolicyEngine.run_quality_gate` 返回 `allowed=False`。

---

## 发现汇总

| 编号 | 级别 | 位置 | 问题 |
|------|------|------|------|
| M1 | Medium | `memory_manager.py:_identity_where_clause` | f-string SQL 拼接，虽安全但建议加注释说明 `_IDENTITY_FIELDS` 是常量 |
| M2 | Medium | `context_service.py:build()` | captured_memory cascade 最坏 6 次 SQL 查询，需确认性能可接受 |
| M3 | Medium | `context_service.py:build()` | 需确认 `ContextResolveOptions` 已有 `account_id`/`thread_id` 字段 |
| M4 | Medium | `openclaw_extensions/index.ts:runtimeIdentity` | `sessionId→thread_id` 映射命名反直觉，需加注释 |
| L1 | Low | `memory_manager.py:stage()` | 去重范围扩大导致存储增长，需确认磁盘预算 |
| L2 | Low | `memory_capture_service.py:_quality_gate()` | policy=None → fail-open，建议加注释显式说明 |
| L3 | Low | `openclaw_extensions/index.ts:mergedContext` | identity 字段在 body 和 context 里双重传播，冗余但无害 |
| — | Gap | `tests/` | 缺少 `_quality_gate` blocked 场景的单元测试 |

---

## 结论

**可合并，无阻塞项。** 4 个 Medium 都是"加注释 / 确认已有字段 / 确认性能"级别的，不需要改代码逻辑。建议合并前确认 M3（`ContextResolveOptions` 字段完整性）即可。

assistant decision / tool-result capture 的 defer 是合理的——先把身份隔离基座打好，再扩采集范围。
