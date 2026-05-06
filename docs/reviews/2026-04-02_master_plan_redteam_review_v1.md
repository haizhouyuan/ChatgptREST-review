# 2026-04-02 Master Plan Red-Team Review v1

Reviewer: Claude Code (claude-opus-4.6), adversarial mode
Target: `docs/reviews/2026-04-02_planning_agent_total_plan_execution_master_v1.md`

---

## Findings

### F1. DANGEROUS — The master plan's "会议沉淀" MVP silently depends on an OpenClawBot bridge that doesn't exist yet

The plan freezes this chain (§6.1):

> Feishu → OpenClawBot → canonical task plane → 深度工作台 → checkpoint → 回到 OpenClawBot

But the code reality is:

- `openclaw_extensions/openmind-advisor/index.ts:444` hits `/v3/agent/turn` — good.
- However, the `TaskIntakePayload` it builds (`:305-348`) has **no `task_id` field**. Grep confirms zero matches for `task_id` in that file.
- The plan says "分配 task_id" (§6.1 step 3), but `/v3/agent/turn` in `routes_agent_v3.py` only has `logical_task_id` as a telemetry passthrough (`:349,396`). It never calls into `task_runtime`.
- `agent_mcp.py` has zero references to `task_runtime`, `checkpoint`, or `task_id`.

So the plan's step 3–6 require building **three** new integration points (task_id allocation, checkpoint write, checkpoint read-back from OpenClawBot), not just "核桥接现实" as Next Step 3 suggests. The plan underestimates this as a "找出落点" exercise when it's actually the bulk of the engineering.

### F2. WRONG — The plan treats OpenClawBot → canonical task plane as an existing bridge that just needs "收敛"

§3.2 says:

> 优先保证 `OpenClawBot -> canonical task plane` 收敛

The word "收敛" (converge) implies something already working that needs tightening. But:

- OpenClawBot (`index.ts:444`) does hit `/v3/agent/turn` — this part works.
- But `/v3/agent/turn` does NOT connect to `task_runtime`. The `logical_task_id` param (`:349`) is only emitted as telemetry (`:396`), never used to create/resume a task.
- `task_runtime` is registered as `core=False` in `app.py:198`.

The bridge from OpenClawBot to the *canonical task plane* (as defined by the unified logical task layer doc) does not exist. The plan should say "build" not "收敛".

### F3. DANGEROUS — Feishu → OpenClawBot → checkpoint read-back has no design at all

The plan's acceptance criterion #4 (§11):

> 能再次从 OpenClawBot 找回并继续

But `index.ts` exposes exactly one tool: `openmind_advisor_ask`. There is:
- No `openmind_advisor_resume` tool
- No `openmind_advisor_status` tool
- No `task_id` parameter on the existing tool
- No way for a Feishu user to say "继续上次的会议沉淀"

The plan's Next 3 (§13) doesn't mention building this at all. This is not a gap — it's a missing half of the MVP.

### F4. WRONG — "publicagentmcp 不再继续长胖" is already violated by the plan itself

§9.1 says publicagentmcp should "保持可用, 不再继续长胖".

But the MVP chain requires:
1. `advisor_agent_turn` to accept and propagate `task_id`
2. `advisor_agent_status` to return checkpoint state
3. Some new tool or parameter for "continue task"

All of these changes would happen inside `agent_mcp.py` — the very surface the plan says should stop growing. The plan contradicts itself: you can't build task continuity through the public MCP surface while also freezing that surface.

### F5. UNDERESTIMATED — The 6-field checkpoint is still paper

§7 defines a minimal 6-field checkpoint. But:

- `TaskStateMachine.checkpoint()` only exists in tests (`test_task_runtime.py`).
- `task_state_machine.py` has a `_TRANSITIONS` dict but no `checkpoint()` method visible in the first 80 lines. The state machine tracks `phase/status` transitions, not checkpoint content.
- `task_store.py` has `last_checkpoint_at` and `state_data_json` columns, but no structured checkpoint schema.

The plan says "先用 6 字段证明跨端 handoff 可行" as if this is a small step. In reality, you need to:
1. Define the checkpoint schema
2. Build a write path from the deep workbench
3. Build a read path from OpenClawBot
4. Wire both through `routes_agent_v3.py` or `task_runtime/api_routes.py`

This is the core of the MVP, not a side deliverable.

### F6. SAYS TOO STRONGLY — "每步都要有红队 gate" (§4.2) is aspirational, not operational

The plan says every step gets a `claudegac` red-team review checking 4 questions. But:
- There's no automation for this. `claudegac` is a manual invocation.
- The 4 questions (§12) are subjective and have no pass/fail criteria.
- Prior red-team reviews took a full `claudecode-agent-runner` job each. At that cost, "every meaningful step" means either the steps are very large (defeating the purpose) or the overhead is enormous.

This should be honest: red-team gates will be periodic, not per-step.

### F7. UNDERESTIMATED — The Feishu WS gateway is not just "historical compatibility"

The feishu_ws_gateway.py (`:86-100`) already builds a `task_intake` spec with `build_task_intake_spec()`. It sets `ingress_lane="advisor_advise_v2"`. The plan (via the ingress constraint doc) demotes this to "internal/fallback/historical".

But this gateway is the only path that actually connects Feishu messages to ChatgptREST today. If the plan's MVP requires "Feishu → OpenClawBot → canonical task plane", someone needs to build the equivalent capability inside OpenClawBot. The plan doesn't acknowledge that OpenClawBot currently has no Feishu message handler — it's a generic OpenClaw plugin that gets invoked by OpenClaw's own Feishu bot framework. The plan assumes OpenClawBot "接住请求" but doesn't verify that OpenClawBot's Feishu integration actually supports the "会议沉淀" workflow (audio files, transcripts, etc.).

---

## What Still Holds

1. **Direction is correct.** Knowledge layer补齐 + task layer首次实现 as parallel tracks is the right split.

2. **"会议沉淀" as first task type is a good choice.** It has natural material input, clear acceptance criteria, and high daily frequency.

3. **The 6-field checkpoint reduction from 14 is wise.** Starting minimal is correct; the prior 14-field spec was premature.

4. **publicagentmcp tension is correctly identified.** The "code reality = orchestration facade, target = ask-wrapper boundary" framing is more honest than either extreme.

5. **Knowledge layer priorities are grounded.** Runtime pack freshness, active atom promotion, and acceptance coverage are the right three items, and the plan correctly says "不重构".

6. **Red-team gate concept is valuable** even if the "every step" claim is unrealistic. The 4 questions in §12 are good sniff tests.

7. **The plan correctly stops scope creep.** Not doing 8 task types, full policy system, or complete evaluator/harness in phase 1 is the right call.

---

## What I Would Change In The Master Plan

### C1. Replace "核桥接现实" (Next Step 3) with an explicit engineering spec

Next Step 3 currently says "核 OpenClawBot → canonical task plane 的当前桥接现实". This sounds like investigation. It should instead be:

> Write the integration spec for: (a) task_id allocation in /v3/agent/turn, (b) checkpoint write API, (c) checkpoint read API, (d) OpenClawBot resume tool.

### C2. Add a Next Step 0: verify OpenClawBot can handle 会议沉淀 materials

Before writing any spec, verify:
- Can OpenClawBot receive audio files from Feishu?
- Can it forward them as attachments to `/v3/agent/turn`?
- Does the current `extractContextFiles()` in `index.ts` handle audio/transcript paths?

If not, the MVP chain is broken at step 1.

### C3. Acknowledge that publicagentmcp WILL grow for the MVP

The plan should drop the "不再继续长胖" language for this phase and instead say:

> publicagentmcp will gain task_id propagation and checkpoint query capabilities as part of the MVP. After the MVP, we reassess the boundary.

### C4. Change "每步红队 gate" to "每个切片红队 gate"

Per-step is unrealistic. Per-slice (i.e., per meaningful deliverable) is achievable and still valuable.

### C5. Add explicit dependency ordering to the Next 3

Current Next 3 are presented as parallel. They're not:
1. Step 0 (verify OpenClawBot 会议沉淀 capability) blocks everything
2. Step 1 (实施规格) depends on Step 0
3. Step 2 (checkpoint schema) can start in parallel with Step 1
4. Step 3 (桥接) is actually the implementation, not investigation

### C6. Drop the word "冻结" for things that haven't been tested

The plan uses "冻结" (freeze) for the MVP chain, checkpoint fields, and acceptance criteria. But freezing implies stability. These are first drafts that will change the moment code hits reality. Use "draft" or "baseline" instead.

---

## Alternative Next 3

### 1. Smoke-test the OpenClawBot → 会议沉淀 path end-to-end with current code

Before writing any spec, manually test:
- Send a Feishu message with an audio file to OpenClawBot
- Trace whether it reaches `/v3/agent/turn`
- Check what `attachments` look like on arrival
- Document every gap

This takes hours, not days, and will immediately reveal whether the MVP chain is 3 weeks or 3 months of work.

### 2. Build task_id allocation into /v3/agent/turn as a minimal patch

Don't build the full task_runtime integration. Instead:
- Add a `task_id` field to the turn request
- If absent, allocate one (UUID)
- Persist it in `AgentSessionStore` alongside `session_id`
- Return it in the response

This gives you task_id without requiring the full `task_runtime` state machine, which has 12 states and is overengineered for an MVP.

### 3. Build a 6-field checkpoint as a JSON sidecar in AgentSessionStore

Don't route through `task_runtime`. Instead:
- Add a `checkpoint` JSON blob to the session store
- Write it at the end of each turn
- Expose it via `advisor_agent_status`
- Let OpenClawBot read it via a new `openmind_advisor_task_status` tool

This avoids the `core=False` task_runtime entirely and builds on the session infrastructure that already works.

---

## Bottom Line

The master plan's direction is right but its execution plan is a layer of abstraction above the actual work. It says "核桥接现实" where it should say "build three new integration points". It says "不再继续长胖" for a surface that must grow to support the MVP. It says "冻结" for designs that haven't touched running code.

The single most dangerous thing in this plan is that it could be read as "we're almost ready to execute" when the reality is: the task_id → checkpoint → resume chain doesn't exist anywhere in running code, and the OpenClawBot → 会议沉淀 material handling hasn't been verified. The plan needs to be honest that the MVP is a build, not a wire-up.
