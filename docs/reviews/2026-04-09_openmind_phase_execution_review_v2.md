# OpenMind Phase 0–6 Execution Review (v2 — deep)

**Reviewer**: Antigravity (Claude Opus 4.6 Thinking)  
**Date**: 2026-04-09  
**Scope**: Commits `cec0d69f`..`3967b3f2` (4 commits, 20 files, +1976/−3 lines)  
**Supersedes**: `2026-04-09_openmind_phase_execution_review_v1.md` (too superficial)

---

## 0. Self-reflection on v1

v1 was a pass-through: I summarized what the code does, said "looks good" at each file, and listed cosmetic nits. I did not:
- Trace cross-file interface contracts (does `_maybe_compile_wakeup_packet` correctly thread `interaction_learning` from the route's context dict into `build_wakeup_packet`?)
- Challenge design decisions (why is `_maybe_compile_wakeup_packet` mutating the Pydantic `task_intake` object in-place instead of producing a new one?)
- Check for real bugs (the `isinstance(active_block, object)` line I noted is cosmetic; did I look for semantic errors?)
- Verify the harness script's fidelity (it doesn't pass `interaction_learning` at all — is that intentional?)
- Evaluate ordering dependencies (does interaction_learning enrichment happen BEFORE wakeup packet compilation?)
- Check token budget correctness (the default 4500 token budget vs. the ContextResolver's 8000 default — what's the reconciliation?)

This v2 attempts to fix those gaps.

---

## 1. Cross-File Interface Audit

### 1a. `interaction_learning` threading: ✅ CORRECT

|Step|Location|What happens|
|---|---|---|
|1|`routes_agent_v3.py:5510–5519`|`_maybe_enrich_interaction_learning_context()` reads from memory store, merges with inline user correction signals, writes `context["interaction_learning"]`|
|2|`routes_agent_v3.py:5522–5542`|`build_task_intake_spec(context=context)` → the interaction_learning dict is now inside `task_intake.context`|
|3|`routes_agent_v3.py:1382–1386`|`_maybe_compile_wakeup_packet()` extracts `task_intake.context.get("interaction_learning")` and passes it as `interaction_learning=` kwarg|
|4|`wakeup_packet.py:126`|`build_interaction_learning_crystal(interaction_learning)` receives the payload|
|5|`crystallized_learning.py:21–89`|Crystal is built only if stable preferences meet the support threshold|

**Verdict**: The chain is correct end-to-end. The ordering (interaction learning enrichment → task intake build → packet compile) is also correct — interaction_learning is in `context` before `build_task_intake_spec` copies it into `task_intake.context`.

### 1b. `context` dict shared mutation: ⚠️ DESIGN CONCERN

The route handler shares a single `context` dict between:
- `_maybe_enrich_interaction_learning_context()` → writes `context["interaction_learning"]`
- `build_task_intake_spec(context=context)` → copies into `task_intake.context`
- `_maybe_compile_wakeup_packet()` — mutates `task_intake.context` AND writes `context["wake_up_packet_receipt"]`
- Multiple downstream consumers: `normalize_ask_contract(context=context)`, `build_strategy_plan(context=context)`, `build_prompt_from_strategy(custom_context=context)`, `_build_control_plane_state()`, etc.

The `_maybe_compile_wakeup_packet` function **mutates** `task_intake.context` (line 1396) and `task_intake.available_inputs` (line 1398–1401). Since `TaskIntakeSpec` is a mutable Pydantic BaseModel, this works. But it means:
- `task_intake.to_dict()` serialized at line 5606 includes the wakeup packet receipt in `.context` — **correct, this is desired**
- `task_intake_to_contract_seed(task_intake)` at line 5607 invokes `_stringify_contract_field(spec.available_inputs)` which now includes the wakeup packet — **correct, this is how the packet reaches the prompt**
- `context["task_intake"] = task_intake.to_dict()` at 5606 reflects the mutated state — **correct**

**Risk**: If a future developer adds a step between packet compilation and contract seeding that depends on the *pre-mutation* `available_inputs`, it will silently get the post-mutation version. This is not a bug today, but it's a maintenance landmine.

**Recommendation**: Add a `# NOTE: wakeup packet compilation mutates task_intake.context and task_intake.available_inputs` comment at line 5573, or document this in the contract.

### 1c. Harness script doesn't pass `interaction_learning`: ⚠️ INCOMPLETE

`ops/run_wakeup_packet_harness.py:72–83` calls `build_wakeup_packet()` without `interaction_learning=`. This means:
- The harness artifact at `artifacts/monitor/wakeup_packet_harness/20260409T022911Z/wakeup_packet.json` has `crystallized_learning: null`
- The harness can't verify the crystallized learning integration path

This is a **coverage gap** in the harness (not the runtime). Adding `--interaction-learning-json` or fabricating a sample payload would close it.

---

## 2. Real Bugs & Semantic Issues

### 2a. `isinstance(active_block, object)` — dead guard (LOW)

**File**: `wakeup_packet.py:298`  
**Problem**: `isinstance(x, object)` is always True in Python. The intent was likely `if active_block is not None`.  
**Impact**: None in practice — `getattr(None, "provenance", [])` returns `[]`, so the next line still works.  
**Fix**: Change to `if active_block is not None:`.

### 2b. Token budget mismatch (DESIGN QUESTION)

**File**: `wakeup_packet.py:95`, default `token_budget=4500`  
**File**: `context_service.py:72`, `ContextResolveOptions` default `token_budget=8000`

`build_wakeup_packet` passes `token_budget=4500` to `ContextResolveOptions`. The `ContextResolver.resolve()` then clips it: `max(1500, min(int(options.token_budget or 8000), 32000))` → 4500 is within range, so it's used as-is.

**Question**: Why 4500? The packet is injected into the compiled prompt which will also include the direct prompt template. If a planning turn has ~16K prompt budget, is 4500 enough? The harness artifact shows `context_used_tokens: 1323` out of `requested_token_budget: 4500`, so under real conditions it's well within budget. But for knowledge-heavy projects with many EvoMap hits, this could truncate useful context.

**Verdict**: Not a bug, but the 4500 default is undocumented in the contract. The contract at `docs/contracts/2026-04-09_wakeup_packet_contract_v1.md` says "token-budgeted, precedence-ordered" but doesn't specify the default budget or how it relates to the overall prompt budget. Worth pinning in the contract.

### 2c. `_maybe_compile_wakeup_packet` error path returns a receipt dict instead of None (SEMANTIC)

**File**: `routes_agent_v3.py:1388–1397`

When packet compilation fails, the function:
1. Writes `context["wake_up_packet_receipt"] = {"applied": False, "reason": "packet_compile_failed", "error": ...}` into `task_intake.context` 
2. Returns `dict(updated_context["wake_up_packet_receipt"])`

Then at line 5580–5581:
```python
if wake_up_packet:
    context["wake_up_packet_receipt"] = dict(wake_up_packet)
```

Since the error dict `{"applied": False, ...}` is truthy, `context["wake_up_packet_receipt"]` gets set **twice**: once inside `_maybe_compile_wakeup_packet` (mutating `task_intake.context`) and once at line 5581 (mutating the route's `context` dict). These are **different dicts** — `context` is the route-level dict, while `task_intake.context` was set by `build_task_intake_spec` earlier. The values are the same, so it's not a bug, but the double-write is confusing.

**More importantly**: the error path sets `task_intake.context = updated_context` at line 1396, which replaces the entire context dict. If `task_intake.context` had additional keys not in `updated_context`, they're lost. Let me check: `updated_context = dict(task_intake.context or {})` at line 1390 copies the existing context, so all keys are preserved. ✅ No bug.

### 2d. `ContextResolver.__init__` type annotation says `runtime: AdvisorRuntime` but `build_wakeup_packet` passes `runtime: Any` (TYPING)

**File**: `context_service.py:137`  
**File**: `wakeup_packet.py:86`

`build_wakeup_packet` accepts `runtime: Any` and directly passes it to `ContextResolver(runtime)`. `ContextResolver.__init__` has a type annotation of `AdvisorRuntime`, but since Python doesn't enforce type annotations at runtime, this works. In practice, `_advisor_runtime()` in routes always returns an `AdvisorRuntime` instance.

However, in tests, if someone mocks `build_wakeup_packet` with `runtime={"memory": None}` (a plain dict), it would blow up inside `ContextResolver.resolve()` when it tries to access `self._runtime.memory`, because `AdvisorRuntime` has a custom `__getitem__` and `get()` that `dict` doesn't need. Wait — `dict` DOES have `get()`, and `AdvisorRuntime` has `def get(self, key, default=None) -> Any: return getattr(self, key, default)`. So a plain dict would work for `.get("memory")` but fail for attribute access like `self._runtime.memory`.

**Verdict**: Not a runtime bug (the production path always passes `AdvisorRuntime`), but a test fragility. If someone writes a unit test for `build_wakeup_packet` with `runtime=MagicMock()`, it would work because MagicMock responds to any attribute. But with `runtime={}`, it would fail with `AttributeError: 'dict' object has no attribute 'memory'`.

---

## 3. Design Decision Challenges

### 3a. Why compose ContextResolver inside build_wakeup_packet instead of accepting a pre-resolved context?

`build_wakeup_packet` creates `ContextResolver(runtime)` and calls `.resolve()` internally (line 100–113). This means every wakeup packet compilation triggers a full context resolution — memory lookup, KB search, EvoMap retrieval, authority anchor loading.

**Alternative**: The route handler could call `ContextResolver.resolve()` once and pass the result to `build_wakeup_packet`. This would allow:
- Reusing the same context result for both the packet and other route logic
- Testing `build_wakeup_packet` without mocking the entire resolver

**Counter-argument**: The route handler currently doesn't use `ContextResolver` directly — it's a wakeup-packet-only path. Splitting the resolution from the packet builder would introduce an unnecessary coordination point.

**Verdict**: Current design is defensible. The encapsulation keeps the packet compiler self-contained. But it means the wakeup packet compilation is a "side-channel" context resolution that's invisible to the rest of the route handler. Document this.

### 3b. `frozen=True` on `WakeUpPacket` but not on `TaskIntakeSpec` — inconsistent immutability

`WakeUpPacket` is `@dataclass(frozen=True)`, preventing mutation after creation. `TaskIntakeSpec` is a mutable Pydantic model that `_maybe_compile_wakeup_packet` mutates in-place.

The packet is immutable — good. But the container it's injected into (`task_intake.available_inputs`) is mutable. This means a downstream consumer could do `task_intake.available_inputs["wake_up_packet"]["layers"][0]["summary"] = "hacked"` because `WakeUpPacket.to_dict()` returns a plain dict. The `frozen=True` on the dataclass only prevents attribute reassignment on the dataclass instance, not on the serialized dict.

**Verdict**: Not a real risk in practice (no code path does this), but worth noting for the record.

### 3c. `crystallized_learning` field is `None` vs. empty dict

`WakeUpPacket.crystallized_learning` defaults to `None` (line 60). When no interaction learning exists, it stays `None`. In `to_dict()`, this becomes `"crystallized_learning": null`. The `render_wakeup_packet` checks `isinstance(crystal, Mapping) and dict(crystal.get("stable_preferences") or {})` — this correctly skips `None`.

But `wakeup_packet_receipt()` doesn't include `crystallized_learning` at all:
```python
def wakeup_packet_receipt(packet):
    return {
        "schema_version": ...,
        "packet_id": ...,
        ...
        "layer_ids": [...],
    }
```

This means the receipt (which is the thin projection in `task_intake.context`) has **no visibility** into whether crystallized learning was applied. A downstream consumer looking at the receipt can't tell if learning was present.

**Recommendation**: Add `"has_crystallized_learning": bool(packet.crystallized_learning)` to the receipt.

---

## 4. Test Coverage — Deep Assessment

### 4a. Covered paths
| Path | Test | Verdict |
|---|---|---|
| Happy path: packet built, layers populated | `test_wakeup_packet.py::test_build_wakeup_packet_returns_layered_packet` | ✅ |
| L0 suppression when authority already in prompt | `test_prompt_builder.py::test_build_prompt_from_strategy_renders_wakeup_packet_without_duplicate_l0` | ✅ |
| Crystal support threshold | `test_crystallized_learning.py::test_build_interaction_learning_crystal_requires_min_support` | ✅ |
| Crystal invalidation lifecycle | `test_crystallized_learning.py::test_build_interaction_learning_crystal_supports_invalidation_via_newer_winner` | ✅ Excellent lifecycle test |
| Route integration (mock) | `test_routes_agent_v3.py::test_agent_turn_projects_wakeup_packet_into_task_intake_and_compiled_prompt` | ✅ |

### 4b. Missing paths (real gaps)
| Gap | Impact | Priority |
|---|---|---|
| `_maybe_compile_wakeup_packet` failure path (the `except` branch) | The fail-open guarantee is untested | P2 |
| `_merge_available_input_mapping` with legacy `str` existing value | The handler at line 1237–1241 is untested | P3 |
| `render_wakeup_packet` with `include_authority_layer=False` when there's no authority key but there IS a wake_up_packet | The prompt builder calls this at line 549, but no test exercises this specific combination | P3 |
| Crystallized learning with `None` payload (trivial but not tested) | `build_interaction_learning_crystal(None)` should return `None` | P3 |
| Harness script end-to-end (with real runtime) | `test_run_wakeup_packet_harness.py` only tests the smoke interface, not the full resolution chain | P3 |
| `wakeup_packet_receipt` with a plain dict input (vs WakeUpPacket instance) | Both paths exist (line 165), but only the WakeUpPacket path is tested | P3 |

### 4c. Test quality observations

The route-level test (`test_agent_turn_projects_wakeup_packet_into_task_intake_and_compiled_prompt`) uses `monkeypatch.setattr(..., "build_wakeup_packet", mock_build_wakeup_packet)` which is the right approach — it verifies the integration without requiring a full advisory runtime. But it doesn't verify that `interaction_learning` is correctly threaded from `context` → `task_intake.context` → `build_wakeup_packet` kwarg, because the mock replaces the real function.

**Recommendation**: Add an assertion that checks the kwargs the mock was called with, specifically that `interaction_learning` matches what's expected from the enriched context.

---

## 5. Contract Document Assessment

### `docs/contracts/2026-04-09_wakeup_packet_contract_v1.md`

**Gaps**:
- Missing: default token budget (4500) and its relationship to the overall prompt budget
- Missing: behavior when `crystallized_learning` is present vs absent in the receipt
- Missing: explicit statement that the packet compiler performs its own `ContextResolver.resolve()` call, separate from any other context resolution in the route

### `docs/contracts/2026-04-09_openmind_scope_surface_inventory_v1.md`

**Solid**: The classification table correctly delineates bridge-only vs runtime. No issues.

### `docs/integrations/2026-04-09_openclaw_cognitive_substrate_runtime_contract_v3.md`

**Solid**: v2→v3 diff is well-motivated. The topology diagram is accurate.

---

## 6. Precedence Enforcement Audit

The core invariant is: **authority anchor > project memory > EvoMap knowledge > runtime heuristics**.

| Layer | Enforcement point | Correct? |
|---|---|---|
| L0 Authority | `ContextResolver` elevates `authority` block first; `_compose_prompt_prefix` places authority section before base prompt | ✅ |
| L0 in prompt | `prompt_builder.py:549` — `include_authority_layer=not authority_present` prevents L0 from rendering twice when authority keys are already in the prompt | ✅ |
| Crystal precedence | `crystallized_learning.py:88` — "Advisory only. Never override the authority anchor with crystallized learning." | ✅ (text, not enforced in code) |
| Crystal in markdown | `wakeup_packet.py:223` — rendered AFTER all layers, with explicit "(advisory; lower priority than the authority anchor)" label | ✅ |

**One observation**: The precedence enforcement for crystallized learning is **textual, not structural**. The crystal is rendered in the packet markdown, and the rendered text says "advisory, lower priority." But there's no runtime gate that prevents a crystal from contradicting the authority anchor. For example, if the authority anchor says `owner: CEO` and a crystal says `preferred_executor_family: codex`, there's no conflict because they're orthogonal keys. But if the authority anchor had a `quality_bar: strict` and a crystal had `quality_bar: relaxed`, the crystal would render both — and the LLM would have to resolve the contradiction using the textual precedence note.

**Verdict**: This is acceptable for phase 1. True structural enforcement would require comparing crystal keys against authority anchor keys, which adds complexity for marginal benefit.

---

## 7. Summary Verdicts

### Overall: **PASS with advisory items**

The execution is genuine, solid, and well-integrated. The code is defensive, the test suite covers the critical paths, and the contracts are frozen with honest residual risks.

### Issues to track

| ID | Type | Severity | Description |
|---|---|---|---|
| R2-1 | Bug | Low | `isinstance(active_block, object)` always True at L298 |
| R2-2 | Missing | P2 | No test for `_maybe_compile_wakeup_packet` failure path |
| R2-3 | Missing | P3 | Harness doesn't exercise `interaction_learning` path |
| R2-4 | Design concern | Low | `_maybe_compile_wakeup_packet` mutates `task_intake` in-place; needs comment |
| R2-5 | Contract gap | Low | Default token budget (4500) undocumented in wakeup_packet_contract_v1.md |
| R2-6 | Missing | P3 | `wakeup_packet_receipt` doesn't report `has_crystallized_learning` |
| R2-7 | Missing | P3 | Route test doesn't assert `interaction_learning` kwarg on mock |

### What v1 got wrong
- v1 said "No test for packet compile failure path" as an afterthought; v2 explains WHY this matters (the fail-open guarantee is unverified)
- v1 missed the harness `interaction_learning` gap entirely
- v1 didn't trace the cross-file interface chain at all 
- v1 didn't mention the `_maybe_compile_wakeup_packet` mutation pattern
- v1 didn't challenge the token budget default or the `ContextResolver` encapsulation decision
- v1 didn't check the `wakeup_packet_receipt` completeness (missing `has_crystallized_learning`)

**Status: Accepted / no rework required, but advisory items should be tracked for follow-up.**
