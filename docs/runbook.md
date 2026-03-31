# ChatgptREST Ops Runbook

This is an operator-focused checklist for keeping the ChatgptREST stack healthy and for cutover from direct `chatgptMCP` calls.

## Stack & Ports (default)

- Chrome (GUI, logged-in; CDP): `http://127.0.0.1:9222` (or `http://127.0.0.1:${CHROME_DEBUG_PORT}`)
- Qwen Chrome (GUI, logged-in; dedicated CDP, no proxy): `http://127.0.0.1:9335` (optional; disabled in the default single-user baseline unless explicitly enabled)
- ChatgptREST driver MCP server (internal; StreamableHTTP): `http://127.0.0.1:18701/mcp`
- chatgptMCP (external MCP server; legacy fallback): `http://127.0.0.1:<port>/mcp`
  - 注意：**外部 chatgptMCP 不能和内部 driver 共享同一个端口同时运行**。
  - 想切到外部 chatgptMCP：要么停掉内部 driver，要么把其中一个改端口。
- ChatgptREST (REST API): `http://127.0.0.1:18711`
- ChatgptREST public agent MCP adapter (optional): `http://127.0.0.1:18712/mcp`
- ChatgptREST admin MCP adapter (optional, internal only): `http://127.0.0.1:18715/mcp`
- ChatgptREST Dashboard Control Plane (read-only operator UI): `http://127.0.0.1:8787`

Quick health endpoints:
- `GET /healthz`
- `GET /health/runtime-contract`
- `GET /v1/health/runtime-contract`
- `GET /v1/ops/status` (includes `build.git_sha` + `build.git_dirty` for version drift checks, plus `active_incident_families`, `active_open_issues`, `active_issue_families`, `stuck_wait_jobs`, and `ui_canary`-derived attention hints)
- Dashboard app: `GET http://127.0.0.1:8787/healthz`

Runtime contract health:

- `GET /health/runtime-contract` and `GET /v1/health/runtime-contract` are the machine-readable checks for:
  - public MCP service identity
  - allowlist enforcement / allowlisted state
  - runtime contract drift
  - current `completion_contract` / MCP surface versions
- When debugging “MCP can start but first request fails” or allowlist/env drift, prefer these endpoints before running a live ask.

Fresh Codex client entry:
- `docs/codex_fresh_client_quickstart.md` — 给新启动、没有维护背景的 Codex 客户端的最小入口说明

Machine-first repo cognition entry:
- `./.venv/bin/python scripts/chatgptrest_bootstrap.py --task "<task>" --runtime quick`
  - 输出 `bootstrap-v1` JSON，默认给 coding agent 做 cold-start 快照
  - 至少先看：`detected_planes`、`runtime_snapshot`、`task_relevant_symbols`、`change_obligation_validation`、`surface_policy`
- `./.venv/bin/python scripts/check_doc_obligations.py --diff HEAD`
  - 检查当前改动集的 doc obligations、baseline tests、缺失 doc update
- `./.venv/bin/python scripts/chatgptrest_closeout.py --agent codex --status completed --summary "..."`
  - 先跑 doc obligation gate，再代理到 shared closeout script
- `chatgptrestctl` 也暴露了同一套入口：
  - `chatgptrestctl repo bootstrap --task "..."`
  - `chatgptrestctl repo doc-obligations --diff HEAD`
  - `chatgptrestctl repo closeout --agent codex --status completed --summary "..."`

## Skill Market Source Intake

skill platform 当前已经支持受控外部 source intake，但默认仍然是 quarantine-first，不做自动安装。

正式说明：

- `docs/ops/2026-03-29_skill_market_source_intake_guide_v1.md`

常用命令：

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/manage_skill_market_candidates.py list-sources

PYTHONPATH=. ./.venv/bin/python ops/manage_skill_market_candidates.py import-source \
  --source-id curated_github_registry \
  --manifest-uri file:///tmp/skill_market_manifest.json \
  --allow-disabled
```

说明：

- allowlist authority：`ops/policies/skill_market_sources_v1.json`
- `import-source` 只会把外部 skill 候选导入 quarantine candidate store
- 不会自动进入 production bundle/runtime

## Dashboard Control Plane (8787)

目标：

- `:8787` 上的 dashboard 是独立的 read-only control plane
- 不参与 jobs 创建、guardian decision、telemetry ingest 的同步写路径
- 查询路径只打 `Dashboard BFF`，底层依赖 `state/dashboard_control_plane.sqlite3` 这份派生读模型

启动：

```bash
cd /vol1/1000/projects/ChatgptREST
bash ops/start_dashboard.sh
```

systemd：

```bash
cd /vol1/1000/projects/ChatgptREST
bash ops/systemd/install_user_units.sh
systemctl --user enable --now chatgptrest-dashboard.service
systemctl --user status chatgptrest-dashboard.service --no-pager
```

关键环境变量：

- `CHATGPTREST_DASHBOARD_HOST`，默认 `127.0.0.1`
- `CHATGPTREST_DASHBOARD_PORT`，默认 `8787`
- `CHATGPTREST_DASHBOARD_DB_PATH`，默认 `state/dashboard_control_plane.sqlite3`
- `CHATGPTREST_DASHBOARD_REFRESH_INTERVAL_SECONDS`，默认 `15`
- `CHATGPTREST_DASHBOARD_BOOTSTRAP_ON_READ`，默认开启

关键页面：

- `/v2/dashboard/overview`
- `/v2/dashboard/runs`
- `/v2/dashboard/runtime`
- `/v2/dashboard/identity`
- `/v2/dashboard/incidents`
- `/v2/dashboard/cognitive`

排障：

- 若页面空白，先看 `curl -fsS http://127.0.0.1:8787/healthz | jq .`
- 若 health 正常但数据为旧，查看 `refresh_status / refreshed_at / root_count`
- 若 `root_count=0`，优先检查 `CHATGPTREST_DB_PATH`、`CHATGPTREST_CONTROLLER_LANE_DB_PATH`、`OPENMIND_*` 路径是否指向预期数据
- 若只想强制重建读模型，可重启 `chatgptrest-dashboard.service`

## Commercial Space Finbot Lane

商业航天现在有独立的 OpenClaw `finbot` 主题车道，不需要再依赖 `theme-batch-run` 的目录顺序。

单次运行：

```bash
cd /vol1/1000/projects/ChatgptREST
python3 ops/openclaw_finbot.py theme-run --theme-slug commercial_space --format json
```

带 heartbeat / lane status 的单次运行：

```bash
cd /vol1/1000/projects/ChatgptREST
bash ops/run_finbot_commercial_space_lane.sh
```

安装持续运行 timer：

```bash
cd /vol1/1000/projects/ChatgptREST
bash ops/systemd/enable_finbot_commercial_space.sh
```

关键对象：

- lane id: `finbot-commercial-space`
- systemd service: `chatgptrest-finbot-commercial-space.service`
- systemd timer: `chatgptrest-finbot-commercial-space.timer`

常用查看：

```bash
python3 ops/controller_lane_continuity.py status --lane-id finbot-commercial-space
systemctl --user status chatgptrest-finbot-commercial-space.service --no-pager
systemctl --user status chatgptrest-finbot-commercial-space.timer --no-pager
journalctl --user -u chatgptrest-finbot-commercial-space.service -n 50 --no-pager
```

当前主题结果会落到：

- `artifacts/finbot/theme_runs/<date>/commercial_space`
- `artifacts/finbot/inbox/pending/finbot-theme-commercial-space.json`

## Baseline Version

- 当前维护基线：`d0536d7`（2026-02-21）
- 基线核验命令：`curl -fsS http://127.0.0.1:18711/v1/ops/status | jq '.build'`

## Incident-Class Runbook（系统化，给被唤醒的 Codex）

目标：把“单次抢修”升级为“同类问题一次处理、后续可复用”，避免再次出现前台长等待、重复重发、无上限重试。

### 0) 首 5 分钟固定动作（非阻塞）

1. 锁定目标：记录 `job_id / conversation_url / issue_id`，不要换新幂等 key 重发。
2. 先开后台等待，不要前台卡住：
   - MCP: `chatgptrest_job_wait_background_start`
   - 轮询心跳: `chatgptrest_job_wait_background_get`（看 `heartbeat_at/poll_count/last_job_status`）
3. 同步取证（并行）：
   - `/v1/ops/status`
   - `/v1/jobs/<job_id>`
   - `/v1/jobs/<job_id>/events?limit=200`
   - `artifacts/jobs/<job_id>/events.jsonl`
4. 若出现 `Connection refused` / `Unexpected content type: None`，先按 R1/R2 处置，不要先让用户手工登录。

### 1) 故障分型（R 类）

| 类别 | 典型信号 | 根因画像 | 标准动作（按顺序） | 通过标准 |
| --- | --- | --- | --- | --- |
| R1 服务不可达 | `Connection refused` / API 18711 不通 | API/driver/worker 进程掉线或 `start-limit-hit` | `reset-failed` → 重启 `api/driver/worker` → `/healthz` + `/v1/ops/status` 校验 | 新 job 可进入 `queued/in_progress`，旧 job 可继续收口 |
| R2 MCP 握手失败 | `Unexpected content type: None` / `MCP startup incomplete` | CDP 端口被占、singleton lock 冲突、driver 非 systemd 进程漂移 | 校验 `/json/version` 返回 `webSocketDebuggerUrl` → 仅用 systemd 重启 driver → 清理 blocked 状态并 `self_check` | `chatgpt_web`/`codex_apps` MCP 可初始化 |
| R3 wait 卡住 | 网页已有答案，但 job 长期 `in_progress(wait)` | wait 长轮询卡滞、driver 短时抖动、事件未收口 | 保持同一 job 后台 wait；必要时重启 wait worker；触发 `repair.check/autofix`；优先 export 收口 | job 进入 `completed` 且 `answer.md` 落盘 |
| R4 上传阶段循环失败 | `TargetClosedError + set_input_files` 反复，`max_attempts` 被不断拉长 | 上传 UI 漂移/页面关闭导致同类错误重试风暴 | 停止盲目扩容重试，触发粘滞错误护栏（见下方参数）；必要时走 Drive/绝对路径附件 | 不再无限扩展 `max_attempts`；失败可终态化并可追踪 |
| R5 Gemini 模式切换漂移 | `Gemini tool state unknown after toggle` | 选中态 DOM 语义漂移 | 用多信号判定（selected chip/Tools class/placeholder），避免仅依赖 checkbox 属性 | `deep_research`/`pro` 可稳定选中 |
| R6 viewer 黑屏/`error code 15` | noVNC 可达但黑屏、GPU exit 15 burst | viewer Chrome GPU crash | 启用 `viewer_watchdog`，命中阈值做 full restart | viewer 恢复且 watchdog 报 healthy |

### 2) Codex 唤醒执行合同（必须遵守）

- 不允许长时间前台 `job_wait`；默认后台 wait + 心跳轮询。
- 不允许“发一条 OK 测试”；只围绕目标 `job_id` 做收口。
- 不允许在 `phase=send` 有活跃非 repair 作业时重启 driver/chrome。
- 不允许把“登录/CF 验证”当第一结论；必须先完成 R1/R2 诊断。
- 每次处置都要更新：`docs/chatgptREST_issues.md` + Issue Ledger（含证据路径）。

## Client Issue Ledger（登记与闭环）

链路（当前）：
- 自动登记：worker 在 `error/blocked/needs_followup` 等状态会自动上报到 `/v1/issues/report`（`source=worker_auto`）。
- 可选 GitHub 同步：`ops/sync_issue_ledger_to_github.py` 可把 ledger issue 自动投射到 GitHub issue，GitHub 只作为协调/审阅锚点，authoritative state 仍在 Issue Ledger。
- 自动修复：部分 web ask 类故障会自动触发 `repair.autofix`（不发新 prompt）尝试把 job 拉回 `completed`。
- 自动收口（可配置）：`openclaw_guardian` 默认按 TTL 扫描 `worker_auto` 的 `open/in_progress` issue，长时间无复发会自动标记为 `mitigated`（默认 72h）。
- 第二阶段自动结案（可配置）：`openclaw_guardian` 会继续扫描 `mitigated` 的 `worker_auto` issue；若 mitigated 后同客户端/同 `kind` 已有 `3` 次 qualifying success 且无复发，则自动标记为 `closed`。
- 人工收口：仍可手工 `POST /v1/issues/{issue_id}/status` 强制结案。
- `mitigated` / `closed` 现在都会留下结构化证据：
  - `mitigated` 可写入 `Verification`
  - `closed` 会沉淀 `UsageEvidence`
- 图检索仍是 derived view：
  - authoritative state 继续在 `client_issues / client_issue_events / client_issue_verifications / client_issue_usage_evidence`
  - graph 只负责关联、检索、演进解释
- 防误报保护（默认开启）：非 `worker_auto` 上报若引用作业已成功 `completed`（支持 `job_id` 或 `metadata.job_ids`），`/v1/issues/report` 返回 `409 IssueReportJobAlreadyCompleted`。  
  - postmortem 例外：`metadata.allow_resolved_job=true`（或 `force=true`）。
  - 环境变量：`CHATGPTREST_ISSUE_REPORT_REQUIRE_ACTIVE_JOB=0` 可关闭此保护（不建议）。

常用核验：
- 最近自动上报：`curl -fsS 'http://127.0.0.1:18711/v1/issues?source=worker_auto&limit=20' | jq .`
- 查某 issue 事件：`curl -fsS 'http://127.0.0.1:18711/v1/issues/<issue_id>/events?after_id=0&limit=200' | jq .`
- 人工收口（示例）：`curl -fsS -X POST 'http://127.0.0.1:18711/v1/issues/<issue_id>/status' -H 'Content-Type: application/json' -d '{"status":"mitigated","note":"autofix passed + smoke ok"}'`
- 记一条 live verification：`curl -fsS -X POST 'http://127.0.0.1:18711/v1/issues/<issue_id>/verification' -H 'Content-Type: application/json' -d '{"verification_type":"live","status":"passed","note":"live verifier ok","job_id":"<job_id>"}'`
- 查 verification：`curl -fsS 'http://127.0.0.1:18711/v1/issues/<issue_id>/verification?limit=50' | jq .`
- 记一条 qualifying usage：`curl -fsS -X POST 'http://127.0.0.1:18711/v1/issues/<issue_id>/usage' -H 'Content-Type: application/json' -d '{"job_id":"<job_id>","client_name":"chatgptrest-mcp","kind":"gemini_web.ask"}'`
- 查 usage：`curl -fsS 'http://127.0.0.1:18711/v1/issues/<issue_id>/usage?limit=50' | jq .`
- issue graph 查询：`curl -fsS -X POST 'http://127.0.0.1:18711/v1/issues/graph/query' -H 'Content-Type: application/json' -d '{"issue_id":"<issue_id>","neighbor_depth":2}' | jq .`
- issue graph 全量快照：`curl -fsS 'http://127.0.0.1:18711/v1/issues/graph/snapshot?include_closed=true&limit=500' | jq '.summary'`
- 查看 guardian 自动收口结果：`jq '.report.client_issue_sweep' artifacts/monitor/openclaw_guardian/latest_report.json`
- 查看 guardian 自动结案结果：`jq '.report.client_issue_close_sweep' artifacts/monitor/openclaw_guardian/latest_report.json`
- 手工复盘上报（已完成 job）示例：`curl -fsS -X POST http://127.0.0.1:18711/v1/issues/report -H 'Content-Type: application/json' -d '{"project":"homeagent","title":"postmortem","job_id":"<job_id>","metadata":{"allow_resolved_job":true}}'`

Issue Ledger -> GitHub 同步（可选）：

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/sync_issue_ledger_to_github.py \
  --repo haizhouyuan/ChatgptREST \
  --force
```

说明：
- 默认只同步 `source=worker_auto`。
- 自动创建的 GitHub issue 会带分类 labels，并在 ledger `metadata.github_issue` 回写 `number/url/state/synced_status`。
- ledger `closed` 后会自动 comment + close 对应 GitHub issue。
- 需要本机 `gh` 已登录并具备 `repo` scope。

Issue Ledger 开发闭环 runner（窄闭环）：

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/run_issue_ledger_dev_loop.py <issue_id> \
  --repo haizhouyuan/ChatgptREST \
  --run-test-cmd "./.venv/bin/pytest -q tests/test_issue_github_sync.py tests/test_run_issue_ledger_dev_loop.py" \
  --service-start-cmd "systemctl --user restart chatgptrest-api.service" \
  --health-url http://127.0.0.1:18711/healthz
```

它会：
- 确保该 ledger issue 有 GitHub 锚点
- 生成 dev-loop task pack（branch / role / validation / health）
- 可选执行测试命令与服务启动命令
- 对目标 health URL 做最后验收

OpenClaw controller 开发闭环（issue -> implementer lane -> reviewer lane -> PR -> merge -> health）：

```bash
cd /vol1/1000/projects/ChatgptREST

export CHATGPTREST_DEV_LOOP_IMPLEMENTER_CMD_TEMPLATE='cd {worktree_q} && codex exec --skip-git-repo-check --cd {worktree_q} --sandbox workspace-write --output-schema {implementer_schema_q} -o {implementer_output_q} - < {implementer_prompt_q}'
export CHATGPTREST_DEV_LOOP_REVIEWER_CMD_TEMPLATE='claudeminmax -p "$(cat {reviewer_prompt_q})" --output-format json > {reviewer_output_q}'

PYTHONPATH=. ./.venv/bin/python ops/run_issue_ledger_openclaw_controller.py <issue_id> \
  --repo haizhouyuan/ChatgptREST \
  --validation-cmd "./.venv/bin/pytest -q tests/test_issue_dev_controller.py" \
  --service-start-cmd "systemctl --user restart chatgptrest-api.service" \
  --health-url http://127.0.0.1:18711/healthz \
  --merge-pr \
  --close-issue-status mitigated
```

说明：
- controller 会先把 issue 同步成 GitHub issue 锚点，然后创建 worktree 和 role prompt pack。
- implementer / reviewer 都通过 `ops/controller_lane_wrapper.py` 落到 `state/controller_lanes.sqlite3`，所以 lane 心跳、完成态和 telemetry 是统一的。
- controller 不要求 implementer 自己做 `git push` / `gh pr create`；它会在 implementer 输出结构化 JSON 后统一提交、push、开 PR。
- `--merge-pr` 只有在 reviewer 输出 `decision=approve` 时才会执行。
- `--close-issue-status mitigated|closed` 会在 health 通过后回写 Issue Ledger。
- 如果未设置 `CHATGPTREST_DEV_LOOP_IMPLEMENTER_CMD_TEMPLATE`，controller 会直接报错，因为它无法猜测你的 implementer runner。

OpenClaw controller 远程 hcom 模式（issue -> hcom implementer -> hcom reviewer -> PR -> merge -> health）：

```bash
cd /vol1/1000/projects/ChatgptREST

export CHATGPTREST_DEV_LOOP_IMPLEMENTER_HCOM_TARGET='@impl-1'
export CHATGPTREST_DEV_LOOP_REVIEWER_HCOM_TARGET='@review-1'
export CHATGPTREST_DEV_LOOP_HCOM_DIR="$HOME/.hcom"

PYTHONPATH=. ./.venv/bin/python ops/run_issue_ledger_openclaw_controller.py <issue_id> \
  --repo haizhouyuan/ChatgptREST \
  --health-url http://127.0.0.1:18711/healthz \
  --service-start-cmd "systemctl --user restart chatgptrest-api.service" \
  --merge-pr \
  --close-issue-status mitigated
```

远程 hcom 模式说明：
- controller 会先执行 `hcom list --names`，目标不在当前 agent 列表里就直接失败，不会盲发。
- controller 通过 JSON hcom 消息把 `prompt_path / output_path / output_tmp_path / schema_path / worktree_path / task_readme` 发给远程角色；远程角色必须在共享 worktree 内干活，并把最终 JSON 先写到 `output_tmp_path`，再原子 `rename` 到 `output_path`。
- 这条链路不依赖 hcom 回复正文收结果，authoritative result 是共享文件上的结构化 JSON。
- 如果同时设置 command template 和 hcom target，当前实现优先走 command template；要切到 hcom，请把对应 template 留空。
- target 默认是精确匹配；如果你需要前缀通配，显式使用 `@impl-*` 这种形式，不要再用裸前缀。
- `--hcom-dir` / `CHATGPTREST_DEV_LOOP_HCOM_DIR` 会透传成 `HCOM_DIR` 给 `hcom list/send`。
- `--implementer-timeout-seconds` / `--reviewer-timeout-seconds` 控制 controller 等待远程 JSON 输出的超时上限。

常用模板占位符：
- `{worktree_q}` / `{worktree_path}`：实现分支的 worktree 路径
- `{implementer_prompt_q}` / `{reviewer_prompt_q}`：controller 生成的角色提示词文件
- `{implementer_output_q}` / `{reviewer_output_q}`：角色必须写回的 JSON 输出文件
- `{implementer_schema_q}` / `{reviewer_schema_q}`：结构化输出 JSON Schema
- `{task_readme_q}`：controller task pack README
- `{github_issue_url_q}`：Issue Ledger 对应的 GitHub issue URL
- `{pull_request_url_q}`：reviewer 阶段可用的 PR URL（如果 PR 已创建）

### Open Issue List / History Evolution Snapshot

读侧投影脚本：

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/export_issue_views.py
```

默认输出：

- `artifacts/monitor/open_issue_list/latest.json`
- `artifacts/monitor/open_issue_list/latest.md`
- `artifacts/monitor/open_issue_list/history_tail.json`
- `artifacts/monitor/open_issue_list/history_tail.md`
- `artifacts/monitor/issue_graph/latest.json`
- `artifacts/monitor/issue_graph/latest.md`

说明：

- 这些文件是从 `client_issues` 和 `client_issue_events` authoritative ledger 自动导出的视图
- `issue_graph/latest.*` 还会连上 `Verification / UsageEvidence / jobs / incidents / docs`
- 它们是 projection，不改变 issue 状态机
- 用途：
  - 新 Codex / 新客户端快速查看当前 open 问题
  - 和 `/v1/ops/status` 的 `attention_reasons` / family counts 对齐，避免“UI canary 绿了但系统仍有 wait 病灶”这种假健康
  - 复盘最近 `mitigated / closed / reopen` 的演进
  - 为后续 graph / retrieval 层提供稳定中间视图

启用 systemd 定时导出：

```bash
cd /vol1/1000/projects/ChatgptREST
bash ops/systemd/install_user_units.sh
systemctl --user enable --now chatgptrest-issue-views-export.timer
systemctl --user enable --now chatgptrest-issue-graph-export.timer
```

若你要一次性刷新当前 projection（不改 issue 状态、不跑 guardian autofix）：

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/refresh_monitor_projections.py
systemctl --user enable --now chatgptrest-monitor-projection-refresh.timer
```

说明：

- `chatgptrest-monitor-projection-refresh.timer` 只刷新读侧投影：
  - `open_issue_list/latest.*`
  - `openclaw_guardian/latest_report.json`
- 它与 `chatgptrest-issue-views-export.timer` 都会调用 `ops/export_issue_views.py`。
  - 若你已经启用 `chatgptrest-monitor-projection-refresh.timer`，就不要再并开 `chatgptrest-issue-views-export.timer`
  - 否则会出现重复 canonical export，两个 service 同时抢写 `open_issue_list/latest.*`
- 它会以 guardian `--projection-only` 模式运行：
  - 隐含 `--no-autofix`
  - 隐含 `--no-notify`
  - 隐含 `--no-include-orch-report`
- 这个 timer 的职责是“保持最新投影可信”，不是替代原有 guardian patrol。

Issue 生命周期推荐口径：

- `open / in_progress`
  - 问题仍在活跃修复或观察中
- `mitigated`
  - live 验证已经通过
- `closed`
  - `mitigated` 后，真实客户端已成功使用至少 3 次，且没有同类复发

## Agent-first CLI (`chatgptrestctl`)

目的：给 Codex/agent 用的统一入口（机器可解析、稳定退出码、避免散落 curl/systemctl/sqlite 命令）。

安装后可用：

```bash
cd /vol1/1000/projects/ChatgptREST
./.venv/bin/pip install -e .
chatgptrestctl --help
```

默认行为：
- 默认 `--output json`（适合 agent 解析）。
- 单命令单输出（`jobs run` 只输出一个 JSON 对象，含 `submit/job/answer`）。
- 退出码：`0` 成功；`2` CLI/本地操作失败；`3` API 调用失败（含 HTTP 状态）。
- 默认会附带追踪 headers：`X-Client-Name`、`X-Client-Instance`、`X-Request-ID`（可通过环境变量覆盖，建议各调用方显式设置实例名）。

推荐环境变量（所有调用方统一）：
- `CHATGPTREST_CLIENT_NAME`：调用方名称（例如 `chatgptrest-mcp`、`openclaw-orch`）。
- `CHATGPTREST_CLIENT_INSTANCE`：调用方实例（例如 `hostA-codex-w2`）。
- `CHATGPTREST_REQUEST_ID_PREFIX`：请求 ID 前缀（最终仍会自动附加时间戳+随机后缀）。
- `CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST`：可选门禁；设置后仅允许白名单 `X-Client-Name` 执行写操作（例如 `POST /v1/jobs`）。
  - 仅允许 MCP：`CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST=chatgptrest-mcp`
  - 多客户端：`CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST=chatgptrest-mcp,chatgptrestctl,openclaw-advisor`
  - 如果启用了 OpenClaw `openmind-advisor` 插件并要求它直连 `/v3/agent/turn`，必须把 `openclaw-advisor` 放进 allowlist；否则 dynamic replay 会被 `403 client_not_allowed` 阻断。
- `CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST`：可选 `/cancel` 专用门禁；设置后仅允许白名单 `X-Client-Name` 调用 `POST /v1/jobs/{id}/cancel`。
  - 仅允许人工 CLI 取消：`CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST=chatgptrestctl`
  - 示例（允许提交但禁止 MCP 取消）：`CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST=chatgptrest-mcp,chatgptrestctl` + `CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST=chatgptrestctl`
- `CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE`：可选写操作追踪门禁；启用后 `POST /v1/jobs` 与 `/cancel` 必须包含 `X-Client-Instance` + `X-Request-ID`。
- `CHATGPTREST_REQUIRE_CANCEL_REASON`：可选取消原因门禁；启用后 `/cancel` 必须包含 `X-Cancel-Reason`（或 `?reason=`）。
- `CHATGPTREST_CANCEL_REASON_MAX_CHARS`：取消原因最大长度（默认 `240`）。
- `CHATGPTREST_ALLOW_FALLBACK_WHEN_MCP_DOWN`：可选兜底（默认关闭）；开启后仅在 MCP 探活失败时，放行 fallback 白名单客户端。
- `CHATGPTREST_FALLBACK_CLIENT_NAME_ALLOWLIST_WHEN_MCP_DOWN`：fallback 客户端白名单（例如 `chatgptrestctl`）。
- `CHATGPTREST_MCP_PROBE_HOST` / `CHATGPTREST_MCP_PROBE_PORT` / `CHATGPTREST_MCP_PROBE_TIMEOUT_SECONDS`：MCP 探活参数（默认 `127.0.0.1:18712` / `0.2s`）。
- `CHATGPTREST_GEMINI_ANSWER_QUALITY_GUARD`：Gemini 答案质量闸门（默认 `1`，会清理前缀 UI 回显噪声并落事件）。
- `CHATGPTREST_GEMINI_SEMANTIC_CONSISTENCY_GUARD`：严格语义门禁（默认 `0`）；检测到 `next_owner` 语义混用时降级 `needs_followup`。
- `CHATGPTREST_GEMINI_ANSWER_QUALITY_RETRY_AFTER_SECONDS`：质量闸门降级后的重试等待秒数（默认 `180`）。
  - 示例（平时仅 MCP；MCP down 时允许 `chatgptrestctl`）：  
    `CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST=chatgptrest-mcp`  
    `CHATGPTREST_ALLOW_FALLBACK_WHEN_MCP_DOWN=1`  
    `CHATGPTREST_FALLBACK_CLIENT_NAME_ALLOWLIST_WHEN_MCP_DOWN=chatgptrestctl`
  - 建议与追踪门禁同时启用：  
    `CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE=1`  
    `CHATGPTREST_REQUIRE_CANCEL_REASON=1`

常用命令：

```bash
# 提交 + 等待 + 拉答案（最常用）
chatgptrestctl jobs run \
  --kind chatgpt_web.ask \
  --idempotency-key run-$(date +%s) \
  --question "请总结今天的运维状态" \
  --preset pro_extended

# 只等状态
chatgptrestctl jobs wait <job_id> --timeout-seconds 900 --poll-seconds 1.0

# 直接基于已有 job_id 执行 run 收口（跳过 submit）
chatgptrestctl jobs run --expect-job-id <job_id>

# 拉完整 answer/conversation
chatgptrestctl jobs answer <job_id> --all --out /tmp/answer.md
chatgptrestctl jobs conversation <job_id> --all --out /tmp/conversation.json

# advisor 一等入口（plan-only / execute）
chatgptrestctl advisor advise --raw-question "请给出 OpenClaw 接入方案" --context-json '{"project":"openclaw"}'
chatgptrestctl advisor advise --raw-question "执行该方案" --execute --agent-options-json '{"preset":"thinking_heavy"}'

# Issue 台账（自动登记 + 人工收口）
chatgptrestctl issues list --source worker_auto --limit 20
chatgptrestctl issues status <issue_id> --status mitigated --note "autofix passed"

# 运维总览 / 诊断
chatgptrestctl ops status
chatgptrestctl doctor --require-viewer

# 服务与 viewer
chatgptrestctl service restart
chatgptrestctl viewer status
chatgptrestctl viewer url
```

## Codex Skill Entry (`chatgptrest-call`)

面向 “让 agent 代替人工拼命令” 的入口：

- Skill 源码：`/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/`
- Wrapper：`/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
- Agent mode 默认走：public MCP `http://127.0.0.1:18712/mcp`
- `--no-agent --maintenance-legacy-jobs` 才允许走 maintenance-only legacy mode：`/vol1/1000/projects/ChatgptREST/.venv/bin/python -m chatgptrest.cli`

常用调用（机器可解析 JSON）：

```bash
/usr/bin/python3 /vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --question "请给出今日运维盘点" \
  --goal-hint research \
  --execution-profile thinking_heavy \
  --out-summary /tmp/run-summary.json
```

受控 maintenance fallback（仅在确实需要 `/v1/jobs` 行为时）：

```bash
/usr/bin/python3 /vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --no-agent \
  --maintenance-legacy-jobs \
  --provider gemini \
  --preset pro \
  --idempotency-key run-$(date +%s) \
  --question "请导出该次 Gemini 运行的完整 answer 与 conversation" \
  --out-answer /tmp/run-answer.md \
  --out-conversation /tmp/run-conversation.json
```

说明：
- 该 skill 的设计目标是给 Codex/agent 使用，默认单次输出一个 JSON 对象。
- `agent` 默认面已经切到 public MCP，不再默认直打 `/v3/agent/*` REST。
- public MCP canonical tools 现在是：`advisor_agent_turn`、`advisor_agent_status`、`advisor_agent_cancel`、`advisor_agent_wait`。
- public MCP 现在默认是 sessionful Streamable-HTTP。`initialize` 成功后应该返回 `mcp-session-id` header，客户端后续 `tools/call` 也必须带回这个 header；`CHATGPTREST_AGENT_MCP_STATELESS_HTTP=1` 只是显式兼容开关，不是默认部署形态。
- 端口边界固定：`18711` 是 REST API base（`/v1/*`、`/v2/*`、`/v3/*`），`18712` 只给 public MCP，且应写成 `http://127.0.0.1:18712/mcp`。不要把 `18712` 当成 API base。
- Claude Code / Antigravity JSON 配置必须显式写成 `"type": "http"` + `"url": "http://127.0.0.1:18712/mcp"`；不要再用 legacy `serverURL` 字段。
- public MCP 现在会在启动期做 runtime contract 自检：如果 `OPENMIND_API_KEY` / `CHATGPTREST_API_TOKEN` 已配置，但当前 MCP service identity 不在 `CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST` 里，服务会 fail fast 并报 `service_identity_not_allowlisted`，而不是等到第一笔请求才漂移失败。
- `advisor_agent_turn.attachments` 可传单个绝对路径字符串或 `list[string]`；服务端会统一归一化。
- public GitHub repo 给 ChatGPT web 做 review 时，直接给 repo URL 就够了；review repo 只在 private mirror、curated subset、导入规模控制时才是可选增强手段，不是默认必经步骤。
- `task_intake.context` 现在会并回服务端 live context；wrapper 传入的 `legacy_provider/github_repo/enable_import_code/drive_name_fallback` 不再停留在客户端 payload 里。
- repo 自带 `chatgptrest_call.py` wrapper 现在会先做 MCP `initialize` 握手，再带着协商后的 session headers 调 `tools/call`；不要再把 “直接裸打 `tools/call`” 当成可接受客户端实现。
- 若长任务把 `delivery_mode=sync` 自动降成 background/deferred，优先读返回里的 `accepted_for_background`、`recommended_client_action`、`wait_tool`，不要自己猜后续动作。
- wrapper 的 agent mode 对 `code_review/research/report/image`、带附件、带 `github_repo`、或 `enable_import_code=true` 的请求会主动走 `delivery_mode=deferred`，先把 `session_id`/summary 暴露出来，再通过 `advisor_agent_wait` 做前台等待。
- sync agent path 也会在真正进入 `advisor_agent_turn` 阻塞前先刷新 summary 快照，所以客户端不应再看到卡在 `initialized + submission_started=false` 的 bootstrap 假状态。
- wrapper 的 agent mode 现在把 `--job-timeout-seconds/--timeout-seconds` 视为总运行预算，`--request-timeout-seconds` 只是 transport timeout，并默认自动按预算推导；不要再把 `--run-wait-timeout-seconds` 这套 legacy jobs 参数带进 agent mode。
- wrapper 的 agent-mode 错误现在区分 `preflight / initialize_mcp / submit_turn / wait`。只有提交后的 transport timeout / disconnect 才会返回 `still_running_possible=true`；本地参数校验失败不应再提示客户端去查 `advisor_agent_status`。
- agent mode 若显式请求 provider，返回体里的 `provenance.provider_selection` 可审计 requested/final/fallback；legacy mode 的 success/error payload 也会打印 `resolved_runtime`（root/python/command）。
- public MCP 现在会把真实 MCP caller 身份透传进 `task_intake.context.client`，包含 `mcp_client_name/mcp_client_version/mcp_client_id`；排查 session 时不要再把所有 public-MCP caller 都当成同一个 `mcp-agent`。
- public advisor-agent 只收用户可见的 end-to-end turn。像 “只返回 JSON 数组/对象” 的结构化抽取、或 “只回答 sufficient/insufficient” 的充分性 gate，这类 pipeline 内部 microtask 现在会被服务端直接拒绝，错误是 `public_agent_microtask_blocked`。
- 若同一个 MCP caller 在短窗口内重复提交等价的重型 `research/report/code_review` turn，服务端会返回 `duplicate_public_agent_session_in_progress`，并附上已有 `session_id`/`existing_session`/`wait_tool=advisor_agent_wait`；客户端应复用现有 session，不要继续重提。
- public MCP 工具层现在会保留 `/v3/agent/*` 的结构化 4xx body，不再把路由层返回压扁成通用 `HTTPError`。收到 `duplicate_public_agent_session_in_progress` 或 `public_agent_microtask_blocked` 时，客户端应直接读取透传出来的 `existing_session_id`、`wait_tool`、`reason`、`hint`、`recommended_client_action`。
  这条护栏在 caller 预生成新的 `session_id` 时仍然生效；只有命中已有 session 的 resume/patch 才会绕过 duplicate dedupe。
- `gemini_cli` 不是 `gemini_web.ask` 的替代 lane。repo review/imported-code review 要走 `gemini_web.ask` 或其上的 public advisor-agent surface；不能把本地 CLI 登录流当成同一条能力。
- coding agent 不应把 `--no-agent` 当常规入口；legacy mode 现在必须显式带 `--maintenance-legacy-jobs`，并会以 `chatgptrestctl-maint` client name 运行。若它真的落到低层 `/v1/jobs` web ask，还必须同时配置匹配的 HMAC secret env。
- `chatgptrestctl jobs submit --client-name` 现在会同时统一 body/header client identity；不要再假设 body `client.name` 和 `X-Client-Name` 可以分开漂移。
- 若已安装到 `$CODEX_HOME/skills/chatgptrest-call`，重启 Codex 后即可被自动触发。
- 双 Home 场景可同时安装（示例）：
  - `~/.codex2/skills/chatgptrest-call`
  - `~/.home-codex-official/.codex/skills/chatgptrest-call`
- `--purpose` 会透传到 `params.purpose`（建议明确区分 `prod` / `smoke`）。
- 对真正运行在 sandbox 里的 Codex，会遇到 “wrapper/CLI 需要访问 `127.0.0.1:18711`，但当前 shell 不允许 loopback HTTP” 的情况。这个场景下，允许改走已在本仓库登记的 ChatgptREST MCP 路径作为客户端 fallback；不要让客户端自己猜 curl 变体。

## Cold Client Acceptance

目的：

- 验证“一个没有当前维护上下文背景的 Codex 客户端”能否仅靠仓库入口文档把 ChatgptREST 链路跑通。
- 把“维护者知道怎么用”和“真实客户端能发现并正确使用”分开验收。

标准命令：

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/codex_cold_client_smoke.py \
  --provider gemini \
  --preset pro \
  --question "请用两句话解释为什么写自动化测试可以降低回归风险。"
```

脚本行为：

- 启动一个新的 `codex exec`
- 默认保留当前 `CODEX_HOME`，但强制使用一个新的 Codex 会话；这更接近真实客户端环境
- 若当前 `CODEX_HOME` 本身存在损坏配置（例如 `config.toml duplicate key`），runner 会自动退到隔离 `CODEX_HOME` 再跑，避免把宿主机本地 Codex 配置污染误判成 ChatgptREST 客户端链路失败
- 如需更苛刻审计，可加 `--isolate-codex-home`
- 只允许它从仓库入口资料发现调用路径：
  - `AGENTS.md`
  - `docs/runbook.md`
  - `docs/client_projects_registry.md`
  - `skills-src/chatgptrest-call/SKILL.md`
  - 必要的 CLI help
- 要求它真正执行一次人类语义问题的客户端调用，而不是只写方案
- 产物落到 `artifacts/cold_client_smoke/<timestamp>/`

何时必须跑：

- 改动影响客户端入口、headers、allowlist、preset、provider contract、skill 用法、runbook 指引时
- 准备宣称“客户端集成已经修好”之前

通过标准：

- cold Codex 无需维护者补提示即可找到正确路径
- 至少一条真实客户端 job 成功
- 若 sandbox 阻断了 loopback HTTP，允许使用仓库已登记的 ChatgptREST MCP fallback，但必须在结果里明确记录：
  - documented wrapper/CLI 为什么不能直接用
  - fallback 走的是什么入口
  - 哪些文档仍需补齐
- 当前这台机子的 ChatgptREST MCP 仍以 stateless runtime 为主；cold client 若走 MCP fallback，`background wait` 可能不可用并退回前台有界等待。这是运行态限制，不是 prompt 或 provider/preset 用错。
- 结果 JSON 明确记录：
  - 读了哪些文档
  - 执行了哪些命令
  - 遇到哪些困惑点
  - 后续建议是什么
- 注意：`conversation` 导出是单独的产物流，可能晚于 job `completed`。`chatgptrest-call` wrapper 现在会对 `409 conversation export not ready` 做有界重试，但 cold client 仍应把 `answer` 获取和 `conversation` 获取视为两个阶段。

失败判定：

- backend 本身能工作，但 cold client 需要靠猜、靠隐藏背景、靠人工补提示才能跑通，也视为集成失败
- cold client 因 allowlist / headers / wrapper / preset 误解而失败，优先修文档或入口工具，不要只做维护者口头说明

推荐的冷启动客户端子代理分工：

- `scout`：便宜、快、读文档预算严格的发现代理。只负责确认入口路径、allowlist 约束、provider/preset 规范；不要真的发请求，也不要大段 dump 文档。
- `executor`：更强的执行代理，负责真正跑一次人类语义问题。这个代理必须显式固定 `provider` / `preset`，优先走 wrapper/CLI，必要时才走仓库登记过的 MCP fallback。
- `judge`：只读验收代理，只检查 `artifacts/cold_client_smoke/<timestamp>/`、真实 `job_id`、最终状态和 confusion points，判断这条链路算不算真正通过。

模型与 profile 选择建议：

- `scout` 用更快更便宜的模型即可，重点是遵守“少读、快到入口”的约束。
- `executor` 用更可靠的模型；对 cold-client 验收来说，真正难的是遵守 contract、少走弯路、在预算内到达真实 client command，而不是泛化 brainstorming。
- `judge` 可以回到较小模型，但 profile 要更收敛：只读、禁改仓库、禁自创请求路径。
- 如果本机 `~/.codex/config.toml` 里维护了命名 profile，验收时优先显式传 `--profile`，不要隐式依赖当前 shell 的默认 profile。

推荐 profile 语义：

- `cold-client-scout`：read-only / 小上下文 / 禁 `apply_patch` / 禁自创 REST headers / 禁 provider 替换。
- `cold-client-executor`：workspace-write 仅限产物目录 / 允许 wrapper、CLI、登记过的 MCP 工具 / 禁修改仓库代码与文档。
- `cold-client-judge`：read-only / 只读 artifacts + runbook + registry / 不发新请求。

当前这台主机的现成 profile 可直接映射为：

- `scout` -> `cold-client-scout`
- `builder` -> `cold-client-executor`
- `reviewer` -> `cold-client-judge`

脚本侧现在支持显式记录 profile / model：

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/codex_cold_client_smoke.py \
  --provider gemini \
  --preset pro \
  --profile cold-client-executor \
  --model gpt-5-codex \
  --question "请用两句话解释为什么写自动化测试可以降低回归风险。"
```

注意：

- `--profile` 是传给 nested `codex exec` 的本机配置 profile 名；仓库不会替你创建它。
- 如果 `executor` 经常靠隐藏背景才能跑通，优先修 runbook / wrapper / skill，而不是继续给 executor prompt 填背景。

## OpenClaw Guardian

用于“独立会话常驻巡查 + 可唤醒处理 + 失败告警”：

- 巡查脚本：`ops/openclaw_guardian_run.py`
- 手动唤醒：`ops/openclaw_guardian_wake.sh`
- 默认 agent/session：`main` / `main-guardian`（见 `config/topology.yaml` sidecars.guardian）
- 若要等 GitHub issue 回复，不要只挂 shell 死循环；改用 `ops/watch_github_issue_replies.py`，它会记住基线评论数，并在新评论出现时走 Feishu webhook 或桌面通知。

快速自检（不触发自动修复与通知）：

```bash
cd /vol1/1000/projects/ChatgptREST
./.venv/bin/python ops/openclaw_guardian_run.py --no-autofix --no-notify
```

说明：
- `--no-autofix` 会同时关闭 issue 自动收口 sweep（纯观察模式，不改状态）。
- `--projection-only` 是更强的只读模式：
  - 会同时关闭 autofix / notify / orch report 引用
  - 适合刷新 `artifacts/monitor/openclaw_guardian/latest_report.json`，不适合做巡查告警
- 在当前 OpenClaw + OpenMind 集成基线里，systemd guardian 模板默认带 `--no-include-orch-report`，避免 legacy `chatgptrest-*` orch 栈报告污染新五角色拓扑。
- 若你仍在维护旧版 ChatgptREST orch/worker 拓扑，才需要显式打开 `--include-orch-report`。
- systemd 基线会固定 `HOME=/home/yuanhaizhou/.home-codex-official` 与 `OPENCLAW_STATE_DIR=/home/yuanhaizhou/.home-codex-official/.openclaw`，避免双 HOME 状态目录漂移。
- 若 `openclaw` 可执行文件不在 PATH，guardian 不会崩溃；会在 `agent_result.error_type=FileNotFoundError` 记录降级失败。可安装 `openclaw`，或通过 `--openclaw-cmd <absolute_path>` 指定命令。

建议定时巡查（15 分钟）：

```bash
systemctl --user enable --now chatgptrest-guardian.timer
systemctl --user --no-pager status chatgptrest-guardian.timer
```

systemd 语义：
- `chatgptrest-guardian.service` 将退出码 `2` 视为成功（表示“仍有未解决 attention”，不是执行异常）；请以 `latest_report.json` 的 `needs_attention/resolved` 作为业务判定依据。

告警配置（可选）：
- `FEISHU_BOT_WEBHOOK_URL`（webhook 方式）
- 或 `FEISHU_BOT_TARGET` + 可选 `FEISHU_BOT_ACCOUNT`（通过 openclaw channel 发送）

Issue 自动收口参数（默认来自 env）：
- `CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_HOURS`（默认 `72`，`0` 表示关闭自动收口）
- `CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_MAX`（默认 `50`，每轮最多收口数量）
- `CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_SOURCE`（默认 `worker_auto`）
- `CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_STATUSES`（默认 `open,in_progress`）
- `CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_ACTOR`（默认 `openclaw_guardian`）
- `CHATGPTREST_CLIENT_ISSUE_CLOSE_AFTER_SUCCESSES`（默认 `3`，mitigated 后满足多少次 qualifying success 自动 `closed`；`0` 表示关闭）
- `CHATGPTREST_CLIENT_ISSUE_CLOSE_MAX`（默认 `20`，每轮最多自动 `closed` 的 issue 数量）

## OpenClaw Orch Agent [RETIRED]

> **Note**: This fleet (`chatgptrest-orch/w1/w2/w3/guardian`) is part of the retired legacy topology.
> See `config/topology.yaml` for the canonical production baseline.

用于旧版 ChatgptREST orch/worker 拓扑的注册一致性与健康检查：

- 工具：`ops/openclaw_orch_agent.py`
- 手动唤醒 orch：`ops/openclaw_orch_wake.sh`
- 约定 agent：
  - `chatgptrest-orch`
  - `chatgptrest-codex-w1`
  - `chatgptrest-codex-w2`
  - `chatgptrest-codex-w3`
  - `chatgptrest-guardian`

注意：
- 对于当前 `rebuild_openclaw_openmind_stack.py` 生成的 OpenClaw + OpenMind 集成基线，这套 legacy `chatgptrest-*` agent 已不是主拓扑。
- `chatgptrest-orch-doctor.timer` 在当前模板里只做只读巡检，不再自动 `--reconcile` 回写 legacy agents。
- 若需要对旧 orch 栈做一次性抢修，可手工运行带 `--reconcile` 的命令；不要再把 `--reconcile` 放到定时器里。

建议流程：

```bash
cd /vol1/1000/projects/ChatgptREST
# 仅检查（不修复）
./.venv/bin/python ops/openclaw_orch_agent.py --strict
# 对齐修复（删除漂移项并重建）
./.venv/bin/python ops/openclaw_orch_agent.py --reconcile --strict
# 可选：逐个 agent 发一条 healthcheck（会消耗一次 agent turn）
./.venv/bin/python ops/openclaw_orch_agent.py --reconcile --ping --strict
# 仅 ping orch（避免全量开销）
./.venv/bin/python ops/openclaw_orch_agent.py --reconcile --ping --ping-agent chatgptrest-orch --timeout-seconds 20 --strict
# 把 UI canary 与近期 ui_canary/proxy incident 一起纳入巡检
./.venv/bin/python ops/openclaw_orch_agent.py --reconcile --include-ui-canary --strict
# 有告警时自动唤醒 orch（带冷却，避免风控）
./.venv/bin/python ops/openclaw_orch_agent.py --reconcile --include-ui-canary --wake-on-attention --wake-cooldown-seconds 1800 --strict
```

输出里可关注：
- `pings[].ok`：turn 是否成功
- `pings[].session_id_matches`：reported session id 是否与期望一致（不一致会作为告警信号保留）
- `ui_canary.ok`：周期 UI 自检是否健康（会检查 stale + 连续失败阈值）
- `incidents.rows[]`：近期 open 的 `ui_canary/proxy` 事故摘要
- `wake_result`：是否触发 orch 唤醒（或因 cooldown 跳过）

可选定时巡检（不发 healthcheck prompt，且不会自动回写 legacy agents）：

```bash
systemctl --user enable --now chatgptrest-orch-doctor.timer
systemctl --user --no-pager status chatgptrest-orch-doctor.timer
```

## Topology Contract

Canonical source of truth for agent/sidecar/external-tool definitions:

- File: `config/topology.yaml`
- Loader: `chatgptrest.kernel.topology_loader`
- Concepts:
  - **Agent** — OpenClaw runtime agent (`main` in lean baseline)
  - **Sidecar** — System process (e.g. `guardian` timer), NOT an agent
  - **External tool** — CLI interface (e.g. `finagent`), consumed via plugin
  - **Retired** — Legacy fleet IDs (`chatgptrest-orch`, etc.)

All ops scripts (`openclaw_guardian_run.py`, `verify_openclaw_openmind_stack.py`) reference this file.
Changes to `topology.yaml` must be reviewed before deploy.

## systemd (recommended)

For stability (and to avoid "connection refused" when your terminal/Codex session exits), run the stack as
`systemd --user` services.

1) Install units + default env file:

```bash
cd /vol1/1000/projects/ChatgptREST
ops/systemd/install_user_units.sh
```

2) Edit env (proxy/no_proxy, tokens, etc):

- `~/.config/chatgptrest/chatgptrest.env`
  - Must include: `NO_PROXY=127.0.0.1,localhost` (otherwise local `127.0.0.1:*` calls may go through proxy)
  - Important: `systemctl --user` resolves `%h` from passwd home, not shell `$HOME`.
    If your shell overrides `HOME` (e.g. Codex profile), confirm the effective file with:
    `systemctl --user show chatgptrest-driver.service -p EnvironmentFiles`

3) Enable services:

```bash
systemctl --user enable --now \
  chatgptrest-chrome.service \
  chatgptrest-driver.service \
  chatgptrest-api.service \
  chatgptrest-worker-send.service \
  chatgptrest-worker-wait.service \
  chatgptrest-worker-repair.service \
  chatgptrest-mcp.service
```

Optional Feishu long-connection ingress:

```bash
systemctl --user enable --now chatgptrest-feishu-ws.service
systemctl --user --no-pager status chatgptrest-feishu-ws.service
```

The Feishu WS gateway must load both:
- `~/.config/chatgptrest/chatgptrest.env` for shared `OPENMIND_*` advisor auth
- `/vol1/maint/MAIN/secrets/credentials.env` for `FEISHU_*`

On the integrated host, the managed unit pins:
- `ADVISOR_API_URL=http://127.0.0.1:18711/v2/advisor/advise`

Do not assume `18713` for Feishu WS ingress unless you explicitly run a
separate Advisor service there.

4) Check status:

```bash
systemctl --user --no-pager status chatgptrest-chrome.service chatgptrest-driver.service chatgptrest-api.service
ss -ltnp | rg ':9222|:18701|:18711|:18712'
python3 ops/health_probe.py --json
```

Operational note:
- If a deploy changes shared executor / provider-routing code (for example `chatgptrest/executors/*`, `chatgptrest/ops_shared/provider.py`, or provider enable flags in `~/.config/chatgptrest/chatgptrest.env`), restart the **generic send worker** `chatgptrest-worker-send.service` in addition to any provider-specific send workers.
- Reason: `chatgptrest-worker-send.service` can claim any queued send job. Restarting only `chatgptrest-worker-send-gemini@*` or `chatgptrest-worker-send-qwen.service` can still leave old code/env active on the generic send lane, which then keeps producing stale behavior like `Unknown job kind`.
- `ops/health_probe.py` 现在除了端口/DB 健康，还会检查 public MCP ingress contract：已登记客户端配置、skill wrapper、以及 `ops/chrome_watchdog.sh` 是否把 issue API 正确指向 `18711` 而不是 `18712`。

5) If API is `failed (start-limit-hit)`:

```bash
systemctl --user reset-failed chatgptrest-api.service
systemctl --user restart chatgptrest-api.service
curl -fsS http://127.0.0.1:18711/healthz
```

6) If driver MCP startup fails (Codex shows `MCP startup incomplete` / `Unexpected content type: None`):
- Check driver service first:

```bash
systemctl --user --no-pager --full status chatgptrest-driver.service
journalctl --user -u chatgptrest-driver.service -n 120 --no-pager
```

- Typical root cause is singleton-lock conflict:
  - `Another MCP server instance is already running (singleton lock held)`
- Recovery:

```bash
systemctl --user reset-failed chatgptrest-driver.service
systemctl --user restart chatgptrest-driver.service
curl -siS -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"diag","version":"1"}}}' \
  http://127.0.0.1:18701/mcp | sed -n '1,40p'
```

7) `codex_apps` handshake failure (`https://chatgpt.com/backend-api/wham/apps`):
- This is upstream/auth/session related (not ChatgptREST internal driver version).
- If not needed for your workflow, disable Apps in Codex config (`features.apps=false`) to avoid noisy startup failures.

8) MCP auto-heal for API downtime:
- `chatgptrest-mcp.service` now sets `CHATGPTREST_MCP_AUTO_START_API=1` by default.
- If MCP receives `Connection refused` to `127.0.0.1:18711`, it will try one local API autostart and then retry the request.

9) Prompt safety guardrails (default on):
- `CHATGPTREST_ENFORCE_PROMPT_SUBMISSION_POLICY=1` enforces the unified submission policy.
- Live `/v1/jobs` smoke must clear the global bearer middleware before it can reach ask-guard logic. When the API runs with tokens configured:
  - non-`/v1/ops/*` routes accept `Authorization: Bearer <CHATGPTREST_API_TOKEN>`
  - `/v1/jobs*` also accepts `Authorization: Bearer <CHATGPTREST_OPS_TOKEN>` as a fallback
- if `CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE=1`, the same request must also include `X-Client-Instance` and `X-Request-ID`
  - if you want a reproducible operator path, prefer `ops/run_low_level_ask_live_smoke.py`, which reads the live env file, chooses the bearer token path, adds the required trace headers, and signs maintenance probes when HMAC secrets are present
- `chatgpt_web.ask` live smoke/test/probe requests are blocked by default (`live_chatgpt_smoke_blocked`), including `purpose=smoke/test/...`, explicit smoketest prefixes, known synthetic fault probes, and registered smoke client names.
- Low-level web ask callers must be pre-registered in `ops/policies/ask_client_registry.json` and must send a registered source identity (`X-Client-Id` or `X-Client-Name`). Missing/unknown identities now fail closed as `low_level_ask_client_identity_required` / `low_level_ask_client_not_registered`.
- Optional provenance headers for registered callers: `X-Client-Instance`, `X-Source-Repo`, `X-Source-Entrypoint`, `X-Client-Run-Id`. For `auth_mode=hmac` profiles, also send `X-Client-Timestamp`, `X-Client-Nonce`, `X-Client-Signature`.
- `chatgptrest-admin-mcp`, `chatgptrestctl-maint`, `internal-submit-wrappers`, and `finagent-event-extractor` are now HMAC-scoped maintenance/internal profiles; simply spoofing the client name is no longer sufficient for low-level ask.
- Registered automation callers are no longer allowed to keep a registry-name-only low-level ask lane. If `trust_class=automation_registered` and `allowed_surfaces` still includes `low_level_jobs`, the profile must be `auth_mode=hmac` or the server now fails closed with `low_level_ask_registry_misconfigured`.
- `planning-wrapper` is the only remaining approved automation wrapper on low-level web ask. It is HMAC-scoped, concurrency-limited, and duplicate-suppressed.
- `openclaw-wrapper` and `advisor-automation` are no longer valid external low-level ask identities. `openclaw-wrapper` is public-agent-only; `advisor-automation` is internal-runtime-only.
- `finbot-wrapper` is now explicitly registered as a public-agent-only service identity. It is intentionally visible in the registry so future finbot traffic is attributable, but low-level web ask remains disabled for that identity until a dedicated lane is approved.
- Direct low-level `POST /v1/jobs kind=chatgpt_web.ask` is blocked for interactive coding clients (`direct_live_chatgpt_ask_blocked`). For coding agents, real live asks should go through the public MCP tool `advisor_agent_turn` on `http://127.0.0.1:18712/mcp`, not ad-hoc `curl/chatgptrestctl` or direct `/v3/agent/turn` usage.
- Direct low-level `POST /v1/jobs kind=gemini_web.ask|qwen_web.ask` from coding-agent client identities is also blocked by default (`coding_agent_low_level_ask_blocked`). The only supported default path for coding agents is the public advisor-agent MCP surface; low-level exceptions must use a registered maintenance/internal identity such as `chatgptrest-admin-mcp` or `chatgptrestctl-maint`.
- If `CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST` is enabled, registered low-level ask identities are allowed through that coarse allowlist gate so the dedicated ask guard can make the real decision. This is expected: an unsigned maintenance request should now fail as `low_level_ask_client_auth_failed` instead of being hidden behind `client_not_allowed`.
- Registered automation callers are additionally screened for bad-fit workloads. Structured extractor / extractor-style JSON-only microtasks, sufficiency gates, and other low-value automation asks fail as `low_level_ask_intent_blocked` instead of consuming live web capacity.
- Gray-zone automation profiles that are marked `codex_guard_mode=classify` may still send substantive review/report asks that request JSON output; those asks now go through Codex intent review instead of being hard-blocked only because they requested JSON formatting.
- If the gray-zone Codex classifier returns `allow_with_limits`, ingress now applies the limits for real by downgrading request fields such as `preset`, `deep_research`, and `min_chars` before persisting the job.
- The gray-zone Codex classifier now prefers the repo's known wrapper install (`~/.home-codex-official/.local/bin/codex`) before generic `PATH` discovery. If classify starts failing closed with unexpected OpenAI scope errors, verify that the process is not resolving to a different PATH-level Codex binary.
- `CHATGPTREST_ASK_GUARD_CODEX_TIMEOUT_SECONDS` controls the gray-zone Codex classifier budget (default `45`). If live classify is healthy but spuriously timing out on substantive JSON review prompts, raise this as an ops setting before changing code defaults; current host rollout uses `120`.
- `advisor_ask` recent-duplicate reuse is enabled by default. `CHATGPTREST_ADVISOR_ASK_RECENT_DUPLICATE_REUSE=1` plus `CHATGPTREST_ADVISOR_ASK_RECENT_DUPLICATE_WINDOW_SECONDS` (default `21600`) causes `/v2/advisor/ask` to reuse an equivalent recent job instead of dispatching a new controller run. Matching first uses the current hashed `request_fingerprint`; if the older row predates that format, the server falls back to exact `question + intent_hint + session_id + user_id + role_id` matching so legacy sessions are still protected from duplicate conversation creation.
- Pro presets hard-block trivial prompts (`trivial_pro_prompt_blocked`) and `purpose=smoke/test/...` (`pro_smoke_test_blocked`) with no request-level override.
- If a legacy synthetic/trivial ask somehow survives ingress and reaches `wait`, worker completion guard now treats a non-empty short answer as terminal instead of endlessly looping through `completion_guard_downgraded -> wait_requeued`. The breaker is controlled by `CHATGPTREST_LEGACY_TRIVIAL_WAIT_LOOP_BREAKER_THRESHOLD` (default `3`) and emits `completion_guard_legacy_trivial_loop_broken` before finalizing the job.
- Research completion contract is now stricter than generic ask completion:
  - `deep_research` / `report_grade` style jobs expose a `completion_contract` block in status/result payloads.
  - `completion_contract.answer_state=final` is the only reliable signal that a research answer is truly finalized.
  - stalled or under-min-chars research answers now stay non-final (`in_progress` or `needs_followup`) instead of being auto-completed via `completion_guard_completed_under_min_chars`.
  - `conversation export` / widget export / answer rehydrate are recovery observations, not by themselves finality proof.
- Non-Pro live ChatGPT smoke remains blocked by default; the only request-level escape hatch left here is `params.allow_live_chatgpt_smoke=true` for tightly controlled non-Pro exceptions.
- `ops/smoke_test_chatgpt_auto.py` is now fail-closed by default; use Gemini/Qwen smoke paths unless you intentionally pass `--allow-live-chatgpt-smoke`.

Attachment-contract preflight notes:
- URI-like text (`https://...`, `s://...`) no longer triggers `AttachmentContractMissing`.
- slash-delimited conceptual phrases such as `episodic/semantic/procedural` no longer trigger `AttachmentContractMissing`.
- true local path references still do: `/vol1/...`, `./bundle.md`, `../report_v1.md`, `C:\tmp\review.pdf`.

Live low-level ask smoke helper:

```bash
./.venv/bin/python ops/run_low_level_ask_live_smoke.py
```

Expected outcomes:

- unsigned maintenance probes => `403 low_level_ask_client_auth_failed`
- signed `chatgptrestctl-maint` => `200` with a `job_id`
- signed `chatgptrest-admin-mcp` => `200` with a `job_id`
- if both `CHATGPTREST_API_TOKEN` and `CHATGPTREST_OPS_TOKEN` exist and differ, the helper also proves `/v1/jobs*` accepts the OPS token fallback path by re-running the unsigned maintenance probe with the OPS token
- unsigned `planning-wrapper` probe => `403 low_level_ask_client_auth_failed`
- signed `planning-wrapper` sufficiency-gate probe => `403 ... reason=sufficiency_gate`
- signed substantive `planning-wrapper` JSON review => `200` with a `job_id`
- immediate duplicate of the same signed `planning-wrapper` review => `409 low_level_ask_duplicate_recently_submitted`
- `openclaw-wrapper` low-level probe => `403 low_level_ask_surface_not_allowed`
- `advisor_ask` alias low-level probe => `403 low_level_ask_surface_not_allowed`

10) Optional periodic monitor report (12h window):
- Enable timer: `systemctl --user enable --now chatgptrest-monitor-12h.timer`
- Check timer: `systemctl --user --no-pager status chatgptrest-monitor-12h.timer`
- Output dir: `artifacts/monitor/periodic/`

11) Optional orch agent reconcile doctor:
- Enable timer: `systemctl --user enable --now chatgptrest-orch-doctor.timer`
- Check timer: `systemctl --user --no-pager status chatgptrest-orch-doctor.timer`
- Note: this timer runs `openclaw_orch_agent.py --reconcile --include-ui-canary --strict` (no `--ping` prompt turns, no wake by default).
- Note: `chatgptrest-orch-doctor.service` treats exit code `2` as success (`needs_attention`), so use report JSON for业务判定而不是只看 unit 是否 failed。

12) Optional viewer watchdog (black-screen auto-heal):
- Enable timer: `systemctl --user enable --now chatgptrest-viewer-watchdog.timer`
- Check timer/service: `systemctl --user --no-pager status chatgptrest-viewer-watchdog.timer chatgptrest-viewer-watchdog.service`
- Tunables (`~/.config/chatgptrest/chatgptrest.env`):
  - `CHATGPTREST_VIEWER_WATCHDOG_STATUS_TIMEOUT_SECONDS` (default `15`)
  - `CHATGPTREST_VIEWER_WATCHDOG_SLEEP_AFTER_RESTART_SECONDS` (default `1`)
  - `CHATGPTREST_VIEWER_WATCHDOG_MAX_HEAL_ATTEMPTS` (default `2`)
  - `CHATGPTREST_VIEWER_WATCHDOG_GPU_EXIT15_THRESHOLD` (default `3`)
  - `CHATGPTREST_VIEWER_WATCHDOG_CHROME_LOG_LINES` (default `200`)
  - 说明：watchdog 会扫描 `chrome.log` 中最近窗口内的 `GPU process exited unexpectedly: exit_code=15`；达到阈值时即使端口健康也会触发 `--full` 重启。

13) Optional Issue Ledger -> GitHub sync timer:
- Enable timer: `systemctl --user enable --now chatgptrest-issue-github-sync.timer`
- Check timer/service: `systemctl --user --no-pager status chatgptrest-issue-github-sync.timer chatgptrest-issue-github-sync.service`
- Requires `CHATGPTREST_GITHUB_ISSUE_SYNC_ENABLED=1` and `CHATGPTREST_GITHUB_ISSUE_SYNC_REPO=owner/repo`.

## Auto-Repair (Codex) (optional)

Goal: make infra/UI glitches self-heal without resubmitting prompts.

This does **NOT** send new prompts. It can:
- capture UI snapshots (`repair.check`/`repair.autofix`)
- refresh pages
- restart driver/Chrome (recommended via `systemd --user`)

Enable worker auto-submit (recommended):

```bash
cd /vol1/1000/projects/ChatgptREST
ops/systemd/enable_auto_autofix.sh
systemctl --user restart chatgptrest-worker-send.service chatgptrest-worker-wait.service
```

What to look for:
- The original job’s `events.jsonl` should contain `type=auto_autofix_submitted`.
- The repair job directory `artifacts/jobs/<repair_job_id>/` should contain evidence + an action report.

Enable full maint self-heal (guarded `sre.fix_request -> repair.autofix`, recommended after you trust the rollout):

```bash
cd /vol1/1000/projects/ChatgptREST
ops/systemd/enable_maint_self_heal.sh
```

This rollout now also aligns the runtime stack onto the same checkout by writing `20-runtime-worktree.conf`
drop-ins for:

- `chatgptrest-api.service`
- `chatgptrest-mcp.service`
- `chatgptrest-maint-daemon.service`
- `chatgptrest-worker-send.service`
- `chatgptrest-worker-wait.service`
- `chatgptrest-worker-repair.service`

So after enabling self-heal, maintagent memory, `sre.fix_request`, runtime autofix, API, and MCP all read the same code and state paths.
The rollout keeps persistent `state/` and `artifacts/` on the primary repo root, so a clean worktree only supplies code, not a second production database.
The script also disables stale `99-current-working-tree.conf` API overrides if they would shadow the managed runtime-worktree drop-in.

This keeps the existing send-phase guardrails, but also enables:
- maint daemon `--enable-codex-sre-autofix`
- medium-risk runtime actions (`capture_ui,clear_blocked,restart_driver,restart_chrome,switch_gemini_proxy`)
- worker auto-submit for retryable infra/UI failures

## Gemini Web (when ChatGPT is degraded)

- Gemini Web automation runs in the **same CDP Chrome** as ChatGPT by default (`GEMINI_CDP_URL` defaults to `CHATGPT_CDP_URL` via `ops/start_driver.sh`).
- Prereq: that Chrome profile must be logged into `https://gemini.google.com/app` (otherwise jobs will fail with an auth/UI error).
- If you see `status=needs_followup` with `error_type=GeminiPromptBoxNotFound/GeminiNotLoggedIn/...`, fix the browser state (login / proxy / captcha) and wait for the same `job_id` to retry.
  - Retry pacing: `CHATGPTREST_GEMINI_NEEDS_FOLLOWUP_RETRY_AFTER_SECONDS` (default `300`).
- Region note: if Gemini shows “目前不支持你所在的地区” (no prompt box), it’s an **egress location** issue (not file count/size). Fix by routing Chrome through a supported-region proxy (e.g. via `ALL_PROXY`/`CHROME_PROXY_SERVER`); if you use mihomo, pin the **actual Gemini-matching selector group** to a supported node, then restart Chrome.
  - Do **not** assume Gemini follows `🚀 节点选择`. On YogaS2 the live rule matched `gemini.google.com` to `💻 Codex`, so switching `🚀 节点选择` had no effect.
  - Verify the real group via mihomo `/connections` before changing anything:

    ```bash
    curl --noproxy '*' -fsS http://127.0.0.1:9090/connections | jq '.connections[] | select((.metadata.host // "")=="gemini.google.com") | {host:(.metadata.host // ""), rule, rulePayload, chains}'
    ```

  - After changing the selector, **restart `chatgptrest-chrome.service`**. Chrome will otherwise keep reusing existing Google/Gemini connections and the region block can appear unchanged.
  - Example (YogaS2 live host): pin `💻 Codex` to a supported node, then restart Chrome and retry the same `job_id`:

    ```bash
    grp_enc=$(python3 -c 'import urllib.parse; print(urllib.parse.quote("💻 Codex"))')
    curl --noproxy '*' -sS -X PUT -H 'Content-Type: application/json' \
      -d '{"name":"🇺🇲 美国 01"}' "http://127.0.0.1:9090/proxies/${grp_enc}"
    systemctl --user restart chatgptrest-chrome.service
    ```
  - Quick check (through proxy): `curl -fsS -x socks5h://127.0.0.1:7890 https://www.cloudflare.com/cdn-cgi/trace | rg '^(loc|colo|ip)='`
  - `repair.check` now emits a `Mihomo / Gemini Egress` section for Gemini jobs; `repair.autofix` can perform `switch_gemini_proxy -> restart_chrome` automatically if you configure:
    - `CHATGPTREST_GEMINI_MIHOMO_PROXY_GROUP`
    - `CHATGPTREST_GEMINI_MIHOMO_CANDIDATES`
    - `CHATGPTREST_CODEX_AUTOFIX_ALLOW_ACTIONS` includes `switch_gemini_proxy`
- UI stability note: Gemini new chat can briefly render a transient `textarea` before the stable editor appears as `div[role='textbox']`, `div.ql-editor[contenteditable='true']`, or `input-area-v2`.
  - Driver default now prefers the stable editor selectors and only falls back to `textarea` after `GEMINI_TEXTAREA_FALLBACK_GRACE_SECONDS` (default `1.8`).
  - If you see `Locator.click ... waiting for locator(\"textarea\").first`, treat it as prompt-box bootstrap drift, not as a generic login, upload, or captcha failure.
- CDP tab isolation note: Gemini now opens a fresh CDP tab per invocation by default instead of reusing an existing `gemini.google.com` page.
  - This prevents cross-process page mutation when multiple Gemini send workers share the same Chrome.
  - Reuse is opt-in only via `GEMINI_REUSE_EXISTING_CDP_PAGE=1`.
- Submit via REST: `POST /v1/jobs` with `kind="gemini_web.ask"` (see `docs/contract_v1.md`).
- Submit via MCP: `chatgptrest_gemini_ask_submit` (recommended for Codex CLI).
- Presets:
  - `pro` (default)
  - `deep_think` (requires Ultra + UI rollout; if missing/fails, use `pro`)
    - When Deep Think returns a short overload/crowded message (e.g. “A lot of people are using Deep Think right now…”), the driver now clicks Gemini's retry control first (default `3` attempts), then ChatgptREST falls back to `pro` if still overloaded.
    - Tune via env:
      - `GEMINI_DEEP_THINK_INPLACE_RETRIES_PER_ROUND` (default `3`, range `0..10`)
      - `GEMINI_DEEP_THINK_RETRY_ATTEMPTS` (legacy alias for the same setting)
      - `GEMINI_DEEP_THINK_RETRY_WAIT_TIMEOUT_SECONDS` (default `180`, range `30..900`)
      - `CHATGPTREST_GEMINI_DEEP_THINK_AUTO_FALLBACK` (default `true`)
  - Policy: `thinking` / `pro_thinking` / `auto` / `default(s)` are accepted for compatibility but normalized to `pro`.
- Deep Research:
  - Set `params.deep_research=true` on `kind=gemini_web.ask` to use Gemini Deep Research tool flow.
  - Constraint: `params.deep_research=true` cannot be combined with `input.github_repo` (import-code path).
  - Executor preflight probe (no prompt send): by default, send phase runs `gemini_web_self_check` first (`CHATGPTREST_GEMINI_DEEP_RESEARCH_SELF_CHECK=1`).
    - If probe confirms Deep Research tool is missing in current UI surface, job returns `status=needs_followup` (`GeminiDeepResearchToolUnavailable`) instead of blind-send.
    - Timeout knob: `CHATGPTREST_GEMINI_DEEP_RESEARCH_SELF_CHECK_TIMEOUT_SECONDS` (default `45`).
  - If you see `RuntimeError: Gemini tool state unknown after toggle: (Deep Research|深入研究|深度研究)`:
    - Root cause is usually Gemini UI selector drift (checkbox attrs hidden after toggle).
    - First verify current tool surface (no prompt send):
      - `gemini_web_self_check` should show `Tools` button visible and include `Deep Research` item.
    - Then restart runtime to load latest selector fallback logic:
      - `systemctl --user reset-failed chatgptrest-driver.service`
      - `systemctl --user restart chatgptrest-driver.service chatgptrest-worker-send.service chatgptrest-worker-wait.service`
    - Retry the **same job** (or resubmit with a new idempotency key only after confirming the old job terminal state).
- Guardrail: do not mix `kind=chatgpt_web.*` with a Gemini `conversation_url` (or vice versa). ChatgptREST rejects mismatches to avoid running the wrong driver and falsely writing `chatgpt_blocked_state.json`.
- Attach files via Google Drive (recommended when “上传文件” is disabled/limited):
  - Pass `input.file_paths` to ChatgptREST (`kind="gemini_web.ask"`). The worker uploads each file into Drive via `rclone copyto`, resolves its Drive `ID` via `rclone lsjson`, then the driver attaches via Gemini UI (`+` → `从云端硬盘添加` → paste URL → `插入`).
  - Attachment count policy (Gemini):
    - As of 2026-02-28, official Gemini help docs indicate “up to 10 files per prompt”, and “for Deep Research, zip upload supports up to 10 files per zip”.
    - Source refs:
      - https://support.google.com/gemini/answer/14903178
      - https://support.google.com/gemini/answer/16407868
    - ChatgptREST executor enforces `CHATGPTREST_GEMINI_MAX_FILES_PER_PROMPT` (default `10`) with auto-merge/index (`GEMINI_ATTACH_INDEX.md`, `GEMINI_ATTACH_BUNDLE.md`, `GEMINI_ATTACH_OVERFLOW.zip`) before Drive upload.
    - Deep Research defaults to zip expansion (`CHATGPTREST_GEMINI_DEEP_RESEARCH_EXPAND_ZIP=1`) so zip-only context is transformed into readable bundle text before send.
  - Prereq: `rclone` is configured + authorized for Drive (override config path via `CHATGPTREST_RCLONE_CONFIG` when needed).
  - Proxy note: `rclone` typically honors `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` (and may ignore `ALL_PROXY`). ChatgptREST bridges `ALL_PROXY` → `HTTP(S)_PROXY` for rclone; you can also set `CHATGPTREST_RCLONE_PROXY` explicitly for the worker/service.
  - Configure via:
    - `CHATGPTREST_GEMINI_ATTACHMENT_PREPROCESS_ENABLED` (default `1`)
    - `CHATGPTREST_GEMINI_MAX_FILES_PER_PROMPT` (default `10`, clamp `1..50`)
    - `CHATGPTREST_GEMINI_DEEP_RESEARCH_EXPAND_ZIP` (default `1`)
    - `CHATGPTREST_GEMINI_ATTACHMENT_PREPROCESS_DIR` (default `/tmp/chatgptrest_gemini_inputs`)
    - `CHATGPTREST_GEMINI_ZIP_EXPAND_MAX_MEMBERS` (default `300`)
    - `CHATGPTREST_GEMINI_BUNDLE_PER_FILE_MAX_BYTES` (default `200000`)
    - `CHATGPTREST_GEMINI_BUNDLE_MAX_BYTES` (default `5000000`)
    - `CHATGPTREST_GDRIVE_RCLONE_REMOTE` (default `gdrive`)
    - `CHATGPTREST_GDRIVE_UPLOAD_SUBDIR` (default `chatgptrest_uploads`)
    - `CHATGPTREST_GDRIVE_SYNC_TIMEOUT_SECONDS` (default `15`)
    - `CHATGPTREST_GDRIVE_MAX_FILE_BYTES` (default `209715200` / 200MiB; set to `0` to disable)
    - `CHATGPTREST_RCLONE_PROXY` (optional; sets `HTTP_PROXY`/`HTTPS_PROXY` for rclone subprocesses)
    - `CHATGPTREST_RCLONE_BIN` (default `rclone`)
    - `CHATGPTREST_RCLONE_TIMEOUT_SECONDS` / `CHATGPTREST_RCLONE_COPYTO_TIMEOUT_SECONDS`
    - `CHATGPTREST_RCLONE_CONTIMEOUT_SECONDS` / `CHATGPTREST_RCLONE_IO_TIMEOUT_SECONDS` (default `10` / `30`)
    - `CHATGPTREST_RCLONE_RETRIES` / `CHATGPTREST_RCLONE_LOW_LEVEL_RETRIES` / `CHATGPTREST_RCLONE_RETRIES_SLEEP_SECONDS` (default `1` / `1` / `0`)
    - Optional cleanup (disabled by default): `CHATGPTREST_GDRIVE_CLEANUP_MODE` (`never` | `on_success` | `always`)
  - Fail-closed by default:
    - retryable errors (timeouts/transient API issues) -> `status=cooldown` (`DriveUploadNotReady`) to avoid sending a prompt without attachments
    - permanent errors (rclone misconfig/auth, file too large) -> `status=error` (`DriveUploadFailed`)
    - Set `params.drive_name_fallback=true` only if you accept unreliable filename search/indexing delays.
- Import code (repo URL) (optional, gated by default): set `input.github_repo="<repo_url>"` and `params.enable_import_code=true` for `kind="gemini_web.ask"`.
- Public repo review without imported-code: prefer direct repo URL in the prompt/context and keep `enable_import_code=false`. Only turn on imported-code when you specifically need Gemini’s repo import lane.
- App mentions (optional): the driver recognizes `@Google 云端硬盘` / `@Google Drive` (and `@Google 文档` / `@Google Docs`) and inserts the **real app mention** (not plain text). Treat this as a convenience for referencing existing Drive/Docs resources by name, not a guaranteed attachment mechanism.

## Qwen Web (domestic-research fast path)

- If Qwen is intentionally disabled on this host, keep it fully out of the runtime path:
  - `CHATGPTREST_QWEN_ENABLED=0`
  - `CHATGPTREST_UI_CANARY_PROVIDERS=chatgpt,gemini`
  - `systemctl --user stop chatgptrest-worker-send-qwen.service`
  - `systemctl --user disable chatgptrest-worker-send-qwen.service`
  - `bash ops/qwen_chrome_stop.sh`
  - stop the optional noVNC viewer (`pkill -f 'websockify --web /usr/share/novnc 6085 192.168.1.17:5905'` or equivalent host-specific wrapper)

- Qwen Web automation uses a **separate CDP Chrome** by default:
  - `QWEN_CDP_URL=http://127.0.0.1:9335`
  - recommended launcher: `ops/qwen_chrome_start.sh` (includes `--no-proxy-server`).
- Worker env must explicitly enable the provider:
  - `CHATGPTREST_QWEN_ENABLED=1`
  - after changing this flag, restart both `chatgptrest-worker-send.service` and `chatgptrest-worker-send-qwen.service`
- Prereq: that Qwen Chrome profile must already be logged into `https://www.qianwen.com/`.
- If login is required, run `bash ops/qwen_viewer_start.sh` and open the printed noVNC URL to login once.
  - Quick diagnosis: `bash ops/qwen_doctor.sh` (starts the viewer, prints noVNC URL, runs `qwen_web_self_check`).
  - After login, you can run a full REST smoke test: `bash ops/smoke_test_qwen.sh`.
- Submit via REST: `POST /v1/jobs` with `kind="qwen_web.ask"` (see `docs/contract_v1.md`).
- Submit via MCP: `chatgptrest_qwen_ask_submit` (recommended for Codex CLI).
- Presets:
  - `deep_thinking` (recommended default)
  - `deep_research` (higher depth, but has daily quota risk)
  - `auto` (maps to `deep_thinking`; if `deep_research=true`, maps to `deep_research`)
- Quota note: Qwen `deep_research` is quota-limited per day; on exhaustion, jobs may return `status=cooldown`.
- Guardrail: do not mix Qwen `conversation_url` with `chatgpt_web.*`/`gemini_web.*`; ChatgptREST rejects cross-provider mismatches.
- Driver health/debug tools:
  - `qwen_web_self_check` (no prompt send, check model/composer/mode buttons)
  - `qwen_web_capture_ui` (no prompt send, capture Qwen UI snapshots for selector regressions)

## Start / Restart

1) Start/verify Chrome (with proxy when needed):

```bash
cd /vol1/1000/projects/ChatgptREST
export DISPLAY=:99
bash ops/chrome_start.sh
```

Optional: start Qwen viewer (recommended for login) + dedicated Qwen Chrome (no proxy, separate profile):

```bash
cd /vol1/1000/projects/ChatgptREST
bash ops/qwen_viewer_start.sh
```

If you don't need the noVNC UI, you can start Chrome only:

```bash
cd /vol1/1000/projects/ChatgptREST
export DISPLAY=:99
bash ops/qwen_chrome_start.sh
```

## Safe UI Viewing (no worker interference)

If you need to frequently **view** ChatGPT Web UI (history, answers) without racing the worker’s CDP automation:

- Use a dedicated “viewer” Chrome on a separate X display + separate Chrome profile (safe to scroll/click).
- Use a separate **view-only** noVNC endpoint for the worker display (safe to watch; no input).

Start viewer (interactive, separate profile, separate DISPLAY):

```bash
cd /vol1/1000/projects/ChatgptREST
bash ops/viewer_start.sh
```

Restart viewer (when noVNC is black / Chrome crashed):

```bash
cd /vol1/1000/projects/ChatgptREST
bash ops/viewer_restart.sh --chrome-only   # keep X/VNC, restart Chrome only
bash ops/viewer_restart.sh --full          # restart X/VNC/Chrome
```

Quick diagnosis / auto-heal (agent-friendly):

```bash
cd /vol1/1000/projects/ChatgptREST
chatgptrestctl viewer status
./.venv/bin/python ops/viewer_watchdog.py --check
./.venv/bin/python ops/viewer_watchdog.py --heal
```

Stop viewer (free ports / clean slate):

```bash
cd /vol1/1000/projects/ChatgptREST
bash ops/viewer_stop.sh
```

Start worker view-only mirror (read-only):

```bash
cd /vol1/1000/projects/ChatgptREST
bash ops/worker_viewonly_start.sh
```

Start worker interactive mirror (for login/debug; may affect active jobs):

```bash
cd /vol1/1000/projects/ChatgptREST
WORKER_VIEW_NOVNC_BIND_HOST=<tailscale_ip> bash ops/worker_view_start.sh
```

Phone access via Tailscale:

- Preferred (HTTPS + paths): enable “Serve” in the Tailscale admin console for this tailnet, then run:

```bash
cd /vol1/1000/projects/ChatgptREST
bash ops/tailscale_serve_chatgptrest.sh
```

- Fallback (Serve disabled): `ops/tailscale_serve_chatgptrest.sh` will bind noVNC to the Tailscale IP and print plain-HTTP tailnet URLs.

Notes:
- Viewer uses a separate Chrome `--user-data-dir` and will require a one-time login in that profile.
- Avoid clicking “Regenerate/Answer now” in the viewer profile unless you intend to change conversation state.
- For unattended operations, enable `chatgptrest-viewer-watchdog.timer` so black-screen/Chrome crash can self-heal.

2) Start ChatgptREST internal driver (recommended):

```bash
cd /vol1/1000/projects/ChatgptREST
export CHATGPT_CDP_URL=http://127.0.0.1:9222
export QWEN_CDP_URL=http://127.0.0.1:9335
export CHATGPT_MIN_PROMPT_INTERVAL_SECONDS=61
export QWEN_MIN_PROMPT_INTERVAL_SECONDS=0
bash ops/start_driver.sh
```

Notes:
- `ops/start_driver.sh` defaults driver state to `state/driver/` (persistent across restarts). Override via:
  - `CHATGPTREST_DRIVER_STATE_DIR`
  - or set `MCP_SERVER_LOCK_FILE` / `MCP_IDEMPOTENCY_DB` / `CHATGPT_BLOCKED_STATE_FILE` / `CHATGPT_GLOBAL_RATE_LIMIT_FILE` explicitly.
  - default singleton lock file is `state/driver/chatgpt_web_mcp_server.lock` (avoid mixed `.run` paths).
- Blocked/cooldown events JSONL: `CHATGPT_BLOCKED_EVENTS_LOG` (default `artifacts/monitor/chatgpt_blocked_events.jsonl`).
- Qwen CDP auto-start/auto-restart is disabled by default:
  - `QWEN_CDP_AUTO_START=0`
  - `QWEN_CDP_AUTO_RESTART=0`
  - if needed, enable explicitly and ensure `QWEN_CHROME_START_SCRIPT`/`QWEN_CHROME_STOP_SCRIPT` are set to the Qwen-specific scripts.

3) (Legacy) Start external chatgptMCP server instead of internal driver:

```bash
cd /vol1/1000/projects/chatgptMCP
export CHATGPT_CDP_URL=http://127.0.0.1:9222
export CHATGPT_MIN_PROMPT_INTERVAL_SECONDS=61
bash ops/start_chatgpt_web_mcp_http.sh
```

4) Start ChatgptREST:

```bash
cd /vol1/1000/projects/ChatgptREST
export CHATGPTREST_DRIVER_MODE=internal_mcp
export CHATGPTREST_DRIVER_URL=http://127.0.0.1:18701/mcp
ops/start_api.sh
ops/start_worker.sh send
ops/start_worker.sh wait
ops/start_sre_runner.sh  # optional dedicated incident-repair coordinator
ops/start_mcp.sh   # optional
```

Notes:
- The `send` worker only submits prompts (paced by the 61s throttle).
- The `wait` worker only waits for answers (no prompt send).
- The optional `sre` worker only consumes `kind` prefix `sre.` and keeps lane-scoped repair memory under `state/sre_lanes/`.
- For single-worker mode (backwards compatible), run `ops/start_worker.sh` without args.
- Optional fixed-window caps (reduce ChatGPT “unusual activity” cooldown risk; default disabled):
  - `CHATGPTREST_CHATGPT_MAX_PROMPTS_PER_HOUR` (default `0`)
  - `CHATGPTREST_CHATGPT_MAX_PROMPTS_PER_DAY` (default `0`)
- Rollback to external chatgptMCP (no code change):
  - set `CHATGPTREST_DRIVER_MODE=external_mcp` and `CHATGPTREST_DRIVER_URL=http://127.0.0.1:18701/mcp`
  - restart the workers (send/wait) to pick up the change

Wait slicing (prevents wait queue starvation):
- `CHATGPTREST_WAIT_SLICE_SECONDS` (default `60`, `0` disables): caps how long a single worker run will wait on one job before re-queuing it.

Wait no-progress timeout guard (prevents infinite `in_progress` loops in `phase=wait`):
- `CHATGPTREST_WAIT_NO_PROGRESS_GUARD` (default `true`)
- `CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS` (default `7200`)
- `CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS` (default `21600`)
- `CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS` (default `1800`; faster fail when no stable thread URL)
- `CHATGPTREST_WAIT_NO_PROGRESS_STATUS` (default `needs_followup`; allowed: `needs_followup|cooldown|blocked|error`)
- `CHATGPTREST_WAIT_NO_PROGRESS_RETRY_AFTER_SECONDS` (default `600`; used when status is retryable)
- Emits event `wait_no_progress_timeout` into DB/artifacts for postmortem.

Wait-phase transient retry pacing (reduces long cooldown after short transport glitches):
- `CHATGPTREST_WAIT_INFRA_RETRY_AFTER_SECONDS` (default `20`): used when `phase=wait` + stable thread URL + infra errors (e.g. connection refused/page closed).
- `CHATGPTREST_WAIT_UI_RETRY_AFTER_SECONDS` (default `12`): used when `phase=wait` + stable thread URL + UI transient errors.
- Fallback remains `CHATGPTREST_INFRA_RETRY_AFTER_SECONDS` / `CHATGPTREST_UI_RETRY_AFTER_SECONDS` for non-wait or no-thread-URL cases.

Conversation export throttling (prevents export storms during wait slicing):
- `CHATGPTREST_CONVERSATION_EXPORT_OK_COOLDOWN_SECONDS` (default `120`)
- `CHATGPTREST_CONVERSATION_EXPORT_FAIL_BACKOFF_BASE_SECONDS` (default `60`)
- `CHATGPTREST_CONVERSATION_EXPORT_FAIL_BACKOFF_MAX_SECONDS` (default `600`)
- `CHATGPTREST_CONVERSATION_EXPORT_GLOBAL_MIN_INTERVAL_SECONDS` (default `30`)
- Per-job state: `artifacts/jobs/<job_id>/conversation_export_state.json`

Completion-time export quick retry (reduces `conversation_export_missing_reply` downgrade loops):
- `CHATGPTREST_EXPORT_MISSING_REPLY_RETRIES` (default `2`)
- `CHATGPTREST_EXPORT_MISSING_REPLY_RETRY_SLEEP_SECONDS` (default `3.0`)

## Anti-Detection (ChatGPT Web)

- Chrome launch flags are set in `ops/chrome_start.sh` (stealth defaults enabled).
- CDP readiness polling (wait for `/json/version`):
  - `CHROME_CDP_READY_TRIES` (default `80`)
  - `CHROME_CDP_READY_DELAY_SECONDS` (default `0.1`)
- Stealth init script (override to disable):
  - `CHATGPT_STEALTH_INIT_SCRIPT` (default `true`)
- Viewport jitter (per page):
  - `CHATGPT_VIEWPORT_JITTER_PX` (default `8`, or `w,h`)
- Typing jitter (per keystroke):
  - `CHATGPT_TYPE_DELAY_MEAN_MS` (default `100`)
  - `CHATGPT_TYPE_DELAY_STD_MS` (default `30`)
  - `CHATGPT_TYPE_DELAY_MIN_MS` / `CHATGPT_TYPE_DELAY_MAX_MS` (default `20` / `220`)
  - `CHATGPT_TYPE_THINK_PAUSE_CHANCE` (default `0.06`)
  - `CHATGPT_TYPE_THINK_PAUSE_PUNCT_CHANCE` (default `0.2`)
  - `CHATGPT_TYPE_THINK_PAUSE_MS` (default `300,1200`)
- Idle interactions during wait loops:
  - `CHATGPT_IDLE_ACTION_CHANCE` (default `0.03`)
  - `CHATGPT_IDLE_SCROLL_PX` (default `60,180`)
- Randomness decision logging (debug):
  - `CHATGPT_RANDOMNESS_LOG` (default `false`)
- Detection regex overrides (optional):
  - `CHATGPT_CLOUDFLARE_TITLE_REGEX` / `CHATGPT_CLOUDFLARE_TITLE_REGEX_EXTRA`
  - `CHATGPT_CLOUDFLARE_URL_REGEX` / `CHATGPT_CLOUDFLARE_URL_REGEX_EXTRA`
  - `CHATGPT_LOGIN_URL_REGEX` / `CHATGPT_LOGIN_URL_REGEX_EXTRA`
  - `CHATGPT_LOGIN_TEXT_REGEX` / `CHATGPT_LOGIN_TEXT_REGEX_EXTRA`
  - `CHATGPT_VERIFY_REGEX` / `CHATGPT_VERIFY_REGEX_EXTRA`
  - `CHATGPT_UNUSUAL_ACTIVITY_REGEX` / `CHATGPT_UNUSUAL_ACTIVITY_REGEX_EXTRA`
  - `GOOGLE_VERIFY_REGEX` / `GOOGLE_VERIFY_REGEX_EXTRA`
- Debug artifacts (network/proxy):
  - `CHATGPT_DEBUG_CAPTURE_PERF` (default `false`)
  - `CHATGPT_DEBUG_PERF_RESOURCE_LIMIT` (default `200`)
- Verification/captcha cooldown:
  - `CHATGPT_VERIFICATION_COOLDOWN_SECONDS` (default `3600`)
- Verification auto-click (same CDP Chrome session):
  - `CHATGPT_AUTO_VERIFICATION_CLICK` (default `true`)
  - `CHATGPT_AUTO_VERIFICATION_CLICK_WAIT_MS` (default `2500`)
- Unusual-activity exponential backoff:
  - `CHATGPT_UNUSUAL_ACTIVITY_BACKOFF` (default `true`)
  - `CHATGPT_UNUSUAL_ACTIVITY_BACKOFF_MAX_SECONDS` (default `7200`)
  - `CHATGPT_UNUSUAL_ACTIVITY_BACKOFF_WINDOW_SECONDS` (default `21600`)
- Worker sleep cycles (human-like breaks):
  - `CHATGPTREST_WORK_CYCLE_SECONDS` (default `7200`)
  - `CHATGPTREST_WORK_SLEEP_MIN_SECONDS` (default `900`)
  - `CHATGPTREST_WORK_SLEEP_MAX_SECONDS` (default `1800`)
  - Notes:
    - Sleep cycles apply only to the `send` worker role (the `wait` worker stays responsive).
    - When the queue has ready `send` work, the sleep cycle is skipped to avoid stalling queued jobs.
    - Disable by setting `CHATGPTREST_WORK_CYCLE_SECONDS=0`.
- IP/profile binding:
  - Keep proxy IP stable with `CHROME_USER_DATA_DIR` (changing IP with old cookies raises risk).
  - If IP must change, clear cookies or use a fresh Chrome profile.

## Restart Chrome (CDP)

When `CHATGPT_CDP_URL` points to local Chrome (default `http://127.0.0.1:9222`), a hung CDP session can make
`chatgpt_web.*` jobs spin in `cooldown` with errors like `BrowserType.connect_over_cdp: Timeout ...`.

Scripts:

```bash
# Stop (best-effort; safe if Chrome is already down)
bash ops/chrome_stop.sh

# Start (idempotent; prints cdp endpoint)
DISPLAY=:99 bash ops/chrome_start.sh
```

## MCP startup failed (`Unexpected content type: None` / handshake failed)

Typical symptom:
- Codex/MCP startup prints:
  - `MCP client for chatgpt_web failed to start ... Unexpected content type: None`
  - or `codex_apps ... https://chatgpt.com/backend-api/wham/apps ... send initialize request`

Do this **before** asking user to relogin:

1) Verify services and ports:
- `systemctl --user status chatgptrest-driver.service chatgptrest-chrome.service --no-pager`
- `ss -ltnpe | rg ':18701|:9222|:9226'`

2) Verify CDP endpoint is a real Chrome DevTools endpoint:
- `curl --noproxy '*' -fsS http://127.0.0.1:<cdp_port>/json/version | jq .webSocketDebuggerUrl`
- Must return non-empty `webSocketDebuggerUrl`.

3) If port is occupied by a non-DevTools listener (very common on `9222`):
- set a dedicated port in `~/.config/chatgptrest/chatgptrest.env`, e.g. `CHROME_DEBUG_PORT=9226`;
- restart:
  - `systemctl --user daemon-reload`
  - `systemctl --user restart chatgptrest-chrome.service chatgptrest-driver.service`
- re-check step (2) on the new port.

4) Clear stale blocked state and re-probe:
- call MCP tool `chatgpt_web_clear_blocked`
- then `chatgpt_web_self_check`
  - `chatgpt_web_self_check` and `chatgpt_web_capture_ui` are safe blocked-state diagnostics: they do not send prompts and remain callable while blocked cooldown is active.
  - In CDP mode, when no explicit conversation URL is requested, these diagnostics now preserve a warm ChatGPT homepage tab instead of always closing it, so the next real turn can reuse the existing page.

5) Only if still blocked after the above, proceed to Cloudflare/login handling.

For `codex_apps` startup failure specifically:
- probe upstream reachability (no prompt send):
  - `curl -I --max-time 10 https://chatgpt.com/backend-api/wham/apps`
- if this fails while local driver is healthy, treat as proxy/upstream issue (mihomo node, DNS, or transient platform outage), not a local login issue.

## Debug: Browser Netlog Capture (ChatGPT Web)

This captures Playwright-level network events into a rotating JSONL log for incident triage (not a TCP packet capture).

Notes:
- Default is off; enable temporarily for flaky UI incidents (e.g., thinking panel shows `Skipping` unexpectedly).
- Privacy: logs include only method + redacted URL + status/error (no headers/body/cookies).
- Scope: only `kind=chatgpt_web.*` tools (does not capture Gemini Web).

Enable (restart the internal driver to apply env):

```bash
export CHATGPT_NETLOG_ENABLED=1
# Optional: keep all debug outputs together
export MCP_DEBUG_DIR=/vol1/1000/projects/ChatgptREST/artifacts/monitor/debug
bash ops/start_driver.sh
```

Log file:
- `artifacts/chatgpt_web_netlog.jsonl` (or `$MCP_DEBUG_DIR/chatgpt_web_netlog.jsonl` if `MCP_DEBUG_DIR` is set)

Rotation:
- `CHATGPT_NETLOG_MAX_BYTES` (default `10000000`)
- `CHATGPT_NETLOG_BACKUP_COUNT` (default `3`)

Filters / redaction:
- `CHATGPT_NETLOG_RESOURCE_TYPES` (default `xhr,fetch,eventsource,websocket`)
- `CHATGPT_NETLOG_HOST_ALLOWLIST` (default `chatgpt.com,ab.chatgpt.com`)
- `CHATGPT_NETLOG_REDACT_QUERY` (default `true`)
- `CHATGPT_NETLOG_REDACT_IDS` (default `true`, masks UUID / long-hex path segments)
- `CHATGPT_NETLOG_LINE_MAX_CHARS` (default `2000`)

Query tips:
- Find `run_id` from `artifacts/jobs/<job_id>/result.json`, then grep:
  - `rg '\"run_id\":\"<run_id>\"' artifacts/chatgpt_web_netlog.jsonl*`
- If you are investigating unexpected thinking skips, look for:
  - `kind=console` with text `[chatgptrest] blocked Answer now click`

Disable / cleanup:
- Set `CHATGPT_NETLOG_ENABLED=0` and restart the driver; delete `artifacts/chatgpt_web_netlog.jsonl*` when done.

Related guardrail (enabled by default):
- `CHATGPT_DISABLE_ANSWER_NOW` (default `true`): blocks clicks on the thinking panel "Answer now" affordance to avoid skipping the thinking phase.

## Debug: CDP Routing Sniff (ChatGPT Web)

When you need to debug cases like "Pro + Extended thinking" selected but the UI appears to fast-path
(no thinking footer / instant answers), a CDP-level sniff can capture the **routing fields** actually
sent to `/backend-api/*`.

Tool:
- `ops/chatgpt_cdp_sniff.py` (sanitized; no cookies/auth headers; does not persist prompt text)

Outputs:
- `artifacts/probe_thinking/<run>/net_events.jsonl` (sanitized request/response metadata)
- `artifacts/probe_thinking/<run>/conversation_posts.jsonl` (whitelisted `request_route.*` + best-effort `response_meta.*`)

Typical usage:

```bash
cd /vol1/1000/projects/ChatgptREST
export CHATGPT_CDP_URL=http://127.0.0.1:9222
python3 ops/chatgpt_cdp_sniff.py --timeout-seconds 900 --max-conversation-posts 1
```

Notes:
- ChatGPT Web may use `/backend-api/f/conversation` (SSE); this tool treats it as a conversation POST.
- This captures only the local CDP Chrome traffic; it cannot capture mobile "Regenerate" traffic.
- Compare `request_route.model` / `request_route.thinking_effort` across a known-good baseline vs a degraded run.

## Thinking-Time Quality Guard (Pro)

For Pro/Extended runs, ChatGPT often shows a footer like `Thought for 17m 9s` under `Pro thinking`.
If `Thought for < 5min`, it usually correlates with degraded generation (e.g., implicit skip / fast-path / UI “Answer now”).

Driver-side observation (no prompt send):
- `CHATGPT_THOUGHT_GUARD_MIN_SECONDS` (default `300`)
- When present, tools attach `thinking_observation` into results (includes `thought_for_present`, `thought_seconds`, `thought_too_short`, `skipping`, `answer_now_visible`).
- Optional evidence capture (off by default): `CHATGPT_THOUGHT_GUARD_CAPTURE_DEBUG=1` attaches `thought_guard_debug_artifacts` (png/html/txt) for incident triage.

Server-side gate (ChatgptREST executor; default: best-effort, no extra prompt send):
- `CHATGPTREST_THOUGHT_GUARD_MIN_SECONDS` (default `300`)
- `CHATGPTREST_THOUGHT_GUARD_AUTO_REGENERATE` (default `false`) triggers a single UI “Regenerate” attempt (no new user prompt).
- Strict mode: require the UI footer to contain a `Thought for Xm Ys` duration (fail-closed on missing observation):
  - `CHATGPTREST_THOUGHT_GUARD_REQUIRE_THOUGHT_FOR` (default `false`)
  - Optional per-marker triggers (defaults keep legacy behavior):
    - `CHATGPTREST_THOUGHT_GUARD_TRIGGER_TOO_SHORT` (default `true`)
    - `CHATGPTREST_THOUGHT_GUARD_TRIGGER_SKIPPING` (default `true`)
    - `CHATGPTREST_THOUGHT_GUARD_TRIGGER_ANSWER_NOW` (default `true`)

Optional (side-effectful) regenerate capability (no new user prompt):
- Driver tools:
  - `chatgpt_web_regenerate` (clicks `Regenerate/重新生成`)
  - `chatgpt_web_refresh` (refresh only)
- Guardrails:
  - `CHATGPT_REGENERATE_STATE_FILE` (default: `state/driver/chatgpt_regenerate_state.json` via `ops/start_driver.sh`)
  - `CHATGPT_REGENERATE_MIN_INTERVAL_SECONDS` (default `1800`)
  - `CHATGPT_REGENERATE_WINDOW_SECONDS` (default `86400`)
  - `CHATGPT_REGENERATE_MAX_PER_WINDOW` (default `3`)
  - `CHATGPT_WAIT_REFRESH_STATE_FILE` (default: `state/driver/chatgpt_wait_refresh_state.json` via `ops/start_driver.sh`)
  - `CHATGPT_WAIT_REFRESH_MIN_INTERVAL_SECONDS` (default `900`)
  - `CHATGPT_WAIT_REFRESH_WINDOW_SECONDS` (default `86400`)
  - `CHATGPT_WAIT_REFRESH_MAX_PER_WINDOW` (default `12`)

Recommendation: land first, enable progressively per `docs/ops_rollout_plan_p0p1p2_safe_enable_20251228.md`.

## Upload Confirmation Guard (ChatGPT Web)

ChatGPT Web UI uploads are occasionally flaky (e.g. request has 5 attachments but the UI only shows 3).
To avoid sending a prompt with missing attachments, the internal driver can enforce a **fail-closed**
upload confirmation.

- `CHATGPT_UPLOAD_REQUIRE_CONFIRM` (default `1` via `ops/start_driver.sh`)
  - `1`: require UI confirmation for each uploaded file; otherwise fail the job (retryable).
  - `0`: legacy best-effort behavior (may proceed even if UI silently drops files).

If you change this env var, restart the internal driver to apply.

## Zip Attachments (ChatGPT Web)

- `.zip` attachments are supported and are uploaded as-is by default.
- If a `.zip` upload is routed into an external connector flow stub (e.g. Adobe Acrobat), disable the Adobe Acrobat App in ChatGPT.

## Health Checks

- REST:

```bash
curl -fsS http://127.0.0.1:18711/healthz
```

Aliases:

```bash
curl -fsS http://127.0.0.1:18711/health
curl -fsS http://127.0.0.1:18711/v1/health
```

- Send pacing (chatgptMCP process):

```bash
curl -sS -X POST http://127.0.0.1:18701/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"chatgpt_web_rate_limit_status","arguments":{}}}' | jq
```

Expected: `min_interval_seconds=61`.

## SQLite: DB Write Unavailable (readonly)

Symptom:
- Worker logs show `sqlite3.OperationalError: attempt to write a readonly database`.
- Jobs can appear stuck in `queued` because the worker cannot `BEGIN IMMEDIATE` to claim or update rows.

Evidence:
- Panic snapshot (best-effort): `state/panic/db_write_unavailable.json`
- Optional autofix report (when enabled): `state/panic/db_write_autofix.json`

Common causes:
- DB directory not writable (SQLite cannot create journal/WAL files).
- WAL/SHM files exist but are not writable by the worker user.
- Disk full / filesystem issues.

Operator actions:
1) Check free space and directory/file permissions under `state/`.
2) If you accept a safe, minimal chmod-based self-heal, enable it on the worker:

```bash
export CHATGPTREST_DB_WRITE_AUTOFIX=1
```

Notes:
- This is an active action and is **disabled by default**. It only adds `u+w` (files) / `u+wx` (dir); it does not remove permissions.
- Prefer enabling progressively per `docs/ops_rollout_plan_p0p1p2_safe_enable_20251228.md`.

## Driver Tab Limits / Stats

The internal driver enforces a concurrent-page cap to prevent tab explosions.

Env knobs:
- `CHATGPT_MAX_CONCURRENT_PAGES` (default `3`)
- `CHATGPT_PAGE_SLOT_TIMEOUT_SECONDS` (default `0`, 0 = wait indefinitely)
- `CHATGPT_TAB_LIMIT_RETRY_SECONDS` (default `300`, returned when limit is hit)

Check current usage:

```bash
curl -sS -X POST http://127.0.0.1:18701/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"chatgpt_web_tab_stats","arguments":{}}}' | jq
```

## Maint Daemon (monitor + evidence packs)

Run the resident maint daemon (no prompt send; bundles incident evidence under artifacts).

By default it also runs an **infra healer**: when jobs are stuck due to CDP/Chrome/driver failures
(e.g. `reason_type=InfraError` / `TargetClosedError` / `CDP connect failed`), it performs a
**drain-guarded** restart of the driver (and starts Chrome if CDP is down), so the same job can
retry and recover to `completed` without client resubmission.

```bash
cd /vol1/1000/projects/ChatgptREST
.venv/bin/python ops/maint_daemon.py
```

Outputs:
- Monitor log: `artifacts/monitor/maint_daemon/maint_YYYYMMDD.jsonl`
- Global Codex memory: `artifacts/monitor/maint_daemon/codex_global_memory.jsonl` + `artifacts/monitor/maint_daemon/codex_global_memory.md`
- Incident packs: `artifacts/monitor/maint_daemon/incidents/<incident_id>/`
- Known issues snapshot: `artifacts/monitor/maint_daemon/incidents/<incident_id>/snapshots/issues_registry.yaml`

Optional (still no prompt send):
- Add `--enable-chatgptmcp-evidence --enable-chatgptmcp-capture-ui` to collect provider-aware `self_check` + UI snapshots on incidents（`chatgpt`/`gemini`/`qwen`）。
- `--enable-ui-canary`（默认开启）会定期跑 `self_check`，并在连续失败达到阈值后创建 `category=ui_canary` incident；失败时可按冷却触发 `capture_ui`。
  - 常用参数：`--ui-canary-providers`、`--ui-canary-every-seconds`、`--ui-canary-fail-threshold`、`--ui-canary-capture-cooldown-seconds`。
  - 输出：`artifacts/monitor/ui_canary/latest.json`（供 orch/guardian 联动）。
- Add `--enable-auto-repair-check` to auto-submit a `repair.check` job per incident and attach `repair_report.json` into the incident pack.
  - Guardrails: global rate limit via `--auto-repair-check-window-seconds` / `--auto-repair-check-max-per-window`.
- Add `--enable-api-autostart` to auto-start the REST API if the `CHATGPTREST_BASE_URL` port is down (safe: no prompt send). MCP adapter option: `CHATGPTREST_MCP_AUTO_START_API=1`.
- Infra healer tuning (enabled by default; disable via `--disable-infra-healer` or `CHATGPTREST_ENABLE_INFRA_HEALER=0`):
  - Rate limits: `--infra-healer-window-seconds` / `--infra-healer-max-per-window` / `--infra-healer-min-interval-seconds`.
- Add `--enable-codex-sre-analyze` to run Codex (read-only) to analyze each incident pack and write `codex/sre_actions.json` + `codex/sre_actions.md`.
  - Guardrails: `--codex-sre-window-seconds` / `--codex-sre-max-per-window` + per-incident `--codex-sre-min-interval-seconds`.
- Add `--enable-codex-sre-autofix` to execute a **whitelisted** subset of low-risk actions from the Codex report (disabled by default; safe-enable).
  - Default allowlist: `restart_chrome,restart_driver` (configure via `--codex-sre-autofix-allow-actions`).
  - Guardrails: `--codex-sre-autofix-window-seconds` / `--codex-sre-autofix-max-per-window` + per-incident `--codex-sre-autofix-max-per-incident`.
- Codex-backed maint fallback（默认开启，可 `--disable-codex-maint-fallback` 关闭）：
  - 当 `codex_sre` 分析失败，或 `codex_sre_autofix` 执行失败时，maint_daemon 会按 incident 维度自动提交一个幂等 `repair.autofix` job（不会发新 prompt）。
  - 产物会自动归档到 incident 包：`snapshots/repair_autofix/repair_autofix_report.json`。
  - Guardrails：`--codex-maint-fallback-window-seconds` / `--codex-maint-fallback-max-per-window` / `--codex-maint-fallback-max-per-incident`。
  - 动作边界：通过 `--codex-maint-fallback-allow-actions` 与 `--codex-maint-fallback-max-risk` 透传给 `repair.autofix`。

Optional (Codex SRE, read-only):

```bash
cd /vol1/1000/projects/ChatgptREST
ops/codex_sre_analyze_incident.py artifacts/monitor/maint_daemon/incidents/<incident_id>
```

## Repair Check (on-demand diagnostics)

Submit a diagnostic job (no prompt send; writes `repair_report.json` under the job artifacts):

```bash
curl -sS -X POST http://127.0.0.1:18711/v1/jobs \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: repair-1' \
  -d '{"kind":"repair.check","input":{"job_id":"<optional_target_job_id>","symptom":"cloudflare / driver down / 409 idempotency"},"params":{"mode":"quick","probe_driver":true,"timeout_seconds":60}}' | jq
```

Recommended: run a dedicated repair worker so diagnostics are not delayed by send pacing:

```bash
cd /vol1/1000/projects/ChatgptREST
ops/start_worker.sh all repair.
```

Recommended for incident-scoped repair coordination (client agent -> runner -> downstream repair jobs):

```bash
cd /vol1/1000/projects/ChatgptREST
ops/start_sre_runner.sh
```

Behavior:
- Consumes `kind=sre.fix_request` (and compatibility alias `sre.diagnose`) through a dedicated `sre.` worker prefix.
- Keeps one Codex lane per incident/job/symptom under `state/sre_lanes/<lane_id>/`.
- Resumes only within the same lane; there is no global long-lived Codex brain.
- Optionally queries GitNexus CLI for code-graph context when `ops/start_sre_runner.sh` is used.

Key env:
- `CHATGPTREST_SRE_LANES_DIR` (default `state/sre_lanes`)
- `CHATGPTREST_SRE_ENABLE_GITNEXUS` (default `1` in `ops/start_sre_runner.sh`)
- `CHATGPTREST_SRE_GITNEXUS_QUERY_CMD` (default `/usr/bin/env npm_config_cache=/tmp/chatgptrest-gitnexus-npx-cache npx --yes gitnexus query`)
- `CHATGPTREST_SRE_GITNEXUS_TIMEOUT_SECONDS` (default `20`)
- Per job request knobs still live in `params`: `route_mode`, `open_pr_mode`, `runtime_max_risk`, `runtime_apply_actions`

Optional (Codex/MCP): auto-submit `repair.check` when a waited job ends in `error/blocked/cooldown/needs_followup`:
- Use MCP tool `chatgptrest_job_wait` with `auto_repair_check=true` (it attaches `auto_repair_check.repair_job_id` into the returned job dict).
  - Guardrails (client-side MCP): `CHATGPTREST_MCP_AUTO_REPAIR_CHECK_WINDOW_SECONDS` (default `300`) + `CHATGPTREST_MCP_AUTO_REPAIR_CHECK_MAX_PER_WINDOW` (default `5`).
  - `chatgptrest_job_wait` keeps waiting through `status=cooldown` until the job becomes terminal (`completed/error/canceled`) or the effective foreground timeout elapses.

Optional (Codex-driven autofix, no prompt send):
- `chatgptrest_job_wait` can auto-submit `kind=repair.autofix` for ask jobs that enter `status=cooldown/error` with a non-empty `reason_type` (excluding `InProgress`), to run Codex analysis + execute a guarded action allowlist (e.g. `refresh/regenerate/restart_driver/restart_chrome`).
  - Enable/disable: `auto_codex_autofix` (default `true`).
  - Guardrails (client-side MCP): `CHATGPTREST_MCP_AUTO_AUTOFIX_WINDOW_SECONDS` (default `1800`), `CHATGPTREST_MCP_AUTO_AUTOFIX_MAX_PER_WINDOW` (default `3`), `CHATGPTREST_MCP_AUTO_AUTOFIX_MIN_INTERVAL_SECONDS` (default `300`).
  - Safety: restart actions are skipped when any non-`repair.*` job is `in_progress` in `phase=send` (drain guard).

Recommended for Codex parallel work (non-blocking wait):
- Start background wait for an existing job:
  - `chatgptrest_job_wait_background_start(job_id=..., notify_controller=true, notify_done=true)`
- Query the background waiter:
  - `chatgptrest_job_wait_background_get(watch_id=...|job_id=...)`
- List active/background waiters:
  - `chatgptrest_job_wait_background_list(include_done=false)`
- Cancel a watcher:
  - `chatgptrest_job_wait_background_cancel(watch_id=...|job_id=...)`

Notes:
- `chatgptrest_job_wait` now has long-wait protection by default:
  - long `timeout_seconds` can auto-handoff to background waiter and return immediately with `watch_id` (`wait_mode=background`);
  - foreground waits are capped by `CHATGPTREST_MCP_WAIT_MAX_FOREGROUND_SECONDS` (default `90`) to avoid long client blocking.
- To fully disable MCP foreground wait loops:
  - set `CHATGPTREST_MCP_WAIT_FOREGROUND_ENABLED=0` (or `CHATGPTREST_DISABLE_FOREGROUND_WAIT=1`);
  - `chatgptrest_job_wait` will always use background watcher and return immediately (`wait_mode=background`, `foreground_disabled=true`).
- Auto-handoff knobs:
  - `CHATGPTREST_MCP_WAIT_AUTO_BACKGROUND` (default `true`)
  - `CHATGPTREST_MCP_WAIT_AUTO_BACKGROUND_THRESHOLD_SECONDS` (default follows foreground cap)
- `chatgptrest_job_wait_background_*` 是 MCP 进程内 watcher，不会出现在 Codex 的“Background terminals”列表里；请用 `..._background_get/list` 看运行状态与心跳字段（`heartbeat_at/poll_count/last_job_status`）。
- Background wait state is in-memory (MCP process scope). Persisted source of truth remains REST job status + artifacts.
- MCP 重启后 watcher 内存会丢失；默认会在 `chatgptrest_job_wait_background_get(job_id=...)` 时自动恢复 watcher（`auto_resumed=true`）。
- Finished watchers are retained for `CHATGPTREST_MCP_BACKGROUND_WAIT_RETENTION_SECONDS` (default `86400`).

Optional (server-side, worker-triggered Codex autofix, no prompt send):
- When an ask job enters retryable `status=cooldown/blocked` due to infra/UI errors (excluding `reason_type=InProgress`), workers auto-submit `kind=repair.autofix` and attach a `job_events` marker on the original job (`type=auto_autofix_submitted`, includes `repair_job_id`).
- `wait` 阶段卡死也会升级：`status=needs_followup` 且 `reason_type in {WaitNoProgressTimeout, WaitNoThreadUrlTimeout}` 时，workers 同样可触发 `repair.autofix`（用于“Web 已出答案但 wait 未收口”场景）。
- Knobs:
  - `CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX` (default `false`)
  - `CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_WINDOW_SECONDS` (default `1800`): per-target idempotency bucket
  - `CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_MIN_INTERVAL_SECONDS` (default `300`): global DB rate limit
  - `CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_TIMEOUT_SECONDS` (default `600`)
  - `CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_MAX_RISK` (default `low`)
  - `CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_APPLY_ACTIONS` (default `true`)
  - `CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_MODEL` (optional)

Repair Agent policy reference:
- `docs/repair_agent_playbook.md`（权限边界、动作顺序、禁行规则；`repair.autofix` prompt 已注入该 playbook）。

## Smoke Test (human-like)

Use the built-in script (avoids obvious “测试:” prompts):

```bash
cd /vol1/1000/projects/ChatgptREST
.venv/bin/python ops/smoke_test_chatgpt_auto.py --count 1
```

## Cloudflare / Blocked / Cooldown

Symptoms:
- ChatgptREST jobs return `blocked/cooldown` with a reason.
- Driver `chatgpt_web_blocked_status` reports `blocked=true`.
  - In this repo we default it to `projects/ChatgptREST/state/driver/chatgpt_blocked_state.json` via `ops/start_driver.sh` (override via `CHATGPT_BLOCKED_STATE_FILE`).

Steps:
1) Confirm driver is on the correct CDP Chrome (see section above; `/json/version` must be valid).
2) Clear blocked state in the driver:
   - call `chatgpt_web_clear_blocked`
3) Run `chatgpt_web_self_check` on the same driver session.
4) If verification page is present:
   - driver will attempt auto-click (`CHATGPT_AUTO_VERIFICATION_CLICK=1`, default);
   - if auto-click fails, use noVNC on the **same** Chrome profile to finish verification/login.
5) Retry by polling the existing ChatgptREST job (`/wait`) or resubmitting only if the first prompt was not sent.

Proxy correlation:
- On `blocked/cooldown`, ChatgptREST records a mihomo delay snapshot into:
  - `artifacts/jobs/<job_id>/mihomo_delay_snapshot.json`
  - job events (`mihomo_delay_snapshot`)
- Daily proxy delay log (default):
  - `artifacts/monitor/mihomo_delay/mihomo_delay_YYYYMMDD.jsonl`

## Proxy Degraded (mihomo 504 / timeouts)

If `mihomo_delay_*.jsonl` shows sustained timeouts (e.g. repeated `HTTP 504 {"message":"Timeout"}`), maint_daemon will create a `category=proxy` incident pack:

- Find the creation event in: `artifacts/monitor/maint_daemon/maint_YYYYMMDD.jsonl` (`type=proxy_incident_created`).
- Open the incident summary: `artifacts/monitor/maint_daemon/incidents/<incident_id>/summary.md`.
- Key evidence files:
  - `artifacts/monitor/maint_daemon/incidents/<incident_id>/snapshots/proxy_health_summary.json`
  - `artifacts/monitor/maint_daemon/incidents/<incident_id>/snapshots/proxy_switch_suggestions.json`

By default, the delay probe tracks business paths:
- `🤖 ChatGPT` → `https://chatgpt.com/cdn-cgi/trace`
- `💻 Codex` → `https://api.openai.com/v1/models`

Override via env:
- `MIHOMO_DELAY_TARGETS=🤖 ChatGPT=https://chatgpt.com/cdn-cgi/trace,💻 Codex=https://api.openai.com/v1/models`

Manual node switch (mihomo API, no auto-switch in server):
- `PUT http://127.0.0.1:9090/proxies/<GROUP>` with body `{"name":"<NODE>"}` (or use mihomo UI).

## “Error in message stream” Duplication Prevention

If the prompt was sent but answer retrieval fails with a short assistant error (e.g. `"Error in message stream"`):
- ChatgptREST treats it as transient and best-effort waits in-place (same conversation) instead of finalizing as a completed answer.
- If still unresolved after `max_wait_seconds`, the job becomes retryable `cooldown` with `reason_type=TransientAssistantError`.

Two-phase mode:
- If a job stays `in_progress`, its `phase` becomes `wait`, and the wait worker continues without re-sending the prompt.

## Duplicate Prompt Guard (same conversation)

If a client accidentally submits the *same* follow-up prompt twice (often by retrying with a different `Idempotency-Key`),
the internal driver will best-effort prevent a second user message:

- It compares the current `question` with the **last user message** already visible in the conversation DOM.
- If they match, it **skips sending** and resumes waiting for the existing turn’s answer (no new prompt sent).

Knob:
- `CHATGPT_DUPLICATE_PROMPT_GUARD` (default `true`)

Scope:
- Only applies when `conversation_url` is provided (follow-up).
- Disabled for attachment uploads (`file_paths`) to avoid skipping required uploads.

## Conversation Single-Flight (same conversation)

Goal: avoid “user messages rapid-fire” in a single ChatGPT conversation (wind-control risk).

Behavior (REST `POST /v1/jobs`, `kind=chatgpt_web.ask`):
- If the request targets an existing conversation (`input.conversation_url` or `input.parent_job_id` resolves to one),
  and there is already an active ask job in that conversation (`status in queued/in_progress`),
  the server returns **HTTP 409** with `detail.error="conversation_busy"` and `detail.active_job_id`.
- To explicitly queue anyway, set `params.allow_queue=true`.

Worker-side enforcement:
- Even when queued, send workers enforce “one in-progress ask per conversation” (by `conversation_id`) so prompts cannot overlap.

Knob:
- `CHATGPTREST_CONVERSATION_SINGLE_FLIGHT` (default `true`)

## Attachment Send Stuck (no conversation_url)

If an attachment upload or new-chat send gets stuck and returns `status=in_progress` without a `conversation_url`,
ChatgptREST keeps the job `in_progress` and requeues into `phase=wait` while polling driver idempotency until the URL appears (no prompt resend).

ChatGPT attachment upload note:
- The ChatGPT driver prefers setting the composer `input[type=file]` directly (avoid fragile “+ menu → Upload file” selectors).
- Upload confirmation is best-effort (filenames are often truncated in the UI):
  - `CHATGPT_UPLOAD_CONFIRM_TIMEOUT_MS` (default `60000`)
- If a transient UI/infra error happens **before** the prompt is sent, the driver returns `status=cooldown` (not `error`) with `retry_after_seconds` so the same job can auto-retry.
  - Knob: `CHATGPT_UNSENT_TRANSIENT_RETRY_AFTER_SECONDS` (default `30`).
- Send-stage retry extension guardrails (prevent endless loops):
  - `CHATGPTREST_RETRYABLE_SEND_EXTEND_MAX_ATTEMPTS` (default `true`)
  - `CHATGPTREST_RETRYABLE_SEND_ATTEMPTS_CAP` (default `20`)
  - `CHATGPTREST_RETRYABLE_SEND_MAX_EXTENSIONS` (default `1`)
  - For sticky upload-closed signatures (`TargetClosedError` + `set_input_files`/`input[type=file]`), the server now **skips** further max-attempt extension and finalizes with `MaxAttemptsExceeded` (`guard=sticky_upload_surface_closed`) plus event `max_attempts_extension_skipped`.
    This avoids “same error forever + max_attempts keeps growing”.

Knobs:
- `CHATGPTREST_DEFAULT_SEND_TIMEOUT_SECONDS` (default `180`): caps how long the send stage waits before yielding to the wait phase.

Client guidance: do **not** “retry by re-asking” with a new idempotency key (which creates duplicate user messages). Prefer `/wait`, then `/answer`.

## Answer Quality Cross-check (offline)

To verify that the saved `answer.*` is consistent with the exported conversation (without any extra UI calls), run:

```bash
cd /vol1/1000/projects/ChatgptREST
.venv/bin/python ops/verify_job_outputs.py --job-id <job_id>
```

It writes:
- `artifacts/jobs/<job_id>/verify_report.json`
- `artifacts/jobs/<job_id>/verify_report.md`

Focus on warnings like: `unbalanced_fences`, `tool_answer_truncated_not_rehydrated`, `answer_export_low_similarity`.

## Client Cutover (high level)

Goal: clients stop calling chatgptMCP’s `chatgpt_web_*` directly.

- For REST clients: use `POST /v1/jobs` + `/wait` + `/answer`.
- For Codex/Claude Code/Antigravity: point MCP to ChatgptREST public agent MCP (`http://127.0.0.1:18712/mcp`) and use `advisor_agent_*` tools only.
- Do not configure other coding agents to call ChatgptREST REST endpoints directly when the public MCP is available.
- Prefer the systemd-managed `chatgptrest-mcp.service` or `ops/start_mcp.sh`; both load env and the public MCP entrypoint now fail-fast if `OPENMIND_API_KEY` and `CHATGPTREST_API_TOKEN` are both missing.
- Audit known coding-agent configs and repair Antigravity drift in place with `python3 ops/check_public_mcp_client_configs.py --fix`.
- Keep the admin MCP (`http://127.0.0.1:18715/mcp`) for ops/debug clients that still need the legacy broad surface.

## Disk / Artifacts Cleanup

Artifacts can grow without bound on long-running hosts. Cleanup old terminal job directories:

```bash
cd /vol1/1000/projects/ChatgptREST
.venv/bin/python ops/cleanup_artifacts.py --days 14 --dry-run
.venv/bin/python ops/cleanup_artifacts.py --days 14
```

`maint_daemon/maint_*.jsonl` 的预算治理先走 dry-run，不直接删文件：

```bash
cd /vol1/1000/projects/ChatgptREST
.venv/bin/python ops/maint_daemon_jsonl_cleanup.py
```

默认输出到：

- `artifacts/monitor/reports/maint_daemon_jsonl_cleanup/<timestamp>/inventory_before.json`
- `artifacts/monitor/reports/maint_daemon_jsonl_cleanup/<timestamp>/inventory_before.md`
- `artifacts/monitor/reports/maint_daemon_jsonl_cleanup/<timestamp>/compression_sample.json`
- `artifacts/monitor/reports/maint_daemon_jsonl_cleanup/<timestamp>/dry_run_plan.json`
- `artifacts/monitor/reports/maint_daemon_jsonl_cleanup/<timestamp>/dry_run_plan.md`

说明：

- 当前工具只做 dry-run，不执行压缩、删除、迁移。
- 默认口径对齐 `docs/ops/2026-03-25_maint_daemon_jsonl_cleanup_execution_plan_v1.md`：
  - 最新两个日包保护
  - 少量 closed 日包保 raw
  - 中间窗口投影为 `would_compress`
  - 更老窗口投影为 `would_summarize_only`

## Incidents Cleanup (stale)

The incident table is append-heavy; old incidents can linger as `status=open` even when no longer recurring.

Resolve incidents that have not been seen recently (dry-run by default):

```bash
cd /vol1/1000/projects/ChatgptREST
.venv/bin/python ops/incidents_cleanup.py --older-than-days 14 --limit 200
.venv/bin/python ops/incidents_cleanup.py --older-than-days 14 --limit 200 --apply
```
