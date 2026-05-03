# Paperclip Agent Configuration - ChatGPT Pro Review

Date: 2026-05-03
Source: ChatGPT Pro Extended (gpt-5-5-pro)
Conversation: https://chatgpt.com/c/69f7750c-f1ac-839d-b275-3cc09dd69ac3

## Summary of Key Recommendations

### P0 Missing Roles (must add)
1. **Data Quality & Provenance Agent** - Gate before debate, checks staleness/source/corporate actions
2. **Compliance / Audit Officer** - Trading policy, restricted list, PII redaction, audit log, veto power
3. **Execution Controller / Fund Manager** - Only agent with broker write, requires human approval
4. **Finbot Backtest / Simulation Agent** - Walk-forward backtest, paper trading, slippage/fees
5. **AgentOps / SRE** - LangGraph runs, runtime health, token/cost, incident replay

### Key Design Decisions
- Risk Manager fallback: always VETO on degraded model (never allow weak model to approve trades)
- Broker write: only Execution Controller, default human approval required
- Runtime Allocator: deterministic code, not LLM (quota ledger + reservation)
- Bull/Bear debate: fixed 2-3 rounds with structured JSON, not open-ended chat
- All FINBOT outputs must have audit fields (runtime, as_of, confidence, schema version)
- claudekimi should be decomposed: client/provider/model/account/quota
- HomePC 2x RTX 3090: run as 2 separate Ollama workers (not auto-combined 48GB)

### Rollout Order
1. Control plane (Runtime Allocator, Data Quality, Security, Observability, Audit)
2. Read-only FINBOT (analysts -> debate -> proposal -> veto, no orders)
3. Paper trading (simulated execution, PnL attribution)
4. Human-approved live execution
5. Selective automation (low-risk only)

## Full Answer
See conversation URL above for the complete 43,622-char answer with:
- 16 MCP server definitions
- Per-agent MCP/skill allocation table
- Runtime matrix (task type -> primary/secondary/fallback)
- Runtime Allocator SQL schema + Pydantic models + allocation algorithm
- Finbot LangGraph graph (mermaid)
- Structured output schemas for all analyst/researcher/trader/risk roles
- Deterministic pre-trade checks
- Circuit breaker configuration
