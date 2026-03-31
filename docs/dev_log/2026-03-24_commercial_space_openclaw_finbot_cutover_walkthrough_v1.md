# 商业航天切到 OpenClaw Finbot walkthrough v1

## 做了什么

### 1. 先确认现有 OpenClaw/finbot 基座

核对了以下事实：

- `ops/openclaw_autoorch.py` 已明确把 `finbot` 作为 canonical OpenClaw investment-research scout。
- `ops/openclaw_finbot.py` 已有 `theme-batch-run` / `daily-work` 等现成入口。
- `config/finbot_theme_catalog.json` 已包含 `commercial_space` 主题。
- `ops/controller_lane_wrapper.py` + `ops/controller_lane_continuity.py` + `ops/openclaw_runtime_guard.py` 已能提供 lane heartbeat / run state / artifact 指针。

### 2. 补单主题入口，避免再依赖 batch 顺序

做了两处最小改动：

- `chatgptrest/finbot.py`
  - `theme_batch_run(..., theme_slug=...)`
- `ops/openclaw_finbot.py`
  - `theme-run --theme-slug commercial_space`

这样商业航天可以被单独执行，而不是靠 `theme-batch-run --limit 5` 间接命中。

### 3. 给商业航天注册独立 lane

在 `config/controller_lanes.json` 增加：

- `lane_id=finbot-commercial-space`
- `lane_kind=finbot`
- `purpose=commercial space theme run`

并执行：

```bash
python3 ops/controller_lane_continuity.py sync-manifest --manifest-path config/controller_lanes.json
```

### 4. 遇到的真实阻断与修复

第一次执行 `theme-run --theme-slug commercial_space` 失败，根因不是 OpenClaw/finbot，而是 `finagent` 上游兼容层断了：

- `run_event_mining_theme_suite.py`
- `finagent.event_replay -> finagent.views`
- `finagent.views` 仍从 `finagent.graph` 导入：
  - `build_graph_from_db`
  - `detect_conflicts`
  - `find_broken_support_chains`

但 `finagent.graph.__init__` 已不再导出这些符号。

修复方式是一个最小 shim：

- `finagent/graph/__init__.py`
  - 重新导出 conflict detector 的 3 个 legacy helper

修完后直接 smoke：

```bash
python3 scripts/run_event_mining_theme_suite.py \
  --spec specs/theme_runs/2026-03-14_commercial_space_sentinel_v2.yaml \
  --events imports/theme_runs/2026-03-14_commercial_space_events_v2.json \
  --as-of 2026-03-15 \
  --theme-slug commercial_space \
  --run-root /tmp/commercial_space_finbot_smoke
```

结果：

- `ok=true`
- `recommended_posture=watch_only`
- `best_expression=Rocket Lab`
- `replay_ok=true`

### 5. 真实切换验证

先直接跑：

```bash
python3 ops/openclaw_finbot.py theme-run --theme-slug commercial_space --format json
```

结果成功，写出：

- `artifacts/finbot/theme_runs/2026-03-24/commercial_space`
- `artifacts/finbot/inbox/pending/finbot-theme-commercial-space.json`

再用 lane wrapper 跑一遍，把 heartbeat / completed 状态打进 controller lane：

```bash
python3 ops/controller_lane_wrapper.py \
  --lane-id finbot-commercial-space \
  --summary "finbot commercial_space" \
  --artifact-path /vol1/1000/projects/ChatgptREST/artifacts/finbot/theme_runs/2026-03-24/commercial_space \
  --executor-kind finbot \
  --provider finagent \
  --model commercial_space_theme_suite \
  -- \
  python3 ops/openclaw_finbot.py theme-run --theme-slug commercial_space --format json
```

最终 lane 状态：

- `run_state=completed`
- `last_exit_code=0`
- `heartbeat_at` 有值
- `last_artifact_path` 指向 commercial space run root

## 为什么这样切

因为你要的不是“再开一个商业航天脚本”，而是：

- 用 OpenClaw `finbot` 作为 canonical scout
- 有 controller lane heartbeat
- 有 runtime guard / stale 检测
- 有 finbot inbox / theme state / artifact 记忆面

商业航天现在已经满足这个运行方式。

## 下一步

如果继续推进，我建议顺序是：

1. 把 `finbot-commercial-space` 做成定时 lane（service/timer 或现有调度）
2. 再把商业航天 domain pack blueprint 逐步落到 `finagent`
3. 保持 `finbot` 作为 northbound 运行面，`finagent` 作为 deeper research substrate

