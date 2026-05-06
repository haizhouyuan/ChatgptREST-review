# ChatGPT Wrapper V1 开发记录与总结（2026-02-24）

## 1. 背景与目标

本轮目标：在不改动 ChatgptREST 核心代码（`chatgptrest/`）前提下，将 v0 壳层增强为 v1 顾问层，并完成“外部双审（ChatGPT Pro + Gemini Deep Think）→ 吸收建议 → 全量落地 → 测试回归”的闭环。

约束：
- 仅改动 `ops/` 与 `tests/`。
- 保持与 v0 执行能力兼容（v1 调用 v0 ask/wait 链路）。
- 最小侵入，不做架构性重构。

## 2. 交付范围

本轮代码交付：
- `ops/chatgpt_wrapper_v1.py`
- `tests/test_wrapper_v1.py`

本轮文档交付：
- `docs/reviews/wrapper_v1_dual_review_devlog_20260224.md`（本文件）

## 3. 外部审阅任务记录（可审计）

### 3.1 Gemini Deep Think 审阅
- job_id: `3da022b3b978414c8a5f478ae62259a5`
- kind: `gemini_web.ask`
- 状态: `completed`
- 完成时间: `2026-02-24 12:02:51 CST`
- 结论: 提出上下文透传、兼容性、自愈状态管理、解析鲁棒性等关键问题。

### 3.2 ChatGPT Pro 审阅
- job_id: `9ddbc3a23dca4e89b7297ed74dd6a35e`
- kind: `chatgpt_web.ask`
- 状态: `completed`
- 完成时间: `2026-02-24 12:22:40 CST`
- 结论: 强调 gaps/force 语义一致性、answer_contract 结构稳定性、动态加载容错与测试补强。

### 3.3 中间取消任务（不影响最终交付）
- job_id: `f74344543aa440f2bb9f64a50d01dead`
- kind: `chatgpt_web.ask`
- 状态: `canceled`
- 时间: `2026-02-24 12:10:40 CST`
- 说明: 早期等待中的重提单取消，最终由 `9dd...` 完成 Pro 审阅。

## 4. 审阅建议落地映射

### 4.1 已落地（代码已实现）

1) 上下文透传与 prompt 增强
- 变更点：`prompt_refine(raw_question, context)` 支持注入 `context`。
- 价值：避免 context 黑洞，提升顾问层提问质量与约束一致性。

2) gaps 阻断兼容性修复
- 变更点：`if gaps and not force` 才返回 `needs_context`。
- 变更点：`force=True` 且有 gaps 时，显式注入“待确认信息/假设”到执行问题。
- 价值：保留默认安全阻断，同时不破坏 v0 存量“强制执行”语义。

3) answer_contract 解析鲁棒性提升
- 变更点：支持 fenced code block 跳过（避免代码块伪标题误判）。
- 变更点：支持中英标题别名映射与编号/加粗标题容错。
- 变更点：`source_refs` 优先从来源段提取并去重保序。
- 变更点：URL 尾标点清洗（中英文标点）。

4) v0 动态加载健壮性
- 变更点：`_load_v0_class` 增加 `RLock`。
- 变更点：检测到缓存模块不完整时主动清理并重载。
- 变更点：加载失败清理 `sys.modules` 半初始化残留。
- 变更点：支持 `CHATGPT_WRAPPER_V1_FORCE_RELOAD` 可控强制重载（默认关闭，兼容现有行为）。

5) 自愈链路状态处理加固
- 变更点：`_try_fill_conversation_url` 同时兼容 object-state 与 dict-state。
- 变更点：state 为 `None` 时直接返回 `False`（防止假阳性自愈）。
- 变更点：conversation_url 未变化时不重复 `_save_state()`。

6) gap_check 边界修复
- 变更点：英文歧义词检测统一对 lower-case 文本匹配。

### 4.2 选择性保留（本轮未做）

1) `_save_state()` 原子写改造
- 原因：v1 兼容层不直接重写 v0 的持久化实现，避免超出“最小侵入”边界。
- 处理：本轮通过“仅变更才写盘”降低写放大和并发触发概率。

2) route 计算延后
- 原因：当前 route 计算为纯字符串规则，无额外调用成本；保留当前顺序可读性更高。

## 5. 测试与验证

执行命令：
- `./.venv/bin/pytest -q tests/test_wrapper_v1.py`
- `./.venv/bin/python -m py_compile ops/chatgpt_wrapper_v1.py tests/test_wrapper_v1.py`

结果：
- `pytest`：`25 passed`
- `py_compile`：通过

新增/增强测试覆盖：
- prompt_refine：结构化改写、空输入模板、context 注入。
- question_gap_check：缺失项检测、大小写不敏感歧义识别、完整上下文无追问。
- channel_strategy：research 路由、组合路由、cross-check 路由。
- answer_contract：
  - 结构化 markdown 解析
  - plain text fallback
  - 编号/加粗标题容错
  - code fence 伪标题忽略
  - 同义标题映射
  - URL 尾标点清洗
- wrapper 兼容与执行：
  - v0 兼容执行
  - 缺上下文阻断
  - force 放行并带 assumptions
  - `from_v0` 构造
- 动态加载与自愈：
  - `_load_v0_class` 幂等与坏缓存恢复
  - idempotency-key 错误重试
  - conversation_url 自愈（object/dict/None）
  - URL 不变时不写盘

## 6. 风险与回滚

风险评估（当前状态）：
- 兼容性风险：低（保留 v0 委托执行，不触碰 chatgptrest 核心）。
- 行为变化风险：中低（force + gaps 分支新增 assumptions 注入，属预期增强）。

回滚策略：
1. 直接回滚 commit（仅涉及 3 个文件，回滚范围清晰）。
2. 若仅需关闭热行为：不使用 v1 入口，继续走 `chatgpt_agent_shell_v0.py`。
3. 若动态加载行为需复旧：不设置 `CHATGPT_WRAPPER_V1_FORCE_RELOAD`。

## 7. 总结

本轮目标已闭环完成：
- 完成了 v1 实现与测试。
- 完成了 Pro + Gemini 双审。
- 已按审阅意见完成关键增强并回归通过。

当前 v1 达到可用基线：
- 具备顾问层四项能力（问题改写、缺口识别、渠道策略、答案契约）。
- 保持 v0 执行兼容。
- 增加了复发场景下的自愈与鲁棒性保障。
