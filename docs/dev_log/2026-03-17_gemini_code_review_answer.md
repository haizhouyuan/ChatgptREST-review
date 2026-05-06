基于你上传的完整代码仓库，结合你目前的硬件物理约束（ThinkPad 8GB 内存承载核心调度 + HomePC RTX 提供本地算力）以及 7 天的运行数据（1.75h/4.3h 的异常周转时间、零 Scorecard），系统目前面临三大核心瓶颈：“非飞书入口被旁路导致大模型被滥用”、“长链接缺乏有效熔断导致死等”、“验收打分平面断环”。

以下是严格基于代码现状给出的深度优化方案：

Q1: 功能优先级（Top 4，按 ROI 排序）

这 4 个问题代码修改量极小，但能瞬间打通阻塞的系统。

1. 修复 MCP 入口旁路与 Skill 预检缺失 (ROI: 最高)

代码位置：mcp/server.py 第 1290 行 (chatgptrest_ask 工具)。

问题：MCP 工具直接组装参数调用了底层的 chatgptrest_job_create，完全跳过了 advisor/standard_entry.py 中的规范化管线。这导致非飞书入口的请求缺失了 Preset 推荐、意图识别和 Agent 的 Skill 预检。

优化：引入 process_mcp_request，将入口请求先通过标准管线验证。

代码量估算 & 效果：~15 行。100% 拦截无能力的 Agent 派发，过滤无效短词测试，预计削减 20%+ 的无意义云端队列。

2. 修复 Preset 防误选的逻辑 Bug (ROI: 极高)

代码位置：advisor/standard_entry.py 第 98 行 (if not validation["ok"]:)。

问题：当用户的 Preset 校验不通过（比如拿 pro_extended 问今天天气，成本极度 Overkill 时），代码只是把警告写入了 result["steps"]["preset_warnings"]，并没有强制覆盖 request.preset，导致杀鸡用牛刀的任务依然流向了昂贵的 Web 队列！

优化：在分支内强制降级：request.preset = validation["recommended"]["preset"]。

代码量估算 & 效果：2 行。彻底阻断高配预设的滥用，大幅降低排队耗时。

3. 修复 Scorecard 漏报 Bug (ROI: 高)

代码位置：advisor/qa_inspector.py 第 348 行 (write_evomap_feedback 方法)。

问题：7 天数据中 Scorecards: 0。因为 8D 质检（QualityReport8D）完成后，代码仅仅调用了 _insert_atom 将报告当作文章写入 EvoMap，完全遗漏了写入计分卡。

优化：引入并调用 TeamScorecardStore。

代码量估算 & 效果：~10 行。激活沉睡的 OpenClaw 记分卡看板。

4. 斩断后台长尾死锁 (ROI: 高)

代码位置：mcp/_bg_wait_config.py 第 20 行。

问题：背景等待任务硬编码了 timeout_seconds: int = 43200 (长达 12 小时！)。配合 chatgpt_web_mcp.py 中 UI 卡死（Answer Now）时的无限重试，导致周转时间被拉长到 1.75h/4.3h。

优化：将其降至 3600（1小时），在 MCP Web 端遇阻时抛出 NeedsFollowup 释放资源，由 repair.autofix 异步回收。

Q2: ChatGPT/Gemini 优化方案（含 Preset 矩阵与防误选）
1. Preset 分类矩阵（适配 8G + RTX 架构）

基于 advisor/preset_recommender.py 重构物理层映射，将计算压力合理分配：

Simple (短问题/轻翻译/调度意图): 强制路由 local_llm (HomePC 跑开源小模型)。耗时：10-30s。

Moderate (代码开发/Review): 推荐 chatgpt: thinking_heavy 或 gemini: pro。目前 repair 模块成功率 100%，证明此档模型稳定度最高。耗时：5-10m。

Complex (多步推理/架构设计): 推荐 chatgpt: pro_extended。但严禁携带大量碎文件。耗时：30m。

Research (大附件/全网深研): 推荐 gemini: deep_think。Gemini 传文件的 DOM 稳定性远超 ChatGPT，应发挥其 1M 上下文优势。

2. 提升 Gemini 成功率 (55-69% -> 85%)

在 executors/config.py 中，Gemini 的 wait_transient_failure_limit (第 160 行) 目前默认只有 3。网页版 Gemini 处理大文件时极易发生网络流断连。将其提升至 5，同时利用现有的 dr_gdoc_fallback_enabled (第 179 行)，一旦深研超时，立即切为 Google Doc 离线导出兜底，避免 4.3h 的 DOM 死等。

Q3: HomePC 本地模型利用方案（路由与分层策略）

8GB 的 ThinkPad 仅作为轻量级 Orchestrator，必须将高频内部节点下放至 HomePC。

1. 节点分层卸载 (Tiered Offloading)

控制面 (L0 - ThinkPad 内存运行): 仅保留 advisor/graph.py 中的 normalize 和 kb_probe（正则清洗与 SQLite FTS5 查询）。

逻辑抽取面 (L1 - HomePC RTX 运行): 强制修改 advisor/graph.py 的 _get_llm_fn，将 analyze_intent, rubric_a, purpose_identify, redact_gate (脱敏) 等分类、总结节点，全部切向 LocalLLMExecutorConfig。在 config.py (第 297 行) 中配置 CHATGPTREST_LOCAL_LLM_ENDPOINT_URL = "http://<HomePC_IP>:11434/v1"。

执行与深研面 (L2 - Web MCP 运行): 仅允许 deep_research 和高管汇报的 external_draft 进入 Web MCP 队列排队。

2. 路由决策树植入极速通道

在 advisor/__init__.py 的 select_route (第 115 行附近)，增加本地优先拦截逻辑：

Python
# 在 Stage B 的顶部新增本地兜底通道：
if scores.complexity < 30 and scores.risk < 30 and not intent.action_required:
    return RouteDecision(
        route="local_llm", # 直接短路外部 API，路由给 HomePC
        scores=scores,
        rationale=f"C={scores.complexity:.0f}<30, 无高风险动作 → 极速本地通道"
    )

Q4: OpenClaw 质量保证方案（自评、验收与闭环）

目前系统的执行面和验收面严重割裂（这正是你 task_spec.py 注释中提到的 Pro/Gemini 给出的核心洞察）。

1. 非飞书入口强制标准化 (TaskSpec)

所有的 MCP 请求进入 mcp/server.py 时，必须通过 IntentEnvelope 进行包裹转换：

Python
from chatgptrest.advisor.task_spec import IntentEnvelope, envelope_to_task_spec

# MCP 入口第一行：
envelope = IntentEnvelope(source="mcp", raw_text=question, ...)
task_spec = envelope_to_task_spec(envelope)
# 后续依据 task_spec.lane 决定是放后台还是交互式队列

2. 自评数据结构与闭环验收

系统有极其优秀的 8D 质检模块 (QualityReport8D) 和 AcceptanceSpec，但它们没牵手。

数据结构对齐：将 TaskSpec.acceptance.pass_score (默认 0.8) 作为卡点阈值。将 QualityReport8D 产出的 total_score() / max_total() 作为实际得分。

流程闭环：在 advisor/report_graph.py 的 _review_or_rewrite 节点 (第 329 行)，现在的逻辑是固定的 review_score < 7 重写。必须改为：
当 8D 质检跑完，如果 score_pct < pass_score，不发出 dispatch.task_completed 信号。而是提取 8D 报告中的 D5 (root_causes) 和 D6 (corrective_actions) 作为 review_notes，强行打回给 OpenClaw 的 rewrite_with_feedback 节点重做。

3. 激活 Scorecards 看板

在 advisor/qa_inspector.py 的 write_evomap_feedback 中补全缺失的计分卡落库代码：

Python
try:
    from chatgptrest.evomap.team_scorecard import TeamScorecardStore
    store = TeamScorecardStore(db_path=_EVOMAP_DB)
    # 计算均分并真正写入 Scorecard
    avg_score = sum(r.score_pct() for r in reports) / len(reports)
    store.record(
        trace_id=reports[0].task_id,
        agent_id=reports[0].evaluator_model,  # 记录是由谁打的分
        task_type="openclaw_task",
        metrics={
            "completeness": reports[0].completeness.score,
            "accuracy": reports[0].accuracy.score,
            "actionability": reports[0].actionability.score
        },
        verdict=reports[0].overall_verdict,
        composite_score=avg_score
    )
except Exception as e:
    logger.warning("Scorecard write failed: %s", e)


加入后，repair.autofix 和各类 Agent 的运行质量将瞬间在看板上可视化，真正实现“调度-执行-自评-纠正”的全闭环。
