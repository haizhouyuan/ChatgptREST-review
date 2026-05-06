# 2026-04-12 same_session_repair WebRetryBudgetExceeded autofix resume walkthrough v1

## 背景

HAT 的 GP / advisor-agent 深度调研在 MCP 使用过程中出现“长时间没有最终答案”的现象。现场会话表面上看像是需要等待更久，但实际不是单纯长耗时，而是同会话修复链没有把 `WebRetryBudgetExceeded` 正确路由到 runtime 修复。

## 现场证据

真实会话：

- `agent_sess_7646e34246054983`

相关 ask jobs：

- `cf5d4c43c77944b4942b9a0a60e4de21`
- `e837f9fe19274c77993db6a29fe05ac7`

两次 ask job 都落到：

- `status=needs_followup`
- `next_action.type=same_session_repair`
- `last_error_type=WebRetryBudgetExceeded`

随后手工提交的 repair job：

- `a866e08bbaff4788920cf746e632d134`

该 repair job 成功完成，且 `repair_autofix_report.json` 说明 heuristic runtime recovery 已成功执行（`capture_ui + refresh`）。

但 public advisor session 仍停在：

- `needs_followup`
- `same_session_repair`
- `WebRetryBudgetExceeded`

这证明问题不在“repair.autofix 不会修”，而在“same-session caller 没有先触发 repair.autofix，再继续同一会话”。

## 根因

共有两层缺口：

1. `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
   - 只会对 `same_session_repair` 做“等待后 blind continue”
   - 没有对 `WebRetryBudgetExceeded` 先提交低风险 `repair.autofix`
   - 并且默认只在存在 `retry_after` / `verification_pending` 时才认为可 auto-resume，导致 `WebRetryBudgetExceeded` 即使有 target `job_id` 也可能不进入恢复链

2. `openclaw_extensions/openmind-advisor/index.ts`
   - 插件也只有 bounded same-session continue
   - 遇到 `WebRetryBudgetExceeded` 不会先做 runtime 修复

3. `chatgptrest/worker/worker.py`
   - worker-side auto-autofix 对 `needs_followup` 只覆盖：
     - `WaitNoProgressTimeout`
     - `WaitNoThreadUrlTimeout`
     - `ProInstantAnswerNeedsRegenerate`
   - 没覆盖 `WebRetryBudgetExceeded`

## 修复

### 1. wrapper：在 same-session 继续前先做 runtime repair

文件：

- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`

新增能力：

- 从 `next_action` 中提取：
  - `error_type`
  - `job_id`
  - `conversation_url`
- 当 `error_type=WebRetryBudgetExceeded` 时：
  - 读取 `CHATGPTREST_OPS_TOKEN`
  - 提交 `kind=repair.autofix`
  - 使用低风险 allowlist：
    - `capture_ui`
    - `clear_blocked`
    - `refresh`
  - 等待 repair job 到 terminal
  - 再继续原 `session_id`

同时放宽 `_should_auto_same_session_repair(...)`：

- `WebRetryBudgetExceeded` 只要存在目标 `job_id` 就允许进入恢复链
- 不再错误依赖 `retry_after_seconds > 0`

### 2. OpenClaw plugin：同样先修再续

文件：

- `openclaw_extensions/openmind-advisor/index.ts`

新增逻辑：

- 检测 `same_session_repair + WebRetryBudgetExceeded`
- 用 `CHATGPTREST_OPS_TOKEN` 提交同样的低风险 `repair.autofix`
- 等待 terminal
- 将 repair 结果挂到 payload
- 然后继续原会话

这样 OpenClaw / Feishu / HAT 走 advisor plugin 时，不再只是盲目 continue。

### 3. worker：把 WebRetryBudgetExceeded 纳入 auto-autofix

文件：

- `chatgptrest/worker/worker.py`

更新：

- `_should_worker_auto_autofix(...)` 现在对 `status=needs_followup` 也接受 `WebRetryBudgetExceeded`
- `_worker_autofix_allow_actions(...)` 给这类问题的默认 allowlist：
  - `clear_blocked`
  - `refresh`
  - `restart_driver`

## 验证

通过的聚焦测试：

- `pytest -q tests/test_skill_chatgptrest_call.py -k 'same_session_repair or web_retry_budget'`
- `./.venv/bin/pytest -q tests/test_worker_auto_autofix_submit.py -k 'web_retry_budget or wait_timeout'`
- `pytest -q tests/test_openclaw_cognitive_plugins.py`

新增覆盖点：

- wrapper 接受 `WebRetryBudgetExceeded` 进入 same-session repair
- wrapper 在 runtime repair 后继续同一 session
- worker 对 `needs_followup/WebRetryBudgetExceeded` 自动提交 `repair.autofix`
- OpenClaw plugin 源码层包含 runtime repair 分支

## 运维含义

以后再看到：

- `status=needs_followup`
- `next_action.type=same_session_repair`
- `last_error_type=WebRetryBudgetExceeded`

不要再把它当成“只要等更久就好”。

正确口径是：

- 这是浏览器可见重试预算已耗尽后的 fail-closed
- 必须先做低风险 runtime 修复
- 然后继续同一会话

## 未做的事

- 本文只修了 runtime repair / same-session resume 链
- 没有提高 retry budget
- 没有绕过 MCP / advisor / OpenClaw 合同
- 没有把长等待场景改成“永远同步阻塞”

## 结论

HAT 的 GP 出问题，不是因为“深度调研太慢所以要无限等”，而是因为 `WebRetryBudgetExceeded` 后的恢复链缺了一步“先 repair.autofix，再 continue 同一会话”。本次修复把这一步补到了 wrapper、OpenClaw plugin、worker 三层。
