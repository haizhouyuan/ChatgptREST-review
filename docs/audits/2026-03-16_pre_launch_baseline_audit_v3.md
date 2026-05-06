# Pre-Launch Baseline Audit — 2026-03-16 (v3 — Post Codex Review)

**Auditor:** Antigravity  
**Reviewer:** Codex (two rounds of independent review)  
**Branch:** `feature/routing-funnel-improvements`  
**Timestamp:** 2026-03-16T15:08:00+08:00

> [!IMPORTANT]
> v3 incorporates Codex's critical review of v2, which identified:
> - health_probe's `--fix` was dangerously ignoring updated_at/not_before/leases
> - ui_canary_sidecar was calling an unreachable HTTP endpoint (driver MCP is stdio-only)
> - consecutive_failures=0 was hardcoded, defeating consumer failure detection
> - Factual errors in v2 about scripts "never in git" and "all green"

---

## Executive Summary

| Area | Status | Notes |
|------|--------|-------|
| API (18711) | ✅ UP | Auth enforced; advisor v3 also on this port |
| Dashboard (8787) | ✅ UP | Health: `ready`, 6730 roots |
| MCP Adapter (18712) | ✅ UP | FastMCP SSE transport (404 on `/` = expected) |
| JobDB | ✅ HEALTHY | 29 tables accessible |
| Stuck Jobs | ✅ OK | 1 stale `needs_followup` (idle 8250s, correctly detected via `updated_at`) |
| KB FTS | ✅ HEALTHY | 938 documents |
| Memory | ✅ HEALTHY | 2,809 records |
| UI Canary (chatgpt) | ❌ BLOCKED | consecutive_failures=2, blocked cooldown from 2026-03-15 |
| UI Canary (gemini) | ⚠️ STALE | Last probe 84427s ago — maint_daemon not running |

---

## Corrections from v2

### 1. health_probe --fix Rewritten (v2 was CRITICAL)

v2's `--fix` blindly forced every `in_progress`/`needs_followup`/`blocked`/`cooldown` job older than 1h (by `created_at`) to `error`, ignoring `updated_at`, `not_before`, active leases, and legitimate long-running waits.

v3 uses `classify_stuck_wait_job()` from `chatgptrest.ops_shared.queue_health`:
- Respects `updated_at` (recently updated = not stuck)
- Respects `not_before` (in backoff = not stuck)
- Respects `lease_owner` + `lease_expires_at` (actively leased = escalate, not error)
- Non-wait stale jobs checked against `updated_at` (not `created_at`)

### 2. ui_canary_sidecar Redesigned (v2 was HIGH)

v2 tried to HTTP-call the driver MCP on port 18710 — which is a stdio-based process and has no HTTP listener. Connection always refused.

v3 reads `state/maint_daemon_state.json` (the authoritative source) and refreshes `latest.json` with the correct metadata:
- `consecutive_failures` preserved from maint_daemon's stateful tracking
- Stale detection when daemon hasn't probed recently
- Full state snapshot included for consumer compatibility

### 3. Factual Corrections

- **"Never in git"**: Git history shows tracked prior versions existed. Corrected to "deleted in PR #199".
- **"All green"**: UI canary sidecar now correctly reports chatgpt blocked (consecutive_failures=2) and gemini stale. Not all green.

---

## Commits

| Hash | Description |
|------|-------------|
| `36f828c` | Initial (flawed) health_probe + ui_canary_sidecar |
| `ef0b4bc` | Audit v2 |
| `441c180` | Rewritten health_probe + ui_canary with correct semantics |

---

## Remaining Pre-Launch Actions

| Priority | Action | Status |
|----------|--------|--------|
| **P1** | Restart maint_daemon to refresh ui_canary probes | Open |
| **P1** | Clear chatgpt blocked cooldown state | Open |
| **P2** | Fix time-bound test `test_build_release_bundle_*` | Open |
| **P2** | Run full test suite on capable machine | Open |
