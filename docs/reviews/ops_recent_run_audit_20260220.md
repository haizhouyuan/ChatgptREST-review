# ChatgptREST 近期运行复盘（2026-02-20）

> 更新（2026-02-21）：本报告中提到的两项未完成项已落地：
> 1) `chatgptrest-monitor-12h` 已固化为 systemd `service+timer`；
> 2) Client Issue 闭环新增 guardian TTL 自动收口。
> 详见：`docs/reviews/maintenance_gap_closure_20260221.md`。

## 1. 范围与数据源
- 复盘窗口：`2026-02-13 23:29:20` 至 `2026-02-20 23:42:28`（近 7 天）。
- 代码变更分界：`d0536d77111c`（`2026-02-19 16:06:01 +0800`，Gemini selector/import-code fail-open 修复）。
- 数据来源：
  - `state/jobdb.sqlite3`
  - `GET /v1/ops/status`、`GET /v1/ops/incidents?limit=200`
  - systemd/journal（`chatgptrest-*` 服务）
  - 作业证据目录 `artifacts/jobs/<job_id>/`

## 2. 结论摘要（TL;DR）
1. 当前核心链路可用：ChatGPT Pro 与 Gemini 均可产出结果；你刚才关注的 Pro 复审任务已恢复完成。
2. Gemini selector/import-code 问题在 `d0536d7` 后未再出现同类 `error`（前 37 次，后 0 次）。
3. 自动修复体系在“基础设施瞬时故障”上有效（大量 cooldown 可恢复），但对“外部前置条件问题”（Cloudflare、人机验证、第三方登录、Drive 配额）只能诊断，不能闭环。
4. 当前主要遗留风险不是“Pro 不可用”，而是：
   - 少量长尾 `in_progress/cooldown` 老任务拖尾
   - incidents 的“自动闭环”不足（部分已修复签名仍保持 open）
   - `monitor-12h` 为历史 failed transient unit，未形成稳定周期化观测

## 3. 运行统计（近 7 天）

### 3.1 总体状态
- 总作业数：`768`
- `completed=693`，`error=44`，`canceled=15`，`needs_followup=11`，`blocked=2`，`cooldown=1`，`in_progress=2`

### 3.2 分 Kind 统计
| kind | total | completed | completed_rate | error | nonterminal(cooldown/blocked/needs_followup/in_progress) | canceled |
|---|---:|---:|---:|---:|---:|---:|
| `repair.check` | 251 | 251 | 100.0% | 0 | 0 | 0 |
| `chatgpt_web.ask` | 237 | 211 | 89.0% | 16 | 3 | 7 |
| `gemini_web.ask` | 166 | 132 | 79.5% | 22 | 7 | 5 |
| `repair.autofix` | 102 | 99 | 97.1% | 0 | 0 | 3 |
| `qwen_web.ask` | 10 | 0 | 0.0% | 4 | 6 | 0 |

### 3.3 主要错误类型（近 7 天，按次数）
- `gemini_web.ask: MaxAttemptsExceeded` ×9（主要为 `ERR_CONNECTION_CLOSED`/CDP不可达）
- `chatgpt_web.ask: UnboundLocalError` ×7（历史回归，后续版本已修复）
- `chatgpt_web.ask: AttributeError` ×6（历史）
- `qwen_web.ask: RuntimeError` ×4（主要登录态）
- `gemini_web.ask: GeminiModeSelectorNotFound` ×3（已修）
- `gemini_web.ask: GeminiProModeNotFound` ×2（已修）

## 4. 代码改动后运行效果（`d0536d7` 之后）

### 4.1 分界后作业统计
`created_at >= 2026-02-19 16:06:01 +0800`
- `chatgpt_web.ask`: `completed=24`
- `gemini_web.ask`: `completed=13`, `in_progress=1`, `cooldown=1`, `canceled=1`
- `repair.check`: `completed=41`
- `repair.autofix`: `completed=7`
- `error=0`（分界后无 `status=error`）

### 4.2 selector/import-code 问题对比
- 对比指标（Gemini mode/import 相关 error）：
  - **before**: `37`
  - **after**: `0`
- 结论：修复生效，线上已显著收敛。

## 5. 你刚才关心的 Pro 失败问题（即时处置结果）

### 5.1 现象判断
- 触发原因是基础设施瞬时故障（`connection refused`/`blocked: network`），不是评审内容失败。

### 5.2 已恢复任务
- `a3fb15c8fa42489fb08c1b822cefb8d8`：`completed`
  - `artifacts/jobs/a3fb15c8fa42489fb08c1b822cefb8d8/answer.md`
- `24e40af2711643b5a40e9afc283c285e`：`completed`
  - `artifacts/jobs/24e40af2711643b5a40e9afc283c285e/answer.md`

### 5.3 Pro 可用性烟雾验证
- `209fe2cd983e46449594890fecb76d76`（`pro_extended`）=> `completed`，返回 `PRO_SMOKE_OK`

## 6. 自动修复/维护程序健康度评估

### 6.1 服务面
- 当前核心服务均 `active(running)`：
  - `chatgptrest-chrome.service`
  - `chatgptrest-driver.service`
  - `chatgptrest-api.service`
  - `chatgptrest-worker-send.service`
  - `chatgptrest-worker-wait.service`
  - `chatgptrest-worker-repair.service`
  - `chatgptrest-maint-daemon.service`
- `chatgptrest-mihomo-delay.timer` 正常触发（每 5 分钟）。
- `chatgptrest-monitor-12h.service` 为历史 transient failed（非核心链路，但说明监控任务管理不够整洁）。

### 6.2 repair 作业表现
- 近 24h：
  - `repair.check completed=32`
  - `repair.autofix completed=7`
- 近 7d：
  - `repair.check completed=251`
  - `repair.autofix completed=99`, `canceled=3`
- 全量累计：
  - `repair.check completed=304`
  - `repair.autofix completed=259`, `canceled=5`

### 6.3 incidents 闭环情况（最近 200 条）
- `resolved=149`, `open=51`
- open 中：
  - `repair_job_id` 存在：`51/51`
  - `codex_last_ok=true`：`48/51`
- 说明：诊断/修复链路“有动作”，但并不等于“根因已消失”。

## 7. 异常项目汇总（重点）

### 7.1 仍在 open 的高频问题簇
1. 外部前置条件类（自动化无法完全闭环）
- Cloudflare challenge（需要人工验证）
- Qwen 登录态缺失（`_QwenNotLoggedInError`）
- Google Drive 配额限制（`DriveUploadNotReady` + 403 quota exceeded）

2. 基础设施瞬时抖动类
- `transport error: [Errno 111] Connection refused`
- `CDP connect failed / Target closed / Target crashed`
- 现象上常表现为 `cooldown -> requeue -> 恢复`，但会拉长任务时延。

3. 历史代码缺陷遗留签名（已修但 incident 未自动关闭）
- `GeminiModeSelectorNotFound`
- `GeminiProModeNotFound`
- `GeminiModeSwitchDidNotApply`
- `Gemini tool not found: (导入代码|Import code)`

### 7.2 当前“异常拖尾”任务
1. `7a519611920a43db84e00c59c5866b73`（`chatgpt_web.ask`）
- 年龄约 `72h+`，长期 `wait_requeued`
- `conversation_url` 退化为 `https://chatgpt.com/`（无 thread id）
- 风险：无限等待，既不完成也不失败，吞噬 worker 关注度

2. `1fbed5c2571f4af4906ad17aa6474b32` / `52b945cec8a54d50be99c7b4d4c59e8c`（`gemini_web.ask`）
- 近日反复在 `in_progress/cooldown` 之间切换
- 典型原因：瞬时网络/CDP 抖动

## 8. 为什么“自动修复有时没起作用”

1. 根因不在系统内（无法自动化消除）
- Cloudflare 人机验证、第三方登录、Drive 配额都需要外部条件或人工参与。

2. 现有修复偏“诊断+重试”，缺少“终止条件治理”
- 对 `conversation_url` 退化且长期无进展的 wait 任务，缺少硬超时与自动转 `needs_followup/error`。

3. incident 生命周期管理不完整
- 即使代码已修、后续任务成功，历史 incident 仍可保持 open，影响态势感知。

4. Codex 分析器偶发失败
- 3 个 open incident 出现 `codex_last_ok=false`：
  - 2 个是 codex 执行失败（rc=1）
  - 1 个是输出解析失败（missing/invalid out_json）

## 9. 维护结论
- 这轮维护从“救火”角度是有效的：
  - ChatGPT Pro 当前可用，关键 Pro 复审任务已完成。
  - Gemini selector/import-code 核心回归已消除（改后无同类 error）。
- 但从“长期稳定性”角度还缺 3 个闭环：
  - 非终态任务自动收敛
  - incident 自动闭环
  - 外部依赖故障的策略分流（人机验证/登录/配额）

## 10. 建议动作（按优先级）

### P0（本周内）
1. 对 wait 阶段增加“无进展硬超时”
- 条件示例：`conversation_url` 无 thread id + 连续 N 次 `wait_requeued` + 无 assistant 增量
- 动作：转 `needs_followup` 并附上可执行指引，避免无限悬挂

2. incident 自动收敛规则
- 当签名在窗口内无新命中且关联 job 已终态，自动从 open -> resolved

3. 把 Drive 配额类错误标为“长退避”
- 避免短周期重试打爆配额/队列

### P1（1-2 周）
1. 为 `chatgptrest-monitor-12h` 建立稳定 timer/service（替换 transient failed）
2. Codex SRE 分析输出增加“弱结构化兜底解析”，避免 out_json 失败即整单失败
3. 将 `repair.check` 结果标准化写入 `run_meta`（便于 dashboard 统计）

### P2（持续）
1. 做一个“运行态看板”文档/脚本：
- 7天成功率、非终态年龄分布、top error、open incidents 趋势
2. 对 Qwen/Gemini/ChatGPT 的“外部前置条件”统一成 checklist 与自动提示模板

---

## 附：本次复盘关键证据（job_id）
- Pro 恢复完成：
  - `a3fb15c8fa42489fb08c1b822cefb8d8`
  - `24e40af2711643b5a40e9afc283c285e`
- Pro 烟雾验证：
  - `209fe2cd983e46449594890fecb76d76`
- Gemini selector/import-code 历史异常样本：
  - `f3628061a2cd4925a4e00ff73f253ae8`
  - `5c701a7103ac41338391b2e495033f00`
  - `e3ce9a926db841269934bf8e61b1feaf`
  - `adb803a9466b4d1baf5c6dc295f2d7e4`
- 当前拖尾样本：
  - `7a519611920a43db84e00c59c5866b73`
  - `1fbed5c2571f4af4906ad17aa6474b32`
  - `52b945cec8a54d50be99c7b4d4c59e8c`
