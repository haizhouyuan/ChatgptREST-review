# v4 Writer Coverage 独立验证 + 修正

> 日期：2026-03-10 | 基于 GitNexus impact + 生产数据分布
> 回应 codex 两个批判：writer coverage gap + KB 3-state 模型

---

## 1. Writer Coverage 验证结果

### 1.1 数据来源

- GitNexus: `stage` upstream impact（7 个 d=2 writer）
- Production: memory.db `source.agent` 分布（572 records）

### 1.2 完整 Writer 清单

| Writer (函数) | 文件 | Agent 值 | 记录数 | % | 构造 source 方式 |
|---|---|---|---|---|---|
| `_remember_episodic` | cc_native.py:251 | openclaw | 372 | 65.0% | **hardcode dict** `{"type":"tool_result","agent":"cc_native"}` |
| `route_decision` | graph.py:581 | advisor | 136 | 23.8% | via `stage_and_promote` |
| `execute_report` | graph.py:1017 | report_graph | 36 | 6.3% | via `stage_and_promote` |
| `_capture_one` | memory_capture_service.py:83 | varies | 26 | 4.5% | **MemorySource dataclass** |
| `add_conversation_turn` | memory_manager.py:500 | main | 12 | 2.1% | **MemorySource dataclass** |
| `execute_deep_research` | graph.py:868 | deep_research | 10 | 1.7% | via `stage_and_promote` |
| `_mirror_feedback_memory` | telemetry_service.py:96 | varies | 3 | 0.5% | **MemorySource dataclass** |

**Top categories:**
```
execution_feedback     357  (62%)  ← openclaw _remember_episodic
route_stat             136  (24%)  ← advisor route_decision
report_result           36  (6%)   ← report graph
captured_memory         26  (4.5%) ← memory_capture_service
```

### 1.3 Codex 判断验证

> codex: "如果 source.role 只接到 capture path … devops/research role memory 会长得很慢"

**我的验证结论：codex 说的问题是真的，但他提的解法过重了。**

codex 建议加一个 "1A-writers" 子阶段去审计并逐个改所有 writer。但从 GitNexus 看：

```
ALL 7 writers → stage_and_promote() → stage()
```

`stage()` (memory_manager.py:220) 是**唯一的写漏斗**。在 `stage()` 里自动注入 `source.role` 只需 ~3 行：

```python
def stage(self, record: MemoryRecord) -> str:
    # ... existing code ...
    record.updated_at = now

    # === 新增：自动注入当前 role ===
    from chatgptrest.kernel.role_context import get_current_role_name
    src = record.source if isinstance(record.source, dict) else {}
    if not src.get("role"):
        role_name = get_current_role_name()
        if role_name:
            src["role"] = role_name
            record.source = src
    # === end ===
```

**这覆盖了 100% 的写入路径**，包括那些 hardcode dict 的 writer（如 `_remember_episodic`），因为 `stage()` 会在写入前给它补上 `role`。

**不需要 1A-writers 子阶段。** 不需要逐个改 7 个 writer。只改漏斗点。

---

## 2. KB 3-State 模型

### 2.1 Codex 原话

> "更准确的边界应该是：ContextResolver 决定 → KBRetriever 保留能力 → 只是不默认由 retrieval 自己决定"

### 2.2 我的判断

codex 说得对。v4 说"过滤不在 retrieval 层"这个表述不够精确。更准确的是：

- **决策权**在 router (ContextResolver)
- **执行能力**在 retrieval (KBRetriever/KBHub)
- 两者要分开，但 retrieval 层不能把能力拿掉

### 2.3 三态模型

```
off     → 不做任何 tag 过滤（当前默认，也是 1C 完成前的状态）
hint    → 按 role 的 kb_scope_tags 优先排序，但不排除无匹配文档
enforce → 硬过滤，只返回匹配 tag 的文档
```

默认从 `off` 开始。1C 完成后升到 `hint`。`enforce` 只在明确场景（如安全审计）使用。

由 ContextResolver 决定当前用哪个态，KBRetriever 保留三种能力。

---

## 3. 我的独立判断

### 与 codex 一致

- ✅ Writer coverage 是真问题（4.5% vs 100%）
- ✅ KB 应该有 off/hint/enforce 三态
- ✅ 决策在 router，能力在 retrieval

### 与 codex 不一致

- ❌ **不需要 1A-writers 子阶段**。`stage()` 是唯一漏斗，一处改动覆盖全部。这不是逐个 writer 的审计问题，是选对注入点的问题。
- ❌ **"先把谁在写 memory 盘清楚"这步已经完成**（就是本文档的 §1.2 表）。不需要作为执行阻断。

### 对 v4 的修正

1. **source.role 注入点从 `_capture_one` → `stage()`**
   - 从覆盖 4.5% → 覆盖 100%
   - 代码量不变（~3 行）
   
2. **v4 §1.2 KB 过滤描述改为三态模型**
   - off → hint → enforce
   - 决策在 ContextResolver
   - 能力在 KBRetriever

3. **执行顺序保持原 1A/1B/1C**
   - 不需要 1A-core + 1A-writers 拆分
   - 改在 `stage()` 注入就够了

---

## 4. 最终执行顺序（收敛版）

```
1A (立刻做, ~120L代码):
  ├── MemorySource + role 字段
  ├── stage() 自动注入 source.role ← 覆盖所有 writer
  ├── get_episodic/get_semantic + role_id 参数
  ├── RoleSpec + 2 字段
  ├── role_context.py (contextvars)
  ├── role_loader.py (YAML loader)
  ├── config/agent_roles.yaml
  └── ContextService.build() 接入 role_id

1B (并行做):
  ├── identity gap 审计
  └── 高频缺失路径修复

1C (KB 治理，完成后再开 hint):
  ├── 受控词表
  ├── backfill 脚本（可重复）
  ├── 903 文档补打 tag
  ├── write-path 校验
  └── off → hint 切换（ContextResolver 决定）
```
