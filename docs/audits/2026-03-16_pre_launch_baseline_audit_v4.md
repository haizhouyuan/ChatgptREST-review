# Pre-Launch Baseline Audit — 2026-03-16 (v4 — Codex Round 3 Final)

**Auditor:** Antigravity  
**Reviewer:** Codex (3 rounds of independent review)  
**Branch:** `feature/routing-funnel-improvements`  
**Head:** `2f8c7b3`

---

## Executive Summary

| Area | Status | Notes |
|------|--------|-------|
| API (18711) | ✅ UP | Auth enforced (401); alive |
| Dashboard (8787) | ✅ UP | 200 OK, 6729 roots |
| MCP Adapter (18712) | ✅ UP | 404 on `/` = expected (FastMCP SSE) |
| JobDB | ✅ HEALTHY | 29 tables |
| Stuck Jobs | ✅ OK | 0 stuck (report-only, no mutation) |
| KB FTS | ✅ HEALTHY | 938 docs |
| Memory | ✅ HEALTHY | 2,811 records |
| health-probe.service | ✅ `status=0/SUCCESS` | Timer-triggered, non-destructive |
| ui-canary.service | ✅ `status=0/SUCCESS` | Snapshot refreshed, exit 0 |
| UI Canary (chatgpt) | ❌ BLOCKED | consecutive_failures=2 |
| UI Canary (gemini) | ⚠️ STALE | maint_daemon not running probes |

---

## Changes Across 3 Codex Review Rounds

### Round 2 → Round 3 (`441c180` → `2f8c7b3`)

| Finding | Severity | Fix |
|---------|----------|-----|
| `--fix` force-errors leased jobs | Critical | `--fix` is report-only; mutation requires `--fix --apply`; active leases never touched |
| `ui_canary` exit 1 on degraded providers | High | exit 0 when snapshot refreshed; exit 1 only when sidecar itself fails |
| HTTP 500/503 counted as alive | Medium | Only 401/403/404/405 confirm liveness; 5xx = unhealthy |

### Design Principles Applied

1. **Separation of observation and action**: `--fix` reports candidates; `--apply` mutates. Timer only uses `--fix`.
2. **Lease sovereignty**: Active lease = lease holder decides. Health probe never overrides.
3. **Sidecar success = its own job done**: Refreshing the snapshot IS the sidecar's job; provider health is data.
4. **Strict liveness**: Only expected 4xx (auth/path) confirms alive; server errors do not.

---

## Systemd Verification

```
health-probe: code=exited, status=0/SUCCESS
  7/7 PASS, --fix CANDIDATES: 0

ui-canary: code=exited, status=0/SUCCESS
  DEGRADED (snapshot refreshed)
  chatgpt: consecutive_failures=2
  gemini: stale (85125s since last probe)
```

---

## Remaining P1 Actions

| Action | Status |
|--------|--------|
| Restart maint_daemon for fresh ui_canary probes | Open |
| Clear chatgpt blocked cooldown state | Open |
