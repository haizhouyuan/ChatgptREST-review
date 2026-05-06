# ChatgptREST Oncall 自修复 72h 复盘与补救执行报告（2026-02-24）

## 1. 结论摘要
- 本次补救已完成并验证：oncall 核心链路从 `ui_canary_stale` 告警状态恢复到 `ok`。
- `maint-daemon` 已从 `disabled/inactive` 恢复为 `enabled/active`。
- `orch-doctor --strict` 与 `guardian` 手工触发均成功，最新报告均 `needs_attention=false`。
- 两个正式 ChatGPT 双 DR 原任务（`cd1b8afe...`、`e586b91b...`）本体没有答案文件，确认为外部 cancel；已通过后续补救链路回收答案产物。

## 2. 复盘范围与证据
- 时间窗口：最近 72 小时（报告生成时点向前滚动）。
- 主证据文件：
  - `artifacts/monitor/reports/20260224_oncall_self_heal/retro_metrics_72h.json`
  - `artifacts/monitor/reports/20260224_oncall_self_heal/retro_metrics_72h_extended.json`
  - `artifacts/monitor/reports/20260224_oncall_self_heal/verification_post_fix_20260224.json`
  - `artifacts/monitor/recovery_dr_cancel_20260224_013202Z.md`

## 3. 72h 异常与处置数据

### 3.1 事件规模
- incidents（72h 内创建）：`22`
  - `open=16`, `resolved=6`
- remediation actions（72h 内创建）：`86`
  - `completed=83`, `failed=3`
- repair jobs（72h 内创建）：`120`
  - `repair.check=85`, `repair.autofix=35`
  - `completed=119`, `canceled=1`
- client issues（72h 内创建）：`15`
  - `open=8`, `closed=4`, `mitigated=3`
  - `worker_auto` 来源 `9` 条（`open=8`）

### 3.2 处置效率
- incident 首次 action 延迟（72h）：
  - `min=0.575s`, `avg=230.175s`, `max=683.386s`
- 已 resolved incident 生命周期：
  - `min=2507.835s`, `avg=5799.760s`, `max=13495.909s`

### 3.3 失败动作
- 失败动作共 `3`，均为 `infra_heal_restart_driver`，错误均为 `restart_driver failed`。
- 失败动作对应 incident 主要集中在 ChatGPT CDP/driver 恢复阶段。

### 3.4 cancel 事件统计
- `cancel_requested`（72h）：`95`
- `x_client_name=chatgptrest-mcp`：`92`
- 2026-02-24T01:32:02Z 附近事件确认包含：
  - `cd1b8afe36d94f01a8b7f503ddf1788f`
  - `e586b91b3ab44126a631d5b9b1e137c5`
  - 事件链：`cancel_requested -> status_changed(in_progress -> canceled)`

## 4. 指定问题追踪结论

### 4.1 两个正式 ChatGPT 双 DR 任务
- `cd1b8afe36d94f01a8b7f503ddf1788f`
  - `status=canceled`, `phase=send`
  - `answer_path/conversation_export_path = null`
- `e586b91b3ab44126a631d5b9b1e137c5`
  - `status=canceled`, `phase=send`
  - `answer_path/conversation_export_path = null`
- 结论：原任务本体没有答案文件，不能直接“回收原 job answer”。

### 4.2 补救回收结果（已落盘）
- `ef77dc8bff9b4f69864ccf18755ea591`
  - `status=completed`
  - `answer_chars=25345`
  - `conversation_export_chars=793090`
- `3b75093b556640b58dd0e12385b76ada`
  - `status=canceled`
  - 无 `answer.md`，但存在 `conversation.json`（`conversation_export_chars=479603`）
- 补救记录见：`artifacts/monitor/recovery_dr_cancel_20260224_013202Z.md`

### 4.3 Gemini DR 长轮询问题链
- `9f617a18ea0c40ee97e6d10fb06e73fd`：`needs_followup`
- `fda93b445c50447dae24a2be9acb3665`：`completed`（短答）
- `829c0a80831a486f8cc02c2bde1e6f52`：`canceled`（wait 长轮询收口取消）
- 结论：该链路出现“研究阶段有内容但 wait 收敛不稳”的典型问题，当前策略是保留阶段快照并取消收口防队列挂死。

## 5. 本次执行的补救改动

### 5.1 配置修复（外部配置）
- `/home/yuanhaizhou/.config/systemd/user/chatgptrest-maint-daemon.service`
  - 删除硬编码：`CHATGPT_CDP_URL=http://127.0.0.1:9222`
  - 原因：与当前 `CHROME_DEBUG_PORT=9226` 失配，导致 maint 侧探测可能打错端口。
- `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env`
  - 新增：`CHATGPTREST_UI_CANARY_PROVIDERS=chatgpt,gemini`
  - 原因：Qwen 专用 CDP 非常驻，纳入 oncall canary 会导致持续假阳性。

### 5.2 运行动作
- `systemctl --user daemon-reload`
- `systemctl --user enable --now chatgptrest-maint-daemon.service`
- `systemctl --user restart chatgptrest-maint-daemon.service`
- 手工刷新一次 `ui_canary/latest.json`（chatgpt + gemini self_check）
- 手工触发 `chatgptrest-orch-doctor.service` 与 `chatgptrest-guardian.service`

## 6. 修复后验证
- 服务态：
  - API/driver/mcp/send/wait/repair/maint-daemon 均 `active`
  - orch-doctor.timer / guardian.timer 均 `enabled + active`
- 端口态：`9226/18701/18711/18712` 全部可连通。
- canary：
  - `artifacts/monitor/ui_canary/latest.json`
  - `ts=2026-02-24T04:04:15Z`
  - providers=`chatgpt,gemini` 且均 `ok=true`
- orch 报告：`artifacts/monitor/openclaw_orch/latest_report.json`
  - `ok=true`, `needs_attention=false`
- guardian 报告：`artifacts/monitor/openclaw_guardian/latest_report.json`
  - `ok=true`, `needs_attention=false`

## 7. 测试结果
- `./.venv/bin/pytest -q tests/test_cli_chatgptrestctl.py`
  - 结果：PASS（8/8）
- `./.venv/bin/pytest -q`
  - 结果：FAIL（1 个已知失败）
  - 失败用例：
    - `tests/test_driver_singleton_lock_guard.py::test_maint_start_driver_if_down_skips_script_fallback_when_systemd_loaded`
  - 失败原因：
    - 测试 mock 未覆盖新增命令 `systemctl --user reset-failed chatgptrest-driver.service`
  - 输出归档：
    - `artifacts/monitor/reports/20260224_oncall_self_heal/pytest_full_20260224.txt`

## 8. 对“CLIENT_INSTANCE / X-Request-ID”的结论
- 72h 内 `cancel_requested` 存在大量历史事件缺失 `x_client_instance/x_request_id`（旧流量）。
- 近期样本已出现完整头：
  - `x_client_instance=YogaS2-pid3399683`
  - `x_request_id=chatgptrest-mcp-...`
- 结论：头补齐在新流量已生效，但历史数据不可追补。

## 9. 仍需跟进的风险
- 全量 pytest 仍有 1 个失败（测试基线未全绿）。
- open incidents 仍有存量（多为历史遗留、last_seen 已超过 60h），需继续清理闭环。
- 若未来需要把 qwen 纳入 oncall，可在 qwen CDP 常驻后再恢复 `ui_canary` provider。

## 10. 本次交付清单
- 复盘报告：`docs/reviews/chatgptrest_oncall_self_heal_retro_20260224.md`
- 执行日志：`artifacts/monitor/reports/20260224_oncall_self_heal/execution_log.md`
- 指标与验证：
  - `artifacts/monitor/reports/20260224_oncall_self_heal/retro_metrics_72h.json`
  - `artifacts/monitor/reports/20260224_oncall_self_heal/retro_metrics_72h_extended.json`
  - `artifacts/monitor/reports/20260224_oncall_self_heal/verification_post_fix_20260224.json`
  - `artifacts/monitor/reports/20260224_oncall_self_heal/pytest_full_20260224.txt`
