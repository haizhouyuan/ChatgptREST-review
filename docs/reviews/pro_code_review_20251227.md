# ChatgptREST — Pro 代码审查尝试记录（2025-12-27）

本文件用于“落盘”记录：在 ChatGPT Pro 上做 ChatgptREST 代码审查时遇到的失败模式、证据路径与可执行的修复方向，便于后续维护/排障与改进 executor/工作流。

## 目标

- 让 Pro 对 ChatgptREST 做严格 code review，并输出：
  1) 结论摘要（最担心的 3–5 点）
  2) P0/P1/P2 清单（影响/触发条件/修复）
  3) 具体补丁建议（按文件路径分组，尽量给可粘贴 diff/片段）
  4) pytest 测试建议 + 验证步骤

## 结论（初次未达成；后续已达成）

后续我们已拿到 Pro 的完整审查输出并落盘为可长期引用的文档：

- `docs/reviews/pro_code_review_full_20251227_694ff03b.md`

本文件保留“初次失败模式与证据”，方便维护同学排查为什么会出现“看起来同一问题被问了两遍/Pro 说没看到附件”等现象。

本次多次尝试后，Pro 未能稳定产出“基于代码内容”的审查结论，主要失败模式有两类：

1) **忽略附件内容**：即便 `files_count>0`，回复仍停留在“我没看到关键文件内容，请补充文件”。
2) **进入 ‘Pro thinking • Writing code’ 并卡住**：Pro 在 UI 中启动代码执行（读取 `/mnt/data/*.py`），长时间不产出最终自然语言审查；`chatgpt_web_ask` 在 900s 超时后返回 `in_progress`，后续 wait 仍无成文答案。

因此，此次文档“落盘”的重点是证据与改进方向，而非审查结论本身。

## 关键作业与证据

### 1) Pro 要求补充文件（首次）

- Job: `artifacts/jobs/0cfeea6fb35246989227fa6271bc8246`
  - Answer: `artifacts/jobs/0cfeea6fb35246989227fa6271bc8246/answer.md`
  - 内容：Pro 表示无法从 zip/上下文中看到关键文件，要求补充 3 个文件（job_store/state_machine、worker、maint_daemon）。

### 2) 已上传关键文件仍被忽略（复现）

- Job: `artifacts/jobs/436dee25b581493a88b9893fd02630c1`
  - Answer: `artifacts/jobs/436dee25b581493a88b9893fd02630c1/answer.md`
  - Conversation (DOM export): `artifacts/jobs/436dee25b581493a88b9893fd02630c1/conversation.json`
  - 现象：尽管该 job 在 chatgptMCP 侧记录 `files_count=4`，Pro 仍回复“没看到关键文件内容，需要你补充 3 个文件”，与上一条几乎一致。

### 3) 新开会话 + 强制“读到附件确认”后进入 Writing code 并超时

- Job（最终被取消）: `artifacts/jobs/5beec90e8bc5433599115e70b144db17`
  - chatgptMCP ask 超时证据：
    - `../chatgptMCP/artifacts/20251227_005129_ask_timeout_6998.txt`
    - `../chatgptMCP/artifacts/20251227_005129_ask_timeout_6998.html`
    - `../chatgptMCP/artifacts/20251227_005129_ask_timeout_6998.png`
  - 现象：UI 中显示 `Pro thinking • Writing code`，并出现 `Answer now`；Pro 在代码执行环境中用 Python 读取 `/mnt/data/*.py`，但未输出最终审查文本；`chatgpt_web_ask` 在 ~900s 后返回 `in_progress`，后续等待仍无结果，最终取消该 job。

## 建议的改进方向（待实现/纳入下一轮）

1) **Prompt/参数层面：显式禁止 Code Interpreter / Writing code**
   - 在审查类 job 的提示中加入明确约束：不使用任何“写代码/运行代码/工具”，只做静态审查输出。
2) **Executor 健壮性：识别 “Writing code + Answer now” 卡住态**
   - 当 `chatgpt_web_ask` 返回 `in_progress` 且 debug snapshot 文本包含 `Pro thinking • Writing code` / `Answer now` 等标记时：
     - 将 job 标记为 `needs_followup`（或 `cooldown`）并落盘明确 reason（“UI 等待 Answer now”），避免 worker 长时间占用。
     - 证据包中保存对应 snapshot 路径，方便人工介入。
3) **持久化/可观测性：尽早写入 conversation_url**
   - 当前 worker 仅在 executor 返回后才 `set_conversation_url()`，导致 in_progress/timeout 时 DB 中 `conversation_url` 为空（排障困难）。
   - 建议：若 input 已提供 `conversation_url`（或 tool 返回了 conversation_url 但最终未完成），也要尽早落盘。
4) **为“代码审查/大附件”提供专用策略**
   - 对于代码审查类任务，优先使用：
     - 更短的 `timeout_seconds` + 明确“不要进入写代码模式”的系统提示；
     - 或拆分：先让模型只输出 P0 清单，再输出补丁与测试（减少一次性生成压力）。
