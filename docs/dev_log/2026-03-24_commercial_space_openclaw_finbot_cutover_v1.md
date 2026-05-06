# 商业航天切到 OpenClaw Finbot v1

## 结论

商业航天主题已切到 OpenClaw `finbot` 运行，不再需要手工依赖 `theme-batch-run` 的目录顺序。

当前正式入口：

```bash
python3 ops/openclaw_finbot.py theme-run --theme-slug commercial_space --format json
```

为获得 OpenClaw heartbeat / lane state / artifact 指针，推荐用 controller lane wrapper：

```bash
python3 ops/controller_lane_wrapper.py \
  --lane-id finbot-commercial-space \
  --summary "finbot commercial_space" \
  --artifact-path /vol1/1000/projects/ChatgptREST/artifacts/finbot/theme_runs/$(date +%F)/commercial_space \
  --executor-kind finbot \
  --provider finagent \
  --model commercial_space_theme_suite \
  -- \
  python3 ops/openclaw_finbot.py theme-run --theme-slug commercial_space --format json
```

## 已落地项

1. `chatgptrest.finbot.theme_batch_run()` 新增 `theme_slug` 过滤能力。
2. `ops/openclaw_finbot.py` 新增 `theme-run --theme-slug ...` 单主题入口。
3. `config/controller_lanes.json` 新增 `finbot-commercial-space` lane。
4. `config/finbot_theme_catalog.json` 里的 `commercial_space` 主题现在可被单独执行。
5. 真实运行验证通过，结果进入：
   - `artifacts/finbot/theme_runs/2026-03-24/commercial_space`
   - `artifacts/finbot/inbox/pending/finbot-theme-commercial-space.json`

## 当前运行结果

- `theme_slug`: `commercial_space`
- `recommended_posture`: `watch_only`
- `best_expression`: `Rocket Lab`
- `action`: `watch_only`

## 控制面状态

`finbot-commercial-space` lane 已在 controller lane continuity 中完成一次真实运行，状态为：

- `run_state=completed`
- `last_exit_code=0`
- `last_summary=finbot commercial_space completed`
- `last_artifact_path=artifacts/finbot/theme_runs/2026-03-24/commercial_space`

## 关键边界

1. 这次切换的是 **OpenClaw finbot 运行面**，不是商业航天 domain pack 全量实现。
2. `finbot` 提供的是：
   - theme run 入口
   - inbox / theme state / dossier artifact
   - OpenClaw lane heartbeat / status / runtime guard 可观测性
3. 它不自动等价于 `finagent` 的 domain-pack memory/graph/evidence 演进；那是下一阶段。
4. 为了让 commercial space theme suite 可运行，同时在 `finagent` 侧补了一个 legacy export shim：
   - `finagent.graph` 重新导出 `build_graph_from_db / detect_conflicts / find_broken_support_chains`

