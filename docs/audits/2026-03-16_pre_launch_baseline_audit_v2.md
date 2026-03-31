# Pre-Launch Baseline Audit — 2026-03-16 (v2 — Corrected)

**Auditor:** Antigravity  
**Reviewer:** Codex (independent verification from finagent)  
**Branch:** `feature/routing-funnel-improvements` (includes merged PR #199)  
**Timestamp:** 2026-03-16T14:05:00+08:00

> [!IMPORTANT]
> This is v2 of the audit. v1 incorrectly classified the Advisor API as P0 not-running. 
> Independent review by Codex confirmed advisor serves on 18711 (not 18713). See corrections below.

---

## Executive Summary

| Area | Status | Notes |
|------|--------|-------|
| API (18711) | ✅ UP | Auth enforced; advisor v3 also on this port |
| Dashboard (8787) | ✅ UP | Restarted for PR #199. Health: `ready`, 6749 roots |
| Advisor API (18711) | ✅ UP | v3 health returns OK (kb=938, memory=2800) |
| Workers (send/wait/repair) | ✅ UP | 5 worker services active |
| Driver | ✅ UP | CDP Chrome connected |
| Feishu WS | ✅ UP | WebSocket gateway running |
| Maint Daemon | ✅ UP | Monitor + incident evidence + ui_canary built-in |
| MCP Adapter (18712) | ✅ UP | FastMCP SSE transport (404 on root = expected) |
| KB FTS5 | ✅ HEALTHY | 938 documents indexed |
| Memory Subsystem | ✅ HEALTHY | 2,802 records |
| EvoMap API | ✅ FUNCTIONAL | Returns valid structure |
| Job Queue | ✅ CLEANED | 169 stale jobs cleaned. 6,568 completed, 1 active |
| Health Probe | ✅ 7/7 PASS | Newly created, all checks green |
| Core Tests | ✅ 37/37 PASS | API startup, advisor API, advisor graph |

---

## Findings

### ~~F-01: Advisor API Not Running on Port 18713~~ → **REJECTED**

> **Correction (v2):** This finding was wrong. Independent verification by Codex confirmed:
> - Advisor v3 serves on **port 18711** (same as the main API). `curl http://127.0.0.1:18711/v2/advisor/health` returns `200 OK` with full v3 subsystem details.
> - Port 18713 is occupied by **GitNexus MCP** (Node.js), not a missing advisor.
> - The original audit incorrectly assumed advisor must be on 18713.

### F-02: Three Systemd Services Broken → **FIXED**

| Service | Root Cause | Fix Applied |
|---------|------------|-------------|
| `chatgptrest-health-probe` | `ops/health_probe.py` deleted, never in git | ✅ **Recreated** — 7 checks, `--fix` mode, writes `latest.json` |
| `chatgptrest-ui-canary` | `ops/ui_canary_sidecar.py` deleted, never in git | ✅ **Recreated** — probes driver MCP self_check per provider |
| `chatgptrest-monitor-12h` | Stale failure from old import path | ✅ **Reset** — `systemctl --user reset-failed` |

**Commits:** `36f828c` (health_probe.py + ui_canary_sidecar.py)

### F-03: Dashboard 500 → **RESOLVED**

Dashboard restarted to pick up PR #199 templates. Health endpoint returns `ready`, root count 6749.

### F-04: Time-Bound Test Fragility → **PRE-EXISTING**

`test_build_release_bundle_marks_manual_review_when_sensitivity_flags` uses a hardcoded `generated_at: 2026-03-11` which is now >72h old. Not a PR #199 regression.

---

## Health Probe Results (Post-Fix)

```
[2026-03-16T06:05:39Z] health_probe: PASS
  ✅ api_18711: alive (non-200 but reachable)
  ✅ dashboard_8787: 200 OK (ready, 6749 roots)
  ✅ mcp_18712: alive (non-200 but reachable)
  ✅ jobdb: 99 tables
  ✅ stale_jobs: 1 (needs_followup — recent active job)
  ✅ kb_fts5: 938 documents
  ✅ memory: 2,802 records
```

---

## Remaining Pre-Launch Actions

| Priority | Action | Status |
|----------|--------|--------|
| **P1** | Fix time-bound test `test_build_release_bundle_*` | Open |
| **P2** | Run full test suite on capable machine | Open |
| **P2** | Check Gemini verification page intermittency | Monitoring |
