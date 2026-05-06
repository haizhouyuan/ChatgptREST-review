# ChatgptREST 平台边界与 MCP 交付合同深度复核 — Claude Code 独立意见 v1

日期：2026-04-07
审核对象：Codex 全库通览分析（平台边界漂移 + MCP 交付合同缺口 + 7 阶段收口方案）
审核方法：逐条对照源代码验证，批判性分析

---

## 总体评价

Codex 这次的分析是迄今为止最深入的一次。核心判断——ChatgptREST 从 web 自动化工具演变成了过度复杂的 advisor agent 平台——有代码事实支撑。但 Codex 的修复方案有 **3 个事实性错误** 和 **2 个方向性偏差**，如果不纠正会导致重复建设。

---

## 第一部分：Codex 诊断验证

### 1.1 "completion_contract 没有投射到 public agent MCP surface" — 验证为真

代码事实：

**Web 自动化 MCP（server.py:3650-3654）已经投射了 completion_contract**：
```python
out["answer_state"] = get_completion_answer_state(out)
out["authoritative_job_id"] = get_authoritative_job_id(out)
out["authoritative_answer_path"] = get_authoritative_answer_path(out)
out["answer_provenance"] = get_answer_provenance(out)
final_answer_ready = status == "completed" and is_research_final(out)
```

**Public agent MCP（agent_mcp.py）完全没有导入 completion_contract**：
- 没有 `answer_state`
- 没有 `authoritative_answer_path`
- 没有 `canonical_answer`
- 只有 `last_answer`（原始字符串）

**routes_agent_v3.py（6388 行）也没有导入 completion_contract**：
- `_controller_snapshot()` 不包含 completion_contract 字段
- `_job_snapshot()` 不包含 completion_contract 字段
- `_build_delivery_surface()` 只有基础字段（format, mode, answer_chars, accepted, answer_ready, terminal）

**controller/engine.py 也没有导入 completion_contract**：
- `_reconcile_job_work_item()` 用简单的 `job.status.value == "completed"` 判断完成
- 没有 answer_state、finality_reason 等质量元数据

结论：**Codex 的诊断完全正确。** completion_contract 是一个成熟的低层系统（374 行，覆盖 answer_state/finality_reason/authoritative_answer_path/canonical_answer/export_available），但只被 web 自动化 MCP 使用，没有被 public agent MCP 使用。

### 1.2 "ChatgptREST 从 web 自动化演变成了过度复杂的平台" — 验证为真

代码事实：

**app.py 加载 14+ 路由器**：
- jobs_v1, advisor_v1, consult_v1, issues_v1, metrics_v1, ops_v1
- evomap_v1, cognitive_v2, dashboard_v2, cc_sessiond_v1
- advisor_v3, agent_v3, task_runtime_v1

**两套 MCP server 并存**：
- `server.py`（153,215 行，50+ 工具）— web 自动化 MCP
- `agent_mcp.py`（55,723 行，6 工具）— public agent MCP

**wrapper 脚本（chatgptrest_call.py）1616 行**，包含：
- 双模式（agent + legacy）
- 传输层恢复重试
- Cloudflare 验证冷却循环
- CDP lane 文件锁
- Pro 请求最小间隔强制
- 无意义 prompt 拦截
- 对话导出重试

这 1616 行 wrapper 的存在本身就是复杂度问题的证据。一个"提交问题、等答案"的操作不应该需要这么多胶水代码。

结论：**Codex 的判断正确。** 系统确实从 web 自动化工具演变成了一个承载过多职责的平台。

### 1.3 "对 coding agent 来说，短任务不需要 advisor，只需要暴露 web 能力" — 部分正确

这个判断的方向是对的，但需要区分两个不同的问题：

**问题 A：coding agent 需要什么？**
- 提交问题给 ChatGPT/Gemini/Qwen
- 等待答案
- 获取答案文本
- 取消任务
- 获取对话 URL（用于后续跟进）

这 5 个操作就够了。advisor pipeline 的 task_intake、scenario_pack、control_plane、lifecycle、effects、memory_capture 对 coding agent 来说都是开销。

**问题 B：web 自动化 MCP 是否就是答案？**
不完全是。web 自动化 MCP（server.py）有 50+ 工具，包括 ops、issues、repair、SRE 等大量运维工具。它不是"简单的 web 能力暴露"，它是另一个复杂系统。

---

## 第二部分：Codex 方案中的事实性错误

### 错误 1：web 自动化 MCP 已经有 completion_contract 投射

Codex 的方案第 2 步说"恢复 coding agent web-first MCP surface"，暗示需要新建一个简单的 web MCP。

**事实是：web 自动化 MCP（server.py）已经有完整的 completion_contract 投射。** `chatgptrest_result()` 函数（line 3618）已经：
- 返回 `answer_state`（final/provisional/partial）
- 返回 `authoritative_job_id`
- 返回 `authoritative_answer_path`
- 返回 `answer_provenance`
- 用 `is_research_final()` 判断 Deep Research 是否真正完成
- 有 `action_hint` 系统（fetch_answer, fetch_authoritative_answer, await_research_finality, poll_later）

所以不需要"恢复"什么，web 自动化 MCP 的答案交付能力已经比 public agent MCP 成熟得多。

### 错误 2：不是"两套系统"的问题，是"投射缺失"的问题

Codex 把问题描述为"advisor agent 系统太复杂，应该回到 web 自动化"。但实际的代码结构是：

```
completion_contract.py（底层，成熟）
    ↓ 被使用
routes_jobs.py（job 层，使用 completion_contract）
    ↓ 被使用
server.py（web 自动化 MCP，投射 completion_contract）
    ✅ coding agent 可以直接用

completion_contract.py（底层，成熟）
    ✗ 没有被使用
routes_agent_v3.py（agent 层，不使用 completion_contract）
    ↓ 被使用
agent_mcp.py（public agent MCP，没有 completion_contract）
    ❌ coding agent 用这个，拿不到答案质量元数据
```

问题不是"advisor 系统太复杂"，而是 **agent 层忘了把 completion_contract 投射上来**。

### 错误 3：controller/engine.py 的 reconcile 逻辑不是"child promotion 缺失"

Codex 说 `_reconcile_job_work_item()` 的 child promotion 逻辑有问题。我验证了代码：

`_reconcile_job_work_item()`（engine.py:1768）的逻辑是：
1. 检查 `job.status.value == "completed"` 且 `job.answer_path` 存在
2. 读取答案文本（最多 20,000 字符）
3. 创建 `StepResult` 并持久化

这个逻辑是正确的——它确实把 child job 的结果提升到了 parent controller。问题不在 promotion 逻辑本身，而在于 **promotion 后的结果没有经过 completion_contract 处理**。controller 用简单的 status 判断（completed/needs_followup/error），没有用 answer_state/finality_reason 等质量元数据。

---

## 第三部分：方向性偏差

### 偏差 1："回到 web-first"是错误的二分法

Codex 把选择框定为"advisor agent MCP vs web-first MCP"。这是一个假二分法。

实际情况是系统已经有两个 MCP server，服务两类不同的客户端：

| | Web 自动化 MCP (server.py) | Public Agent MCP (agent_mcp.py) |
|---|---|---|
| 规模 | 153K 行，50+ 工具 | 55K 行，6 工具 |
| 客户端 | 直接 web 自动化调用方 | Codex/Claude Code/Antigravity |
| completion_contract | ✅ 已投射 | ❌ 未投射 |
| 答案质量元数据 | ✅ answer_state, authoritative_answer_path | ❌ 只有 last_answer |
| 路由/编排 | ❌ 无 | ✅ 有（task_intake, scenario_pack） |
| 项目上下文 | ❌ 无 | ✅ 有（available_inputs, project_context） |

正确的方向不是"让 coding agent 回到 web 自动化 MCP"，而是：

1. **把 completion_contract 投射到 public agent MCP**（修复缺口）
2. **让 coding agent 可以选择轻量模式**（跳过 advisor 编排，直接提交 web 任务）
3. **保留 advisor 编排作为可选增强**（OpenClaw 和复杂任务仍然需要）

### 偏差 2：7 阶段方案的前 2 步顺序错误

Codex 的方案：
1. 冻结产品边界
2. 恢复 coding agent web-first MCP
3. OpenClaw 编排层
4. Authority anchor 收紧
5. project_id 贯穿
6. Promotion pipeline 修复
7. Harness 驱动演化

我的判断：**步骤 1 和 2 应该合并为一个更精确的动作。**

"冻结产品边界"太抽象——冻结什么？不做什么？这需要具体化。"恢复 web-first MCP"是基于错误前提（web MCP 已经存在且成熟）。

正确的第一步应该是：**修复 public agent MCP 的 completion_contract 投射缺口**。这是一个精确的、可验证的、影响范围小的改动，能立即解决 Deep Research 场景下 coding agent 拿不到完整答案的问题。

---

## 第四部分：我的独立方案

### 核心判断

ChatgptREST 的问题不是"做了太多事"，而是"两个 MCP surface 的能力不对齐"。

web 自动化 MCP 有 completion_contract 但没有 advisor 编排。
public agent MCP 有 advisor 编排但没有 completion_contract。

修复方向是**对齐**，不是**回退**。

### 方案：3 步修复 + 4 步演进

#### 修复 A（阻断级，1-2 天）：completion_contract 投射到 agent MCP

具体改动：

1. `routes_agent_v3.py` 的 `_session_response()` 增加 completion_contract 字段：
   ```python
   from chatgptrest.core.completion_contract import (
       get_completion_answer_state,
       get_authoritative_answer_path,
       get_authoritative_job_id,
       get_answer_provenance,
       is_research_final,
   )
   ```
   在 `_session_response()` 中，当 session 有关联 job 时，计算并返回：
   - `answer_state`
   - `authoritative_answer_path`
   - `authoritative_job_id`
   - `answer_provenance`
   - `answer_ready`（基于 `is_research_final()`）

2. `agent_mcp.py` 的 `advisor_agent_status` 和 `advisor_agent_wait` 返回值自动包含这些字段（因为它们调用 `_session_response()`）

3. 新增 `advisor_agent_answer` 工具：
   ```python
   async def advisor_agent_answer(
       ctx: Context | None,
       session_id: str,
       offset: int = 0,
       max_chars: int = 80000,
   ) -> dict[str, Any]:
       """Fetch the canonical answer for a completed session."""
   ```
   这个工具从 `authoritative_answer_path` 读取完整答案，处理分页。

验收：coding agent 调用 `advisor_agent_wait` 后能看到 `answer_state="final"` 和 `answer_ready=True`，然后调用 `advisor_agent_answer` 获取完整答案。

#### 修复 B（重要，1 天）：wrapper 脚本简化

`chatgptrest_call.py` 的 agent 模式应该利用新的 completion_contract 字段：

1. 用 `answer_ready` 替代当前的 terminal status 猜测
2. 用 `advisor_agent_answer` 替代从 `last_answer` 提取答案
3. 移除不再需要的 transport recovery 逻辑（如果 wait 本身已经可靠）

目标：agent 模式的核心逻辑从 ~300 行降到 ~100 行。

#### 修复 C（中等，1 天）：controller/engine.py 使用 completion_contract

`_reconcile_job_work_item()` 应该用 `completion_contract_from_job_like()` 而不是简单的 status 检查：

```python
from chatgptrest.core.completion_contract import completion_contract_from_job_like

contract = completion_contract_from_job_like(job_dict)
if contract.get("answer_state") == "final":
    # 真正完成
elif contract.get("answer_state") == "provisional":
    # Deep Research 还没最终确认
```

这样 controller 就能正确处理 Deep Research 场景下"status=completed 但答案还不是 final"的情况。

#### 演进 1：authority anchor 收紧（对应 Codex Phase 4）

与之前的审核意见一致，不再重复。

#### 演进 2：project_id 贯穿（对应 Codex Phase 5）

与之前的 9 changeset 需求定义一致，不再重复。关键前置：scope_project 一次性回填。

#### 演进 3：promotion pipeline 修复（对应 Codex Phase 6）

需要先诊断 0.19% active 率的根因。初步假设：
1. groundedness gate 通过率低
2. promotion 没有定期调度
3. 需要数字目标（从 0.19% 到至少 5%）

#### 演进 4：产品边界文档化（对应 Codex Phase 1，但放在最后）

在修复和演进都完成后，再写产品边界文档。因为边界应该从实际代码状态推导，而不是先画边界再改代码。

---

## 第五部分：对 Codex 6 条验收标准的逐条评价

### Codex 标准 1："coding agent 默认走 web-first MCP"

**不同意。** coding agent 应该继续走 public agent MCP，但 public agent MCP 需要投射 completion_contract。理由：
- public agent MCP 已经有 task_intake、delivery_mode、workspace_request 等 coding agent 需要的编排能力
- web 自动化 MCP 有 50+ 工具，对 coding agent 来说噪音太大
- 问题不是"用哪个 MCP"，而是"agent MCP 缺了 completion_contract"

### Codex 标准 2："advisor agent 只作为 OpenClaw 后端"

**部分同意。** advisor pipeline 对 OpenClaw 确实是必要的。但 coding agent 也可能需要 advisor 的路由能力（选择 ChatGPT vs Gemini vs Qwen）。应该是"coding agent 可以选择是否经过 advisor 编排"，而不是"coding agent 不能用 advisor"。

### Codex 标准 3："web MCP 暴露 submit/wait/result/cancel/conversation"

**方向正确，但实现方式不对。** 这 5 个操作应该作为 public agent MCP 的轻量模式暴露，而不是让 coding agent 切换到 web 自动化 MCP。

### Codex 标准 4："completion_contract 投射到 public surface"

**完全同意。** 这是最关键的修复。

### Codex 标准 5："wrapper 脚本简化"

**完全同意。** 1616 行 wrapper 是复杂度的症状。

### Codex 标准 6："产品边界冻结"

**同意方向，不同意时序。** 应该先修复再冻结，而不是先冻结再修复。

---

## 第六部分：综合判断

### Codex 做对了什么

1. **诊断准确**：completion_contract 没有投射到 public agent MCP 是真实的代码缺口
2. **根因正确**：ChatgptREST 确实从 web 自动化演变成了承载过多职责的平台
3. **方向正确**：需要简化 coding agent 的使用路径
4. **数据扎实**：用真实代码和数据支撑判断

### Codex 做错了什么

1. **误判了 web 自动化 MCP 的状态**：它已经有 completion_contract 投射，不需要"恢复"
2. **假二分法**：不是"advisor vs web-first"的选择，而是"对齐两个 surface"的问题
3. **方案过重**：7 阶段方案的前 2 步可以用一个精确的 completion_contract 投射修复替代
4. **时序错误**：应该先修复代码缺口，再讨论产品边界

### 我的优先级排序

1. **立即做**：completion_contract 投射到 agent MCP（修复 A）
2. **紧接着做**：controller/engine.py 使用 completion_contract（修复 C）
3. **然后做**：wrapper 脚本简化（修复 B）
4. **之后做**：project_id 贯穿（已有 9 changeset 定义）
5. **再之后**：authority anchor 收紧 + promotion pipeline 修复
6. **最后做**：产品边界文档化

### 一句话总结

> Codex 正确诊断了 public agent MCP 的 completion_contract 投射缺口，但把修复方案过度扩大成了"回到 web-first"的平台重构。实际需要的是一个精确的投射修复（把已有的 completion_contract 能力从 web 自动化 MCP 复制到 agent MCP），而不是让 coding agent 换一个 MCP server。


