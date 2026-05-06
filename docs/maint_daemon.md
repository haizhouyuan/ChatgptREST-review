#!/usr/bin/env markdown
# maint_daemon（常驻维护工程师）设计草案

目标：把 `ChatgptREST + Driver + Chrome/CDP + mihomo` 这套链路做成“**可观测 + 可自愈 + 可复盘**”的服务，而不是靠人工盯着 terminal。

约束（强约束）：
- **不做 Cloudflare/验证码绕过**：出现 challenge/blocked，只做“收证据 + 保护性暂停 + 提醒人工登录/验证”。
- **不额外制造风控风险**：稳态只读观测；可选 canary 低频、拟人化、可关；所有“发送 prompt”的动作仍受服务端 `61s` 节流约束。
- **客户端省心**：client 只 `POST /v1/jobs` → `/wait` → `/answer`；并发/节流/重试/证据收集尽量在 server 侧完成。

## 当前落地状态（2026-02-21）

- 已落地周期 `ui_canary`（默认开启）：按 provider(`chatgpt/gemini`) 跑 `self_check`；仅当 `CHATGPTREST_QWEN_ENABLED=1` 或显式把 `qwen` 写进 `CHATGPTREST_UI_CANARY_PROVIDERS` 时才会包含 Qwen。连续失败触发 `category=ui_canary` incident。
- 失败冷却抓图：`capture_ui` 按冷却执行，不发 prompt；总览写入 `artifacts/monitor/ui_canary/latest.json`。
- orch/guardian 联动：`openclaw_orch_agent` 与 `openclaw_guardian` 默认消费 ui_canary 报告与近期 incidents 做 `needs_attention` 判定。
- 仍遵循 safe-enable：主动修改状态的动作（重启、autofix）默认受限频与护栏约束。

## 一、核心闭环（检测 → 证据 → 自愈 → 升级）

维护进程按“事件驱动 + 状态机”设计：
- **Observers（只读）**：持续产出健康/异常事件（jobs、blocked_state、CDP、proxy、资源）。
- **Correlator**：把短时间内的事件聚合成一次 Incident（避免通知风暴）。
- **Policy Engine（FSM）**：决定是否收证据、是否执行低风险修复、是否暂停、是否升级到 Codex 分析。
- **Evidence Packer**：落盘事故包（可复盘、可交给 Codex 诊断）。
- **Remediator**：执行动作（有护栏、限次、熔断）。
- **Notifier**：发通知/落日志（tmux、stdout、文件、Webhook 可选）。

建议状态机（MVP）：
- `HEALTHY` / `DEGRADED` / `RECOVERING` / `BLOCKED` / `PAUSED` / `MANUAL_REQUIRED`

## 二、观测项（Observers）

### 1) ChatgptREST Observer
- DB：`jobs` / `job_events`（已存在）
- 重点信号：
  - `status=blocked/cooldown/needs_followup/error/canceled`
  - `in_progress` 超时（例如 > `timeout_seconds + grace`）
  - 反复出现的 `TransientAssistantError` / `Error in message stream`
  - 队列积压（`queue_position/estimated_wait_seconds` 持续高）

### 2) Driver / UI Observer（尽量不发 prompt）
- 读：`projects/ChatgptREST/state/driver/chatgpt_blocked_state.json`（或 `CHATGPT_BLOCKED_STATE_FILE`）
- 调：`chatgpt_web_self_check` / `chatgpt_web_blocked_status` / `chatgpt_web_capture_ui`（只在异常时触发）
- 可选：`chatgpt_web_tab_stats`（tab 上限/占用情况）

### 3) CDP / Chrome Observer
- 读：`http://127.0.0.1:9222/json/version`（CDP 健康探针）
- 读：Chrome PID 文件（`projects/ChatgptREST/.run/chrome.pid` 或 `projects/chatgptMCP/.run/chrome.pid`）+ 进程是否存活
- 资源：Chrome CPU/Mem（粗略）

### 4) mihomo / 网络 Observer
- 读：`artifacts/monitor/mihomo_delay/mihomo_delay_YYYYMMDD.jsonl`（已存在）
- 重点信号：
  - 最近 N 次 delay snapshot 持续 `ok=false`
  - 延迟尖刺/超时（例如连续 3 次超时）
- 自动事故包（proxy incident）：
  - 若同一 `(group, selected)` 满足 `consecutive_failures >= proxy-incident-min-consecutive-failures`，maint_daemon 会创建 `category=proxy` 的 incident pack（不发 prompt、不自动切节点）。
  - 典型证据文件（见 `artifacts/monitor/maint_daemon/incidents/<incident_id>/snapshots/`）：
    - `mihomo_delay_last.json` / `mihomo_delay_recent.json`
    - `proxy_health_summary.json`（包含 streak + last_ok_age + baseline OK 延迟统计）
    - `mihomo_proxies_group.json`（从 mihomo `/proxies` 抽取 group/selected 的结构化信息；需要 mihomo controller 可访问）
    - `mihomo_candidate_probes.json` / `proxy_switch_suggestions.json`（对少量候选节点做 `/delay` 诊断，仅建议人工切换）
  - 人类可读摘要：`artifacts/monitor/maint_daemon/incidents/<incident_id>/summary.md`
- 建议：用 `MIHOMO_DELAY_TARGETS` 做“按业务分组”的轻量探针（已支持），例如：
  - `MIHOMO_DELAY_TARGETS=🤖 ChatGPT=https://chatgpt.com/cdn-cgi/trace,💻 Codex=https://api.openai.com/v1/models`
  - `MIHOMO_DELAY_URL` 仅作为 fallback（某些组未配置 target 时使用）

### 5) OS 资源 Observer（可选）
- 磁盘剩余 / fd / mem pressure（避免“磁盘满→落盘失败→一切看起来像风控”）

## 三、事故包（Evidence Pack）落盘规范

建议目录（默认 under `CHATGPTREST_ARTIFACTS_DIR`）：

```
artifacts/
  monitor/
    maint_daemon/
      maint_YYYYMMDD.jsonl
      codex_global_memory.jsonl
      codex_global_memory.md
      incidents/
        <incident_id>/
          manifest.json
          summary.md
          snapshots/
            chatgptrest_job.json
            job_events.json
            issues_registry.yaml
            blocked_state.json
            mihomo_delay_last.json
            cdp_version.json
          job_artifacts/
            request.json
            answer.md
            conversation.json
          actions.jsonl
          codex/
            prompt.txt
            response.md
```

`manifest.json` 建议字段：
- `incident_id, signature, first_seen_ts, last_seen_ts, severity`
- `related_job_ids[]`
- `env`: chatgptrest/chagptmcp/chrome/mihomo 关键配置摘要（脱敏）
- `actions[]`: 每个动作的 `attempt_id / ok / error / elapsed_ms / guardrail_reason`

## 四、自动修复动作（Remediator）与护栏

MVP 只做**低风险**动作（默认开启）：
- `capture_ui`（异常时抓 UI 快照）
- `self_check`（异常时采集自检结果）
- “保护性暂停”：进入 `PAUSED`，并写明 `manual_required_reason`

逐步增强（默认关闭，需显式开关）：
- CDP 不通且确认 Chrome 崩：执行 `projects/ChatgptREST/ops/chrome_start.sh` 重启 Chrome（限次、冷却；legacy 仍可用 `projects/chatgptMCP/ops/chrome_start.sh`）
- driver 进程异常：执行 `projects/ChatgptREST/ops/start_driver.sh` 重启 driver（限次、冷却；legacy 仍可用 `projects/chatgptMCP/ops/start_chatgpt_web_mcp_http.sh`）
- Tab 过多：优先“重启 Chrome”而不是逐 tab 清理（更稳定、实现成本低）

护栏（必须）：
- 每类动作 `max_attempts_per_hour` + `cooldown_seconds`
- 连续失败进入 `PAUSED`，避免重启风暴/刷 UI 风暴
- blocked/challenge 时不做刷新循环（最多 1 次“证据采集刷新”，其余交人工）

## 五、canary（可选，拟人化，低频）

原则：能不用就不用；只在“健康信号不足”或“疑似 silent failure”时启用，并且低频。

推荐：
- 频率：`>= 6h`（或仅在从 `RECOVERING` 回 `HEALTHY` 前做一次确认）
- 提示词：像真实用户（例：`“深圳明天大概多少度？给我一句话就行。”`）
- 只校验：是否能产出“足够长的自然语言”，不追求准确率

## 六、Codex 升级协同（codexsdk）

触发条件（去重、限频）：
- 同一 `signature` 在 24h 内重复出现且自动修复无效
- 或出现“需要改 selector / 改解析 / 改协议”的明确迹象

输入：Incident evidence pack 路径（zip 或目录），让 Codex 产出：
- root cause 假设（带置信度）
- 最小修复 patch 建议（按 repo 分发：ChatgptREST / chatgptMCP）
- 回归验证清单

注意：Codex 升级本质是“自动写工单/补丁建议”，不要让它自动 `git push` 或自动重启生产（除非你明确允许）。

### 结构化动作建议（read-only）

本仓库提供一个“读事故包→产出结构化动作建议”的最小工具（不执行动作）：

- Schema：`ops/schemas/codex_sre_actions.schema.json`
- 脚本：`ops/codex_sre_analyze_incident.py`

示例：

```bash
cd /vol1/1000/projects/ChatgptREST
ops/codex_sre_analyze_incident.py artifacts/monitor/maint_daemon/incidents/<incident_id>
```

输出：`.../<incident_id>/codex/sre_actions.json`

脚本内部使用 `codex exec --sandbox read-only --output-schema ...`，并强制写入硬约束：
- 不做 ChatGPT Web smoke test prompt
- 不改 61s send pacing
- 优先只读动作；副作用动作（refresh/regenerate/restart）必须带 guardrails

### 与 repair.check / Thought Guard 的衔接

- `kind=repair.check`（不发 prompt）可作为“即时诊断”入口，补齐 DB/blocked/CDP/driver probe，并生成 `repair_report.json`。
- `kind=repair.autofix`（不发 prompt）执行策略统一遵循 `docs/repair_agent_playbook.md`（权限边界、动作顺序、禁行规则）。
- worker 侧自动升级已覆盖 `needs_followup + WaitNoProgressTimeout/WaitNoThreadUrlTimeout`，用于 wait 卡住时自动触发 `repair.autofix` 收口。
- Pro Thinking 质量守护信号（不含思维链）：
  - driver 的 `thinking_observation`（`thought_seconds/skipping/answer_now_visible`）
  - worker 事件：`thought_guard_abnormal` / `thought_guard_regenerated`

这些信号建议纳入 incident 的 signature/去重逻辑，用于快速定位“登录态掉了”与“thinking 被跳过”两类事故。

## 七、当前已存在的底座（可复用）

- `ops/monitor_chatgptrest.py`：DB events + blocked_state + mihomo delay tail（JSONL）
- `ops/mihomo_delay_snapshot.py` / `ops/mihomo_delay_daemon.sh`：代理延迟测量与日志
- `docs/runbook.md`：运维手册（服务启停/blocked 处理/烟囱测试）

## 八、已发现的真实问题（已修复）

1) 回答截断：
- 症状：`answer.md` 明显短于 `conversation.json` 中的 assistant 文本。
- 修复：worker 在完成后优先用 `conversation_export` 进行 **answer ↔ conversation 对齐**，并做 DOM 文本归一化（`Copy code` → fenced code）。

## 九、1 周实施计划（按天）

- Day 1：确定目录规范 + Incident 数据模型 + JSONL 事件格式（不写动作）
- Day 2：实现 maint_daemon（只读监控 + 事故包落盘），加入去重/合并逻辑
- Day 3：接入 driver 自检/抓 UI（异常触发），把证据打全
- Day 4：加“卡死/断连”检测（CDP 探针 + Chrome PID），引入“保护性暂停”
- Day 5：加低风险自愈（Chrome/MCP 重启：限次+冷却+熔断），完善 runbook
- Day 6：接入 codexsdk（可选）：把事故包喂给 Codex 输出 patch 建议（限频）
- Day 7：压测/演练：模拟 chrome 崩/代理超时/selector 失效，校验闭环与护栏

## 十、快速上手（当前实现）

本仓库已提供一个可直接运行的最小实现（监控 + incident evidence packs）：

```bash
cd /vol1/1000/projects/ChatgptREST
.venv/bin/python ops/maint_daemon.py
```

常用开关：
- `--enable-chatgptmcp-evidence`：incident 时采集 `blocked_status/rate_limit_status/self_check`（不发送 prompt；适用于内部 driver 或外部 chatgptMCP）
- `--enable-chatgptmcp-capture-ui`：incident 时抓 UI 快照（不发送 prompt；适用于内部 driver 或外部 chatgptMCP）
- `--enable-chrome-autostart`：CDP 探针失败时尝试执行 `projects/ChatgptREST/ops/chrome_start.sh`（安全：已在跑则不动；外部 chatgptMCP 可传 `--chatgptmcp-root` 指向其 repo）
- `--enable-infra-healer`：**默认开启**。当 Job 因 CDP/Chrome/driver 异常（如 `InfraError` / `TargetClosedError` / `CDP connect failed`）进入 `cooldown/error`，maint_daemon 会在 **drain guard** 通过时尝试：
  - 先（必要时）启动 Chrome（CDP down）
  - 再重启 driver（安全：端口已开且 self_check OK 时会跳过）
  - 可用 `--disable-infra-healer` 或 `CHATGPTREST_ENABLE_INFRA_HEALER=0` 关闭；限频参数见 `--infra-healer-*`。
- `--enable-auto-repair-check`：incident 时自动提交 `kind=repair.check` 诊断作业（不发送 prompt），并把 `repair_report.json` 归档到事故包
  - 全局限流：`--auto-repair-check-window-seconds` / `--auto-repair-check-max-per-window`（避免异常风暴/自循环）
- `--enable-codex-sre-analyze`：incident 时自动运行 Codex（read-only）分析事故包，落盘 `codex/sre_actions.json` + `codex/sre_actions.md`
  - 全局限流：`--codex-sre-window-seconds` / `--codex-sre-max-per-window`，以及每个 incident 的最小间隔：`--codex-sre-min-interval-seconds`
- `--enable-codex-sre-autofix`：按 Codex 报告执行**白名单**低风险动作（默认关闭；safe-enable）
  - 允许动作：`--codex-sre-autofix-allow-actions`（默认 `restart_chrome,restart_driver`）
  - 全局限流：`--codex-sre-autofix-window-seconds` / `--codex-sre-autofix-max-per-window`，以及每个 incident 限次：`--codex-sre-autofix-max-per-incident`
  - 护栏：若 DB 中存在 `status=in_progress && phase=send` 的非 `repair.*` 作业，则跳过 `restart_chrome/restart_driver`（避免打断正在发送 prompt）。
- 一键启用：`ops/systemd/enable_maint_self_heal.sh` 会同时打开 maint daemon guarded autofix 和 worker auto-submit，并把 API/MCP/worker/maint 统一对齐到同一个 runtime checkout；共享 `state/` / `artifacts/` 仍留在主仓（写入对应的 systemd drop-in / env）。
- `--enable-codex-maint-fallback`：当 `codex_sre` 分析失败或 `codex_sre_autofix` 失败时，自动提交一个幂等 `repair.autofix` 作业作为二级兜底（默认开启，可关闭）。
  - 参数：`--codex-maint-fallback-allow-actions`、`--codex-maint-fallback-max-risk`、`--codex-maint-fallback-timeout-seconds`
  - 限流：`--codex-maint-fallback-window-seconds` / `--codex-maint-fallback-max-per-window` / `--codex-maint-fallback-max-per-incident`
  - 归档：成功后会把 `repair_autofix_report.json` 自动归档到 incident 包 `snapshots/repair_autofix/`
- `--incident-auto-resolve-after-hours`：自动把超过 TTL 未再出现的 incident 标为 resolved（默认 72h；0 关闭）；频率与批量上限见 `--incident-auto-resolve-every-seconds/--incident-auto-resolve-max-per-run`
- `--enable-issues-registry-watch`：监控 `docs/issues_registry.yaml` 变更并同步到所有 open incident pack（写入 `snapshots/issues_registry.yaml`）；可触发对 open incidents 的 Codex 复审（受 `--codex-sre-*` 限频）
- `--enable-codex-global-memory`：维护全局“可审计记忆”文件 `codex_global_memory.jsonl` + `codex_global_memory.md`（默认开启；可用 `--disable-codex-global-memory` 关闭）；每次 Codex 分析后追加一条 record，并把 digest 快照到 incident pack 的 `snapshots/codex_global_memory.md`（注入 Codex prompt）
  - `maintagent bootstrap memory`：若本机存在 `/vol1/maint/exports/maintagent_memory_packet_*.json`（或显式配置 `CHATGPTREST_MAINT_BOOTSTRAP_MEMORY_PACKET`），maint daemon 会把这份机器/工作区快照压缩成 `Maintagent Bootstrap Memory` 段，合并进 `codex_global_memory.md` 与 incident snapshot。这样 Codex 在诊断时能看到机器基线、工作区规模、已知漂移和 refresh 触发条件，而不是只看到故障模式。
  - stale 判定：默认 `168h`，可通过 `CHATGPTREST_MAINT_BOOTSTRAP_MEMORY_STALE_HOURS` 调整；记忆包过旧时会继续注入，但标记为 `stale` 供诊断时降权。
  - 降级行为：如果记忆包缺失或损坏，maint daemon 仍保持原有 incident/global memory 行为，只是不注入 bootstrap facts。


systemd user service 模板：`ops/systemd/chatgptrest-maint-daemon.service`
