# 2026-04-07 Full Execution Master Plan v1

## 1. 目的

这份文档是本轮 `A-F` 全盘实施的唯一执行锚点。

目标不是再讨论方向，而是把：

1. 当前已确认的问题
2. 批次化实现路径
3. 每批验收标准
4. Claude 审核闭环
5. 文档与提交纪律

全部固定下来，避免后续实现依赖会话记忆。

## 2. 已冻结的执行原则

### 2.1 这轮先做什么

按优先级执行：

1. `A`：Public Agent MCP completion contract 投射修复
2. `B0 + C + D`：project-scoped substrate 地基与 authority 合同
3. `E`：OpenClaw / OpenMind project-aware 贯通
4. `F`：promotion pipeline 恢复与 harness 回放

### 2.2 这轮不做什么

1. 不把 `server.py` 二次角色拆分混进当前 bug 修复
2. 不先做新的 product 面重构
3. 不把 `_project_context.md` 扩成大而全缓存文件
4. 不先做“自动进化”宣传式改造，先修可用性和 substrate 主链

## 3. Claude 审核闭环结论

### 3.1 官方 `resume` 能力结论

已按 Claude Code 官方文档确认：

1. `claude --resume <session-id>` 官方支持按 session ID 恢复会话
2. `--fork-session` 官方支持基于旧会话上下文分叉新会话
3. `--print --output-format json` 官方支持非交互脚本式调用

官方文档来源：

1. `https://code.claude.com/docs/en/cli-reference`
2. `https://code.claude.com/docs/en/tutorials`

### 3.2 本机 smoke test 结论

已做本机 smoke test：

1. 当前默认 Claude CLI 运行环境：
   - `HOME=/home/yuanhaizhou`
   - `claude 2.1.92`
2. 直接 `resume 45e39abb-3440-40d6-88fa-11624251b4cb` 失败：
   - `No conversation found with session ID`
3. 进一步确认：
   - 当前历史 Claude 会话大量保存在 `/vol1/1000/home-yuanhaizhou/_root_home/.claude`
   - 但该特定 session id 仍未在本机可恢复存储中找到
4. 结论：
   - **Claude 的 `resume` 能力本身可用**
   - **这条现成的 `claudegac` session 目前不在本机可恢复会话存储里**
   - 本轮审核自动化不能依赖该旧 session，必须创建一条新的、受控的 Claude 审核会话并持续复用

### 3.3 本轮 Claude 审核策略

本轮采用：

1. Codex 主开发
2. `claudegac` 审核
3. 审核会话改为**新建受控会话**，后续统一用 `resume` 延续
4. 不使用 `agent teams` 做主开发
5. 不使用 `claudeminmax` 做主编码；如需要，只用于边界测试或 sidecar 审查

## 4. 批次执行图

### Batch A1：Public agent completion contract projection

范围：

1. `chatgptrest/api/routes_agent_v3.py`
2. `chatgptrest/mcp/agent_mcp.py`
3. `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`

目标：

1. `_job_snapshot -> _controller_snapshot -> _session_response` 贯通 completion contract
2. `delivery.answer_ready` 改为 finality-aware
3. 新增 `advisor_agent_answer`
4. wrapper 以 `answer_state` 为准，不再只靠 `last_answer`

验收：

1. Deep Research final：`wait` 后可稳定取回完整正文
2. Deep Research provisional：不再误报 `answer_ready=true`
3. no-job session：`advisor_agent_answer` 回退 `last_answer`
4. 普通短回答：兼容现有行为

### Batch A2：Controller 稳态 contract-aware reconcile

范围：

1. `chatgptrest/controller/engine.py`

目标：

1. `_reconcile_job_work_item()` 按 completion contract finality 而非简单 `completed` 判断交付

验收：

1. 不再把 provisional research answer 提前晋升为 final delivery

### Batch B0：scope_project 前置修复包

范围：

1. `chatgptrest/evomap/knowledge/schema.py`
2. `chatgptrest/evomap/knowledge/db.py`
3. ingest / migration 脚本

目标：

1. 修正 `Atom.scope_project` dataclass / DB 对齐缺口
2. 回填已有 atoms 的 `scope_project`
3. 新 ingest 自动继承 project scope

验收：

1. `Atom.from_row()` 不再静默丢 `scope_project`
2. 绝大多数 atoms 具备 `scope_project`

### Batch C+D：project_id threading + authority contract

范围：

1. `memory_manager`
2. `work_memory_manager`
3. `context_service`
4. `context_assembler`
5. `routes_cognitive`
6. `signals / telemetry / event bus`
7. `advisor/prompt_builder.py`

目标：

1. `project_id` 进入主 recall / resolve / telemetry 主链
2. authority 优先级合同同时落在 `ContextAssembler` 和 `prompt_builder`

硬规则：

`authority anchor > project memory > EvoMap knowledge > KB evidence > runtime heuristics`

验收：

1. 同 query 在不同 project_id 下结果不同
2. authority anchor 永远不会被自动检索覆盖
3. token 裁剪不会先裁 authority 内容

### Batch E：OpenClaw / OpenMind project-aware integration

范围：

1. `openclaw_extensions/openmind-advisor`
2. `openclaw_extensions/openmind-memory`
3. `openclaw_extensions/openmind-telemetry`
4. `openclaw-workspaces/main/AGENTS.md`
5. `planning` 项目 authority anchor 文件

目标：

1. `projectRef -> project_id` 稳定贯通
2. OpenClaw 对项目型请求不再自己乱找文件
3. project-aware memory/telemetry/advisor 注入统一

验收：

1. Feishu / OpenClaw 项目型请求稳定进入 advisor/plugin backend
2. planning 与 PRS 两个项目均可加载 authority anchor

### Batch F：promotion pipeline + harness

范围：

1. `evomap/evolution/*`
2. harness / replay / acceptance docs

目标：

1. 先诊断 promotion pipeline 失活根因
2. 再恢复 batch promotion / active retrieval
3. 最后接 harness 回放与 eval

验收：

1. active retrieval 对关键项目规则可用
2. harness replay 能稳定验证 project-scoped context 是否生效

## 5. 审核与证据纪律

### 5.1 每批都必须有

1. review 文档
2. walkthrough 文档
3. 必要测试
4. 单独 commit
5. GitNexus detect changes
6. closeout

### 5.2 Claude 审核方式

每个主批次完成后：

1. 生成最小审查包
2. 送入新的受控 `claudegac` 会话
3. 保存审核结论与需要修正的点

## 6. 当前执行起点

当前起点是：

1. `Batch A1`
2. 同时准备新 `claudegac` 审核会话
3. `engine.py` contract-aware reconcile 放到 `Batch A2`

这就是本轮的正式执行主线。
