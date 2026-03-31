# 2026-03-22 Phase 9 Agent V3 Route Work Sample Validation Review v1

## 1. Review Verdict

`Phase 9` is directionally correct and can pass as a phase deliverable.

It successfully upgrades the validation seam from:

- semantic snapshot only

to:

- live `/v3/agent/turn` route replay

That is a meaningful step forward and matches the intended roadmap:

- first freeze front-door object semantics
- then validate multi-ingress semantic consistency
- then move one layer deeper into public route replay

But there is still one fidelity gap in the current validator, so this phase
should be described as:

- **agent_v3 public-route business-sample validation**

not as:

- exact controller-route replay validation

## 2. Main Finding

### Finding 1: controller-side final route is not independently validated

The phase pack says it validates:

- final public `status`
- final public `provenance.route`
- clarify vs controller branch selection

That is mostly true for the route layer, but controller-route validation is still
partly synthetic.

Current validator behavior:

- it replays the live router from [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- but patches `ControllerEngine` with a fake controller in [agent_v3_route_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/agent_v3_route_work_sample_validation.py#L111)
- that fake controller simply echoes `stable_context.ask_strategy.route_hint` back as `result["route"]` in [agent_v3_route_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/agent_v3_route_work_sample_validation.py#L120)

Meanwhile the live route uses controller output directly for the public response:

- controller result route enters session state at [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1630)
- and becomes public response route at [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1646)

So today this validator proves:

- the live route still chooses `clarify` vs `controller`
- and the public response still forwards the controller-returned route correctly

But it does **not** independently prove:

- that real controller-side route resolution would still match strategist route hint

If future drift appears between:

- strategist `route_hint`
- controller returned `route`

this validator could stay green because the fake controller forces them to be the
same.

This is not a production bug today. It is a validation-fidelity gap.

## 3. What Phase 9 Does Prove

This phase does prove several important things:

1. `/v3/agent/turn` still performs live ingress normalization for these business samples
2. route-level clarify gating still works on the public surface
3. route-level controller handoff still happens on the expected samples
4. public `status` / `provenance.route` wiring stays stable at the router seam

That is stronger than `Phase 7` and `Phase 8`, because it is no longer only
observing helper-layer semantics.

## 4. What Phase 9 Still Does Not Prove

The phase docs are mostly accurate here, and the following boundaries still hold:

- not OpenClaw dynamic replay
- not full-stack controller/runtime/knowledge validation
- not artifact/writeback correctness

I would add one more explicit non-goal:

- not real controller route-resolution equivalence

## 5. Overall Assessment

My overall assessment is:

- **Phase 9 passes as route-level public-front-door validation**
- **Phase 9 does not yet pass as exact controller-route replay validation**

That makes this phase useful and legitimate, but still one step short of a
stronger controller-delivery validation pack.

## 6. Recommended Next Step

The most natural follow-up is not to widen scope immediately to full-stack.

The next clean step is:

1. keep the live `/v3/agent/turn` replay
2. replace the echo-style fake controller with a controller stub that can return
   intentionally different route payloads
3. add at least one assertion that router-visible `provenance.route` tracks
   controller output, not just strategist hint

After that, the next phase can move into:

- controller-delivery replay
- or full-chain runtime/knowledge validation

with a much cleaner seam.
