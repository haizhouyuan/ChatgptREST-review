# ChatgptREST 链路跑通修复与调整计划（2026-02-24）

## 1. 目标

- 目标 1：修复 `deep_research` 场景中 export 错误覆盖答案的问题，避免“完成但答案无效”。
- 目标 2：在当前 MCP stateless 运行模式下，消除 `background wait` 误用导致的“假等待/误判卡死”。
- 目标 3：降低外部自动取消对正常推进 job 的误伤，恢复链路稳定收敛。

## 2. 问题分层与优先级

1. `P0-A`（代码缺陷）  
   `answer_reconciled_from_conversation` 路径会在 `prefer_export=True` 时直接替换答案，未复用 DR finality guard。
2. `P0-B`（语义缺陷）  
   completion guard 对 `search_query` 类工具 JSON 缺乏“非正文”识别，可能 fail-open 为 completed。
3. `P0-C`（运行策略）  
   生产主要为 stateless MCP，background wait 不应作为默认依赖路径。
4. `P1`（编排协同）  
   外部 stale-recovery cancel 在 send/wait 正常推进窗口内触发，误杀有效作业。

## 3. 修复计划（执行顺序）

### 3.1 P0-A：修复 DR export 覆盖路径

- 文件：`chatgptrest/worker/worker.py`
- 改动点：
  - 在 post-completion 的 `if cand and prefer_export` 分支前增加统一 guard：
    - `deep_research=true` 且 `_deep_research_export_should_finalize(cand)` 为 `False` 时禁止替换；
    - connector/tool-call stub 时禁止替换。
  - 增加事件：`answer_reconcile_skipped_by_guard`，记录 `reason`、`export_answer_chars`、`export_match`。
- 预期效果：
  - `implicit_link::connector_openai_deep_research` payload 不再落成最终 `answer.txt`。

### 3.2 P0-B：增加“非正文工具输出”识别

- 文件：`chatgptrest/worker/worker.py`
- 改动点：
  - 增加 `_looks_like_tool_payload_answer()`（检测 top-level `search_query`、`response_length` 等）。
  - 在 completion guard 前执行：
    - 命中后不走“completed_under_min_chars”终态；
    - 转为继续等待（优先）或可配置 error（谨慎启用）。
  - 事件：`completion_guard_downgraded` 增加 `reason=tool_payload_not_final`。
- 预期效果：
  - 避免“结构化搜索请求 JSON”被当作最终研究正文。

### 3.3 P0-C：链路运行策略调整（stateless MCP）

- 文件：`~/.config/chatgptrest/chatgptrest.env`（运行配置）与文档 `docs/runbook.md`
- 建议配置：
  - `CHATGPTREST_MCP_WAIT_FOREGROUND_ENABLED=1`
  - `CHATGPTREST_DISABLE_FOREGROUND_WAIT=0`
  - `CHATGPTREST_MCP_WAIT_AUTO_BACKGROUND=0`（或阈值调到长任务不触发）
- 说明：
  - 在 stateless MCP 下，foreground wait + bounded timeout 是更稳定主路径。
  - background wait 只在明确 stateful 运行（`FASTMCP_STATELESS_HTTP=0`）时启用。

### 3.4 P1：外部取消治理

- 文件：`chatgptrest/api/routes_jobs.py`（策略约束）+ 编排侧策略文档
- 规则建议：
  - 自动 cancel 保护窗：`in_progress < 180s` 禁止 stale-recovery 自动取消；
  - 强制结构化取消原因：`policy_name + trigger + trace_id`；
  - cancel 事件指标化：按 `x_client_name/x_client_instance/x_cancel_reason` 统计告警。

## 4. 测试计划

1. `test_deep_research_reconcile_guard.py`  
   构造 export 为 `implicit_link` payload，断言不覆盖 raw answer，并写 `answer_reconcile_skipped_by_guard`。
2. `test_tool_payload_not_final_guard.py`  
   构造 `{"search_query":[...],"response_length":"short"}`，断言不会完成为最终正文。
3. 扩展 `tests/test_mcp_job_wait_autocooldown.py`  
   覆盖 stateless 下 wait 兜底行为（无假 background running）。
4. 回归组合：
   - `tests/test_deep_research_export_guard.py`
   - `tests/test_conversation_export_reconcile.py`
   - `tests/test_min_chars_completion_guard.py`
   - `tests/test_mcp_job_wait_background.py`（stateful 条件下）

## 5. 发布与回滚

1. 先合入代码修复（P0-A/P0-B）+ 单测。
2. 在预发开启并跑 20+ 真实样本（含 DR、thinking_heavy、web_search）。
3. 生产仅先切 P0-C 策略；P1 外部取消治理与编排方灰度联动。
4. 回滚策略：
   - 保留 feature flag（tool_payload guard 可开关）；
   - 出现误伤时先关闭新 guard，保留事件采样继续观察。

## 6. 验收标准（7 天窗口）

1. `deep_research` completed 中 `implicit_link` payload 误完成数 = 0。
2. `completed_under_min_chars` 且正文为 `search_query` 工具 JSON 的占比接近 0。
3. 自动 cancel 中 `in_progress < 180s` 的占比 = 0。
4. 人工“卡住后强制取消”工单数显著下降。
5. 样本链路：submit -> wait -> answer_get 成功率达到预期并稳定。

## 7. 执行进展（2026-02-24）

### 7.1 已完成变更

1. `P0-A` 已实现（代码）
   - 新增 helper：`_should_reconcile_export_answer()`
   - post-completion reconcile 路径在替换 answer 前强制执行 guard：
     - 阻断 `deep_research_not_final`（如 `implicit_link` payload）
     - 阻断 connector tool-call stub
   - 新增事件：`answer_reconcile_skipped_by_guard`
2. `P0-B` 已实现（代码）
   - 新增 helper：`_looks_like_tool_payload_answer()`
   - completion guard 中增加 `tool_payload_not_final` 降级路径（`min_chars>0` 时生效）
   - `completion_guard_downgraded` 事件 payload 增补 `tool_payload` 细节
3. 文档与流程
   - 本计划文档已更新为执行态
   - 保持 stateless MCP 下 foreground wait 主路径策略

### 7.2 新增/更新测试

1. 更新：`tests/test_deep_research_export_guard.py`
   - 覆盖 `_should_reconcile_export_answer()` 对 implicit-link/connector stub 的拦截行为
2. 新增：`tests/test_tool_payload_answer_guard.py`
   - 覆盖 `search_query + response_length` payload 检测与误判防护

### 7.3 测试结果（本轮）

1. 通过：
   - `pytest -q tests/test_deep_research_export_guard.py tests/test_tool_payload_answer_guard.py tests/test_conversation_export_reconcile.py tests/test_min_chars_completion_guard.py`
   - 结果：`27 passed`
2. 通过：
   - `pytest -q tests/test_worker_and_answer.py tests/test_mcp_job_wait_autocooldown.py tests/test_mcp_stateless_mode.py tests/test_mcp_job_wait_background.py tests/test_client_name_allowlist.py`
   - 结果：`41 passed`
3. 环境内既有问题（与本次改动无关）：
   - `tests/test_deep_research_classify.py` 在当前代码基线出现 import error（缺少 `_classify_non_deep_research_answer` 导出）
   - 该失败未阻断本次改动相关测试集

### 7.4 追加回归（充分测试补充）

1. 全量回归尝试：
   - 命令：`./.venv/bin/pytest -q`
   - 结果：在 collection 阶段被既有 import error 中断（`tests/test_deep_research_classify.py`），未进入完整执行
2. 全量近似执行（忽略 collection 阶段中断继续）：
   - 命令：`./.venv/bin/pytest -q --continue-on-collection-errors`
   - 结果：除上述 import error 外，新增 1 个既有失败：
     - `tests/test_driver_singleton_lock_guard.py::test_maint_start_driver_if_down_skips_script_fallback_when_systemd_loaded`
     - 失败原因为测试桩未覆盖新引入的 `systemctl --user reset-failed ...` 调用，属于测试基线漂移
3. 本次修复相关回归（强相关套件）：
   - 命令：`./.venv/bin/pytest -q tests/test_deep_research_export_guard.py tests/test_tool_payload_answer_guard.py tests/test_conversation_export_reconcile.py tests/test_min_chars_completion_guard.py tests/test_worker_and_answer.py tests/test_mcp_job_wait_autocooldown.py tests/test_mcp_stateless_mode.py tests/test_mcp_job_wait_background.py tests/test_client_name_allowlist.py`
   - 结果：全部通过（`68 tests collected`，执行通过）
4. review 合并后的回归（新增审计测试）：
   - 命令：`./.venv/bin/pytest -q tests/test_wait_no_progress_guard_audit.py tests/test_deep_research_export_guard.py tests/test_tool_payload_answer_guard.py tests/test_conversation_export_reconcile.py tests/test_min_chars_completion_guard.py tests/test_worker_and_answer.py tests/test_mcp_job_wait_autocooldown.py tests/test_mcp_stateless_mode.py tests/test_mcp_job_wait_background.py tests/test_client_name_allowlist.py`
   - 结果：全部通过（`69 tests collected`，执行通过）
5. 结论：
   - 本次修复引入点（P0-A/P0-B）在现有基线下回归通过；
   - 当前阻断全绿的是仓库既有基线问题，未由本次补丁引入。

## 8. Antigravity 报告复核结论（独立判断）

目标文档：`chatgptrest_issue_recurrence_deep_analysis.md`

1. 同意：
   - `F1` 为最高优先级代码缺陷，且已进入修复执行
   - `F2`（stalled fail-open 语义缺口）成立
   - `F3`（外部取消策略误伤）成立
2. 需修正表述：
   - `needs_followup/blocked` 不是 single-flight 当前实现的直接锁定条件（single-flight 主要看 queued/in_progress）
   - “cancel 无审计”表述过重；事件链已有 `requested_by/headers/reason`，问题在于策略治理而非数据缺失
3. 补充：
   - stateless MCP 下不应默认依赖 background wait，这一运行边界是链路稳定性的关键前提

## 9. 关联报告复核（补充）

- 复核文档：`/home/yuanhaizhou/.gemini/antigravity/brain/dcc9490f-232b-4b45-a019-279f879cb903/chatgptrest_issue_recurrence_deep_analysis.md`
- 独立判断：
  1. 报告主结论方向正确：优先修复 export 覆盖与 completion guard fail-open。
  2. 运行侧需明确 stateless MCP 与 background wait 的边界，避免“看似 in_progress、实则无有效 watcher”。
  3. 外部 cancel 需要治理策略（保护窗 + 强制理由 + trace 透传），否则继续复发。

## 10. `88a2a88` Review 合并记录（2026-02-24）

来源：`/home/yuanhaizhou/.gemini/antigravity/brain/dcc9490f-232b-4b45-a019-279f879cb903/review_88a2a88_walkthrough.md`

1. 已采纳：`wait_no_progress` guard 异常审计补齐
   - 在 worker 的 `timeout_decision` 评估分支中，`except Exception` 不再仅静默回落；
   - 新增事件：`wait_no_progress_guard_eval_failed`（DB + artifacts）；
   - payload 含：`reason=guard_eval_exception`、`error_type`、`error`、`phase=wait`。
2. 已补测试：`test_wait_no_progress_guard_exception_is_audited`
   - 人为注入 `_wait_no_progress_timeout_decision` 异常；
   - 断言 job 继续按 fail-open 路径留在 `in_progress/wait`；
   - 断言审计事件 `wait_no_progress_guard_eval_failed` 已落盘。
3. 保留观察（暂不改行为）：
   - `_looks_like_tool_payload_answer` 目前是“保守匹配”（`search_query` + `response_length` 双条件）；
   - 该策略本轮保持不变，以降低误报；后续按线上样本再决定是否放宽。
