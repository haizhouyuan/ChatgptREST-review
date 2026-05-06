# ChatgptREST Answer Harvest Blueprint (Worker + Quality Gate + Dashboard)

> Updated: 2026-02-16
> Scope: ChatGPT Web / Gemini Web / Qwen Web answer retrieval reliability
> Goal: improve answer retrieval success without changing `docs/contract_v1.md`

## Why this blueprint
Current answer retrieval has multiple fragile points:
- UI/network volatility (blocked/cooldown, transient DOM/SSE races).
- partial/truncated outputs from tool calls.
- export/backfill timing mismatch during wait slicing.
- duplicated heuristics spread across executor + worker.

We already have useful primitives:
- `chatgpt_web_answer_get` rehydration path.
- `conversation_export` fallback with cooldown/backoff.
- completion guards for deep research and min chars.

This blueprint upgrades those primitives into one dedicated, auditable subsystem:
- independent `harvester` worker,
- explicit quality gates,
- observable metrics and SLOs.

## Non-negotiables
1. No external contract break:
   - Keep `/v1/jobs`, `/wait`, `/answer`, `/conversation` semantics.
2. Side-effect fail-closed:
   - Harvester must never send prompts.
   - Only read-only tools are allowed.
3. Provider coverage:
   - ChatGPT + Gemini + Qwen must all have harvest strategy.
4. Evidence and audit:
   - Every harvest attempt emits structured events.

## Target architecture

### New runtime role
- Add a new worker role: `harvest`.
- Keep existing `send` and `wait` roles unchanged for compatibility.
- Harvester consumes only jobs that are candidates for answer consolidation.

### New package layout
```text
chatgptrest/
  harvester/
    loop.py                # polling/claim loop for harvest tasks
    candidate.py           # candidate selection rules
    strategy.py            # provider strategy registry
    quality_gate.py        # deterministic quality scoring + acceptance
    state.py               # read/write per-job harvest state
    events.py              # harvest event helpers
    metrics.py             # aggregation snapshots for dashboard
    sources/
      chatgpt.py           # answer_get/export/dom-fallback strategy
      gemini.py            # wait/export-derived strategy
      qwen.py              # wait/export-derived strategy
```

### Data model additions (minimal)
- Keep `jobs` table as source of truth.
- Add `harvest_state_json` column to `jobs` (or standalone file fallback):
  - `status`: `idle|running|succeeded|deferred|failed`
  - `attempt`: integer
  - `last_source`: `answer_id|conversation_export|wait_answer|dom_markdown`
  - `best_score`: float
  - `last_error_type`, `last_error`
  - `next_not_before`
- Keep artifact mirror:
  - `artifacts/jobs/<job_id>/answer_harvest_state.json`
  - `artifacts/jobs/<job_id>/answer_harvest_report.json`

## Harvest candidate rules

### Candidate statuses
- `in_progress` (long-running with partial answer)
- `cooldown|blocked` (if conversation URL exists and read-only recovery is possible)
- `completed` (if final answer quality is below gate threshold)

### Entry guards
- Require provider-compatible thread URL:
  - ChatGPT `/c/`
  - Gemini `/app/`
  - Qwen provider-specific thread route
- Respect `not_before` and cooldown windows.
- Skip when global blocked circuit is active for that provider.

## Source strategy (per provider)

### ChatGPT priority order
1. `answer_id` chunk rehydration (`chatgpt_web_answer_get`)
2. server export (`chatgpt_web_conversation_export`)
3. wait snapshot (`chatgpt_web_wait` read-only poll)
4. DOM markdown fallback from existing turn (read-only)

### Gemini priority order
1. wait poll answer (`gemini_web_wait`)
2. conversation export (if available in provider implementation)
3. provider read-only snapshot fallback

### Qwen priority order
1. wait poll answer (`qwen_web_wait`)
2. provider export/snapshot fallback

## Quality gate design

### Gate inputs
- normalized answer text
- source metadata (`source`, `attempt`, `provider`, `model_text`)
- optional conversation export text for similarity check
- policy context (`deep_research`, `min_chars`)

### Core checks
1. Non-empty and min length:
   - configurable `min_chars`.
2. Structural integrity:
   - balanced markdown code fences.
3. Similarity consistency:
   - if export exists, answer/export similarity above threshold.
4. Stub rejection:
   - reject connector/tool-call stubs or ack-only phrases for deep research.
5. Truncation suspicion:
   - if `answer_chars` indicates truncation and no rehydration success, do not finalize.

### Decision outcomes
- `accept`: write final answer path and close harvest.
- `defer`: keep best-so-far, schedule next attempt.
- `fail`: hard-fail with reason and cooldown.

## State machine (harvest-specific)
```text
idle -> running -> (accept -> succeeded)
               \-> (defer -> deferred -> idle)
               \-> (hard error -> failed)
```

Rules:
- max attempts per job (`HARVEST_MAX_ATTEMPTS`, default 12).
- exponential backoff with jitter for defer/fail.
- cooldown alignment with provider blocked state.

## Event schema

Add event types (both DB and artifacts):
- `harvest_started`
- `harvest_source_attempted`
- `harvest_source_succeeded`
- `harvest_quality_scored`
- `harvest_deferred`
- `harvest_finalized`
- `harvest_failed`
- `harvest_blocked_circuit_open`

Required payload keys:
- `provider`, `source`, `attempt`, `score`, `decision`, `reason`
- `elapsed_ms`, `next_not_before` (for defer/fail)

## Metrics & dashboard

### Metrics snapshot file
- `artifacts/monitor/harvest/harvest_metrics_YYYYMMDD.jsonl`

### Required dashboard panels
1. Harvest success rate by provider:
   - `harvest_finalized / harvest_started`
2. Median finalize latency:
   - `finalized_at - prompt_sent_at`
3. Source contribution:
   - `% finalized from answer_id/export/wait/dom`
4. Quality gate failures by reason:
   - `stub`, `low_similarity`, `unbalanced_fence`, `too_short`, `truncated`
5. Blocked circuit impact:
   - skipped attempts due to provider blocked state
6. Retry pressure:
   - attempts/job p50 p90

### Suggested SLOs
- chatgpt harvest finalize success >= 98%
- gemini harvest finalize success >= 97%
- qwen harvest finalize success >= 97%
- false finalize rate <= 0.2%

## Safety controls
- strict allowlist of read-only tools for harvester:
  - `*_wait`
  - `chatgpt_web_answer_get`
  - `chatgpt_web_conversation_export`
  - `*_blocked_status`
- explicit denylist:
  - `*_ask`
  - `*_regenerate`
  - `*_refresh` (except controlled diagnostics mode)
- circuit breaker:
  - when provider blocked cooldown active, postpone harvest instead of hammering UI.

## Rollout plan

### Phase H0 (shadow mode)
- Harvester computes candidate + score but does not override answer.
- Emits events/metrics only.
- Duration: 24h soak.

### Phase H1 (assist mode)
- Harvester may finalize only if quality score improves existing answer by threshold.
- Keep worker existing finalize path as primary.

### Phase H2 (authoritative mode)
- Harvester becomes authoritative for final answer consolidation.
- Worker finalize path simplified to enqueue harvest signal.

## Merge-ready checklist
- tests:
  - `test_harvest_quality_gate.py`
  - `test_harvest_state_machine.py`
  - `test_harvest_readonly_tool_allowlist.py`
  - `test_harvest_provider_strategy_chatgpt.py`
  - `test_harvest_provider_strategy_gemini.py`
  - `test_harvest_provider_strategy_qwen.py`
- no contract regression on `tests/test_contract_v1.py`
- no tool schema drift in `tests/test_mcp_tool_registry_snapshot.py`

## 12h soak checklist
- no prompt send from harvester (`ask` tool calls count must be zero).
- harvest finalize success meets SLO floor.
- `conversation_export_failed` trend does not worsen.
- blocked-related retry storms are reduced.
- no duplicate prompt incidents.

## Open decisions for implementation
1. DB column vs file-only `harvest_state`:
   - preferred: DB column + artifact mirror.
2. provider-specific export availability:
   - if Gemini/Qwen export unavailable, keep wait/snapshot-only mode first.
3. whether to expose harvest metrics in `/v1/ops/status`:
   - recommended yes, behind optional compact fields.
