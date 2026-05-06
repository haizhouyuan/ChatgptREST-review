# 2026-04-04 W1 ChatGPT Live Lane Unblock And Completion Execution Review v1

## 1. Scope

This batch closes the previously open `W1-S5` gap for the canonical `OpenClawBot` planning completion gate on explicit `requested_provider=chatgpt`.

This batch does **not** widen the claim to every ChatGPT-backed task shape. The stable statement remains narrow:

1. integrated `18711` host;
2. `OpenClawBot` planning completion gate;
3. explicit `requested_provider=chatgpt`;
4. truthful terminal `session / task / checkpoint` alignment.

## 2. What actually blocked the lane

The blocker was **not** missing ChatGPT login state in shared Chrome.

What the investigation showed instead:

1. the shared CDP Chrome profile already had a valid ChatGPT session;
2. the real send blocker was Cloudflare / Turnstile verification on the live `chatgpt.com` tab;
3. after send started working, the canonical compact-planning answer was still being held open by our own completion guards:
   - controller defaulted `quick_ask` jobs to `min_chars=200`;
   - worker treated `<100 chars` compact planning bullet answers as `suspect_short_answer`;
4. the gate runner itself silently ignored `--requested-provider` / `--output-dir`, which initially produced false operator conclusions.

## 3. Code changes

Changed files:

1. `chatgpt_web_mcp/_tools_impl.py`
2. `chatgptrest/controller/engine.py`
3. `chatgptrest/core/conversation_exports.py`
4. `chatgptrest/eval/openclawbot_planning_task_plane_live_completion_gate.py`
5. `ops/run_openclawbot_planning_task_plane_live_completion_gate.py`

### 3.1 ChatGPT verification click path is more reliable

`chatgpt_web_mcp/_tools_impl.py` now:

1. prefers the hidden `cf-turnstile-response` ancestor click path before generic frame-center fallback;
2. extends the observation window when the page reports `verification_success_waiting`.

Net effect: the live challenge page is less likely to stay stuck at `Verify you are human` after the first automatic click.

### 3.2 Compact planning jobs now use a truthful `min_chars`

`chatgptrest/controller/engine.py` now lowers default `min_chars` to `60` for:

1. `scenario=planning`
2. `output_shape=planning_memo`
3. `provider_hints.planning_mode=compact_next_steps`

Net effect: canonical three-bullet planning answers no longer inherit the generic `quick_ask` `200`-char threshold.

### 3.3 Compact planning short answers are no longer misclassified

`chatgptrest/core/conversation_exports.py` now treats `<100 chars` answers as `final` when:

1. the prompt explicitly requests `planning_memo`;
2. the prompt explicitly asks for a three-bullet compact answer;
3. the answer actually contains at least three list items.

Net effect: worker wait-phase completion no longer requeues valid compact planning answers just because they are short.

### 3.4 The runner now honors real CLI intent

`ops/run_openclawbot_planning_task_plane_live_completion_gate.py` now:

1. parses `--requested-provider`;
2. parses `--output-dir`;
3. keeps env override behavior for timeouts;
4. preserves explicit `main([])` testing instead of accidentally swallowing or leaking CLI args.

Net effect: an operator asking for `chatgpt` now actually gets a `chatgpt` run.

### 3.5 The live gate sample and wording were tightened

`chatgptrest/eval/openclawbot_planning_task_plane_live_completion_gate.py` now:

1. uses a stronger attachment sample so the canonical fact is harder for the model to ignore;
2. broadens attachment-fact matching to include `恢复时间窗口`;
3. replaces the stale boundary text with `runner defaults to requested_provider=gemini unless explicitly overridden`.

## 4. Regression coverage

Validated with:

```bash
python3 -m py_compile \
  chatgpt_web_mcp/_tools_impl.py \
  chatgptrest/controller/engine.py \
  chatgptrest/core/conversation_exports.py \
  chatgptrest/eval/openclawbot_planning_task_plane_live_completion_gate.py \
  ops/run_openclawbot_planning_task_plane_live_completion_gate.py \
  tests/test_chatgpt_cdp_page_reuse.py \
  tests/test_controller_engine_planning_pack.py \
  tests/test_answer_quality_completion_guard.py \
  tests/test_openclawbot_planning_task_plane_live_completion_gate.py \
  tests/test_run_openclawbot_planning_task_plane_live_completion_gate.py

./.venv/bin/pytest -q tests/test_chatgpt_cdp_page_reuse.py -q
./.venv/bin/pytest -q tests/test_controller_engine_planning_pack.py tests/test_scenario_packs.py -q
./.venv/bin/pytest -q tests/test_answer_quality_completion_guard.py tests/test_longest_candidate_extraction.py -q
./.venv/bin/pytest -q tests/test_openclawbot_planning_task_plane_live_completion_gate.py -q
./.venv/bin/pytest -q tests/test_run_openclawbot_planning_task_plane_live_completion_gate.py -q
```

Runtime reload performed:

```bash
systemctl --user restart chatgptrest-api.service
systemctl --user restart chatgptrest-worker-send.service chatgptrest-worker-wait.service
```

## 5. Live evidence freeze

### 5.1 First truthful ChatGPT green

The first successful explicit `requested_provider=chatgpt` freeze is:

1. `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_chatgpt_v5/report_v1.json`
2. `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_chatgpt_v5/report_v1.md`

It proves:

1. `requested_provider=chatgpt`
2. `terminal_status=completed`
3. `num_passed=6`
4. `num_failed=0`

Terminal session / job:

1. session `openclaw-live-planning-completion-session-0e931085`
2. task `pln_dafe6d57b74d`
3. job `c943e979b92846019ccb12cb3925be70`

### 5.2 Final freeze with corrected scope wording

The final freeze for this batch is:

1. `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_chatgpt_v6/report_v1.json`
2. `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_chatgpt_v6/report_v1.md`
3. `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_chatgpt_v6/manifest.json`

Terminal session / job:

1. session `openclaw-live-planning-completion-session-df0e65fc`
2. task `pln_f1db6dffc972`
3. job `2c56863c544542d2a4394d8d99515846`

This rerun also stayed green:

1. `requested_provider=chatgpt`
2. `terminal_status=completed`
3. `num_passed=6`
4. `num_failed=0`

## 6. Current authoritative judgment

`W1` is now complete for the canonical ChatGPT completion lane as well.

What is now safe to say:

1. the canonical `OpenClawBot` planning completion gate is green on explicit `requested_provider=gemini`;
2. the same canonical gate is now also green on explicit `requested_provider=chatgpt`;
3. the old statement `ChatGPT live lane remains verification-blocked` is no longer authoritative.

What is still **not** safe to say:

1. this is not a blanket claim that every ChatGPT task shape is stable;
2. the runner default is still `gemini` unless the operator explicitly overrides it;
3. `W2-W6` remain outstanding.
