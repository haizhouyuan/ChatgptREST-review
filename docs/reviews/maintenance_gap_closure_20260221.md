# ChatgptREST 查漏补缺与未完任务收口（2026-02-21）

## 1. 本轮目标
- 补齐会话内遗留的文档/skill/AGENTS 同步缺口。
- 完成“Client Issue 闭环自动化”与“monitor-12h 固化”两项未落地项。
- 做一次可复现验证并记录结果。

## 2. 本轮落地改动

### 2.1 Client Issue 自动收口（guardian）
- `ops/openclaw_guardian_run.py`
  - 新增 `client_issue_sweep`：按 TTL 扫描 `worker_auto` 的 `open/in_progress`，自动更新为 `mitigated`。
  - 新增参数（支持 env 覆盖）：
    - `CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_HOURS`（默认 `72`）
    - `CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_MAX`（默认 `50`）
    - `CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_SOURCE`（默认 `worker_auto`）
    - `CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_STATUSES`（默认 `open,in_progress`）
    - `CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_ACTOR`（默认 `openclaw_guardian`）
- 测试：`tests/test_openclaw_guardian_issue_sweep.py`

### 2.2 monitor-12h 固化（systemd + 脚本）
- 新增脚本：`ops/run_monitor_12h.sh`
  - 固定执行 12h 监控窗口并产出 summary。
- 新增 systemd 单元：
  - `ops/systemd/chatgptrest-monitor-12h.service`
  - `ops/systemd/chatgptrest-monitor-12h.timer`
- 安装脚本更新：
  - `ops/systemd/install_user_units.sh` 增加 monitor timer 提示。

### 2.3 文档与入口同步
- `docs/contract_v1.md`
  - 补 `params.purpose`、Pro trivial/smoke guard 与 override 参数说明。
- `docs/runbook.md`
  - Client Issue 自动收口链路、guardian 参数、monitor-12h timer 启用方式。
  - 补双 Codex Home 的 `chatgptrest-call` skill 安装路径说明。
- `AGENTS.md`
  - 增加 `run_monitor_12h.sh` 与 client issue 自动收口原则。
- `docs/client_projects_registry.md`
  - 闭环口径更新为“自动登记+自动修复+TTL 自动收口”。
- `docs/issues_registry.yaml`
  - 新增 `ISSUE-0013`（stale open issues auto-mitigate）。
- `docs/handoff_chatgptrest_history.md`
  - 新增第 50 条历史记录（本次闭环）。
- `docs/README.md`
  - 文档索引增加 skill 入口。
- `skills-src/chatgptrest-call/SKILL.md`
  - 增补双 Home 安装说明。

## 3. 验证结果

### 3.1 测试
- 命令：
  - `./.venv/bin/pytest -q tests/test_openclaw_guardian_issue_sweep.py tests/test_cli_chatgptrestctl.py tests/test_block_smoketest_prefix.py tests/test_gemini_deep_think_overloaded.py tests/test_gemini_deep_think_retry_policy.py`
- 结果：`22 passed`

### 3.2 脚本/语法
- `python3 -m py_compile ops/openclaw_guardian_run.py chatgptrest/cli.py skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
- `bash -n ops/run_monitor_12h.sh ops/systemd/install_user_units.sh`

### 3.3 运行态
- `ops status`: `ok=true`
- `service status --include-optional`: `ok=true`
- timers:
  - `chatgptrest-guardian.timer`: `active/waiting`
  - `chatgptrest-monitor-12h.timer`: `active/waiting`

### 3.4 自动收口实测
- Dry-run（无状态修改）：
  - 命令：`./.venv/bin/python ops/openclaw_guardian_run.py --no-autofix --no-notify`
  - 结果：`enabled=false`，`reason=disabled_by_no_autofix`
- Active sweep：
  - 命令：`./.venv/bin/python ops/openclaw_guardian_run.py --no-notify`
  - 首轮执行曾自动收口 `updated=7`（stale worker_auto issues）
  - 当前再次执行结果：`listed=10`，`eligible=0`，`updated=0`，`failures=[]`
- 证据：`artifacts/monitor/openclaw_guardian/latest_report.json`

## 4. 备注
- `chatgptrest-monitor-12h.timer` 默认每日触发一次 12h 监控窗口（`00:05`）。
- 若不希望自动收口，设置：
  - `CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_HOURS=0`
