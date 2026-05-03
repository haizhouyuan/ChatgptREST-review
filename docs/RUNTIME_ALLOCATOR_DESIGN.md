# Runtime Allocator Agent - Cross-Company Design

Created: 2026-05-03
Updated: 2026-05-03 (incorporated ChatGPT Pro review)
Status: design -> implementation

## Purpose

The Runtime Allocator is a **deterministic service + explainable agent** that:
1. Routes tasks to the optimal runtime based on capability matching
2. Tracks quota consumption across paid runtimes via reservation system
3. Implements automatic fallback with task-risk-aware policies
4. Logs all routing decisions for audit

**Key principle**: Core quota, circuit-breaking, fallback, reservation must be CODE, not LLM.
LLM can explain routing decisions but should not make them.

## Available Runtimes

| Runtime | Endpoint | Strengths | Privacy Tier | Quota Model |
|---------|----------|-----------|--------------|-------------|
| claudekimi | Xiaomi MiMo proxy | Code, reasoning, structured output, tool use | external_cloud | Paid API (opaque headers) |
| gemini_local | Gemini CLI v0.39.1 | Text gen, frontend, creative, multilingual, Google Search grounding | external_cloud | Free tier: 60 RPM, 1000 RPD (Pacific midnight reset) |
| HomePC GPU0 | Ollama :11434 | Free, private, GPU-accelerated, embeddings, classification | local | 24GB VRAM cap |
| HomePC GPU1 | Ollama :11435 | Free, private, GPU-accelerated, benchmark, fallback | local | 24GB VRAM cap |
| MiniMax | api.minimaxi.com/v1 | Fast, Chinese-optimized, cheap | external_cloud | Paid API |

## Task Classification Matrix

| Task Type | Primary | Secondary | Fallback | Rule |
|-----------|---------|-----------|----------|------|
| FINBOT final synthesis | claudekimi | gemini_local review | Ollama summary only | Primary unavailable -> HOLD/HUMAN_REVIEW |
| FINBOT Risk Manager veto | claudekimi | **no fallback** | local deterministic calc only | Risk review failure = do not trade |
| FINBOT analyst fan-out | News: gemini_local, Fund: claudekimi, Tech: deterministic | cross-check | Ollama extraction | Analyst stage can be cheap; final synthesis cannot |
| Bull/Bear debate | claudekimi | Gemini cross-check | not recommended | Fixed 2-3 rounds, avoid token runaway |
| Frontend/UI | gemini_local | claudekimi review | Ollama for lint | Gemini CLI for file/CLI/web tasks |
| Code architecture | claudekimi | gemini_local critique | local coder patch draft | High complexity -> deep reasoning first |
| Long document/meeting | gemini_local | claudekimi synthesis | Ollama summarization | Local compress first, then cloud synthesize |
| HR sensitive data | local Ollama or redacted | claudekimi after redaction | local preferred | HR PII never leaves local/private |
| Memory indexing | local Ollama embeddings | cloud eval sample only | local | Batch tasks run locally |
| Benchmark/eval batch | HomePC Ollama | cloud sample grading | local | Don't burn cloud quota on mass eval |
| Runtime Allocator | **deterministic Python** | small LLM for explanation only | local | Allocator must not depend on LLM to route |

## Data Model

```sql
CREATE TABLE runtime_provider (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,          -- xiaomi_mimo, gemini, ollama, minimax
  endpoint TEXT NOT NULL,
  auth_ref TEXT NOT NULL,          -- vault key ref, NOT raw secret
  privacy_tier TEXT NOT NULL,      -- local, private_cloud, external_cloud
  enabled BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE model_profile (
  id TEXT PRIMARY KEY,
  runtime_provider_id TEXT REFERENCES runtime_provider(id),
  model_name TEXT NOT NULL,
  capabilities JSONB NOT NULL,     -- code, reasoning, json, tool_calling, vision, long_context
  max_context_tokens INT,
  supports_tools BOOLEAN,
  supports_json BOOLEAN,
  cost_in_per_mtok NUMERIC,
  cost_out_per_mtok NUMERIC,
  quality_scores JSONB,            -- internal eval scores by task class
  latency_p50_ms INT,
  latency_p95_ms INT,
  updated_at TIMESTAMP NOT NULL
);

CREATE TABLE quota_window (
  id BIGSERIAL PRIMARY KEY,
  provider_id TEXT REFERENCES runtime_provider(id),
  model_name TEXT,
  dimension TEXT NOT NULL,         -- RPM, TPM, RPD, TPD, GPU_SLOT, VRAM_MB, QUEUE_DEPTH
  limit_value BIGINT,
  used_value BIGINT NOT NULL DEFAULT 0,
  reserved_value BIGINT NOT NULL DEFAULT 0,
  reset_at TIMESTAMP,
  source TEXT NOT NULL,            -- api_header, docs, inferred, manual
  updated_at TIMESTAMP NOT NULL
);

CREATE TABLE route_event (
  id UUID PRIMARY KEY,
  request_id UUID NOT NULL,
  agent_name TEXT NOT NULL,
  task_class TEXT NOT NULL,
  selected_provider TEXT NOT NULL,
  selected_model TEXT NOT NULL,
  fallback_chain JSONB,
  est_input_tokens INT,
  est_output_tokens INT,
  actual_input_tokens INT,
  actual_output_tokens INT,
  cost_usd NUMERIC,
  latency_ms INT,
  status TEXT,                     -- success, retry, fallback, blocked, human_review
  error_code TEXT,
  created_at TIMESTAMP NOT NULL
);
```

## RouteRequest / RouteDecision Schema

```python
from pydantic import BaseModel, Field
from typing import Literal

class RouteRequest(BaseModel):
    request_id: str
    agent_name: str
    task_class: Literal[
        "finbot_news", "finbot_fundamental", "finbot_technical",
        "finbot_debate", "finbot_trade_proposal", "finbot_risk_veto",
        "frontend", "code_reasoning", "meeting_summary",
        "hr_sensitive", "document_draft", "memory_indexing", "benchmark"
    ]
    privacy_tier_required: Literal["local_only", "private_ok", "external_ok"]
    min_quality_tier: Literal["cheap", "standard", "high", "critical"]
    needs_tool_calling: bool = False
    needs_json: bool = True
    max_latency_ms: int | None = None
    max_cost_usd: float | None = None
    input_tokens_est: int
    output_tokens_est: int
    can_degrade: bool = True
    high_stakes: bool = False

class RouteDecision(BaseModel):
    provider_id: str
    model_name: str
    endpoint: str
    reservation_id: str
    fallback_chain: list[str]
    reason_codes: list[str]
    requires_human_review: bool = False
    blocked: bool = False
```

## Allocation Algorithm

```python
def allocate(req: RouteRequest) -> RouteDecision:
    candidates = registry.models_enabled()

    # 1. Hard filters
    candidates = [
        m for m in candidates
        if m.privacy_tier <= req.privacy_tier_required
        and (not req.needs_tool_calling or m.supports_tools)
        and (not req.needs_json or m.supports_json)
        and m.max_context_tokens >= req.input_tokens_est + req.output_tokens_est
    ]

    # 2. Policy filters
    if req.task_class == "finbot_risk_veto":
        candidates = [m for m in candidates if m.quality_tier == "critical"]
        req.can_degrade = False

    if req.task_class == "hr_sensitive":
        candidates = [m for m in candidates if m.privacy_tier in ["local", "private_cloud"]]

    # 3. Quota preflight
    candidates = [
        m for m in candidates
        if quota.can_reserve(
            provider=m.provider_id,
            model=m.model_name,
            rpm=1,
            tpm=req.input_tokens_est + req.output_tokens_est,
            rpd=1
        )
    ]

    # 4. Score
    scored = []
    for m in candidates:
        score = (
            4.0 * quality_score(m, req.task_class)
            - 1.5 * normalized_cost(m, req)
            - 1.0 * normalized_latency(m)
            - 2.0 * quota_pressure(m)
            + 0.5 * cache_hit_bonus(m, req)
            + 0.5 * locality_bonus(m, req)
        )
        scored.append((score, m))

    if not scored:
        return fallback_or_block(req)

    selected = max(scored, key=lambda x: x[0])[1]
    reservation = quota.reserve(selected, req)

    return RouteDecision(
        provider_id=selected.provider_id,
        model_name=selected.model_name,
        endpoint=selected.endpoint,
        reservation_id=reservation.id,
        fallback_chain=build_fallback_chain(req, selected),
        reason_codes=explain(selected, req),
        requires_human_review=req.high_stakes and selected.quality_tier != "critical"
    )
```

## Quota Reservation

Must follow: estimate -> reserve -> execute -> commit/refund

```
preflight:
  estimate input/output tokens
  reserve RPM=1, TPM=input+output_budget, RPD=1

execute:
  call runtime

commit:
  subtract actual tokens
  refund unused reservation
  update latency/error/cost

on 429:
  mark quota_window as exhausted
  infer reset_at if provider gives header
  otherwise exponential backoff + dynamic cooldown
```

For opaque providers (claudekimi proxy), use inferred token bucket:
```python
if status_code == 429:
    bucket.capacity = max(bucket.capacity * 0.8, minimum_capacity)
    bucket.cooldown_until = now + ewma_retry_after()
```

## Fallback Policy (Risk-Aware)

| Scenario | Fallback |
|----------|----------|
| Document draft, meeting summary | gemini_local -> claudekimi -> ollama, mark quality level |
| Code patch | Can fallback, must run tests |
| FINBOT analyst report | Can fallback, needs Data Quality recheck |
| FINBOT debate | Fallback to another high-reasoning model; weak model -> INSUFFICIENT_CAPABILITY |
| FINBOT trade proposal | Fallback -> must enter human review |
| FINBOT risk veto | **No weak model fallback**; primary unavailable -> VETO_OR_HUMAN_REVIEW |
| Broker execution | **No model fallback**; only deterministic order-state recovery |

## Circuit Breakers

```yaml
circuit_breakers:
  external_cloud:
    open_if:
      error_rate_5m: "> 0.20"
      p95_latency_ms: "> 60000"
      rate_limit_count_5m: "> 5"
    half_open_after_sec: 120

  ollama_gpu:
    open_if:
      gpu_vram_free_mb: "< 1500"
      queue_depth: "> 20"
      temperature_c: "> 85"
    half_open_after_sec: 60
```

## HomePC Dual GPU Setup

Run as 2 independent Ollama workers (NOT auto-combined 48GB):
```bash
# GPU0
CUDA_VISIBLE_DEVICES=0 OLLAMA_HOST=0.0.0.0:11434 ollama serve
# GPU1
CUDA_VISIBLE_DEVICES=1 OLLAMA_HOST=0.0.0.0:11435 ollama serve
```

## Integration Points

- Paperclip agents declare `preferredRuntime` and `fallbackRuntimes` in adapterConfig
- Runtime Allocator reads Paperclip API for agent configs
- Runtime Allocator monitors heartbeat run results for failure signals
- Runtime Allocator can update agent adapterType via Paperclip PATCH API
- All route events logged to `route_event` table for audit

## Implementation Plan

### Phase 1: Static Routing (Current)
- Each agent has a fixed adapterType
- Manual fallback (human switches)

### Phase 2: Quota Ledger + Health Monitoring (Next)
- Implement quota_window tracking
- Periodic health checks on each runtime
- Track success/failure rates per runtime

### Phase 3: Dynamic Routing
- Runtime Allocator receives RouteRequest
- Runs allocation algorithm
- Implements automatic fallback on failure

### Phase 4: Quota Intelligence
- Predict daily/weekly budget exhaustion
- Proactively shift load before quota runs out
