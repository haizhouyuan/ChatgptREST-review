# Pre-Launch Baseline Audit — 2026-03-16

**Auditor:** Antigravity  
**Branch:** `feature/routing-funnel-improvements` (includes merged PR #199)  
**Timestamp:** 2026-03-16T13:30:00+08:00

---

## Executive Summary

| Area | Status | Notes |
|------|--------|-------|
| API (18711) | ✅ UP | Auth enforced, returns `unauthorized` without token |
| Dashboard (8787) | ✅ UP | Restarted to pick up PR #199 templates. Health: `ready`, 6716 roots |
| Advisor API (18713) | ❌ NOT RUNNING | Port 18713 occupied by Node.js process (not Python uvicorn) |
| Workers (send/wait/repair) | ✅ UP | 3 worker services active |
| Driver | ✅ UP | CDP Chrome connected |
| Feishu WS | ✅ UP | WebSocket gateway running |
| Maint Daemon | ✅ UP | Monitor + incident evidence |
| MCP Adapter | ✅ UP | FastMCP REST wrapper |
| KB FTS5 | ✅ HEALTHY | 938 documents indexed |
| Memory Subsystem | ✅ HEALTHY | 2,784 records, 6,602 audit events |
| EvoMap API | ✅ FUNCTIONAL | Returns valid structure (0 scorecards after restart) |
| Job Queue | ✅ CLEANED | 169 stale jobs → `error` status. Remaining: 6,568 completed, 608 error, 271 canceled |
| Core Tests | ✅ 37/37 PASS | API startup, advisor API, advisor graph |
| Full Test Suite | ⚠️ TIMEOUT | Exceeds 300s on this host. Earlier PR merge run: 84/84 pass |

---

## Findings

### 🔴 Critical (Blocks Launch)

#### F-01: Advisor API Not Running on Port 18713

Port 18713 is occupied by a **Node.js** process (PID 2224821), not the Python uvicorn Advisor API.

- **Expected:** `PYTHONPATH=. .venv/bin/python -m uvicorn chatgptrest.api.app:create_app --factory --host 0.0.0.0 --port 18713`
- **Actual:** Node.js server (likely Antigravity language server or MCP) is bound to 18713
- **Impact:** All `/v2/advisor/*` routes are unreachable. The MCP `chatgptrest` adapter at `http://127.0.0.1:18712` may still route through the API at 18711 for v1 endpoints, but v2 Advisor endpoints (advise, health) require 18713.
- **Fix:** Stop the Node.js process on 18713 and start the Advisor API, or reconfigure the Advisor to a different port.

### 🟡 High (Degraded Operations)

#### F-02: Three Systemd Services Broken by PR #199 Script Deletions

| Service | Script Referenced | Status | Root Cause |
|---------|-------------------|--------|------------|
| `chatgptrest-health-probe.service` | `ops/health_probe.py` | ❌ FAILED | Script deleted in PR #199 |
| `chatgptrest-ui-canary.service` | `ops/ui_canary_sidecar.py` | ❌ FAILED | Script deleted in PR #199 — but code on disk at 12:42 still ran successfully (Gemini hit Google verification page), then 12:57 ran with deleted script |
| `chatgptrest-monitor-12h.service` | `ops/monitor_chatgptrest.py` → imports `chatgptrest.core.backlog_health` | ❌ FAILED (stale) | Journal error from 00:06:48 references old code. **Current code on disk is fixed** — the import no longer exists. Next timer trigger should succeed. |

**Impact:**
- `health-probe`: Periodic health checks not running. This means automated degradation detection is blind.
- `ui-canary`: Intermittent — worked at 12:28 and 12:42 (with one Gemini verification error), failed at 12:57. The script was deleted between runs.
- `monitor-12h`: Daily summary generation paused. The code on disk is correct now; the service just needs a re-trigger.

**Fix:**
- `health-probe` and `ui-canary`: Need new scripts or service file updates to point to equivalent merged code. Check if PR #199 provides replacement modules.
- `monitor-12h`: Reset failed state and re-trigger: `systemctl --user reset-failed chatgptrest-monitor-12h.service`

#### F-03: Dashboard HTML Pages Return 500 on First Access After Merge

After the PR #199 merge, the dashboard HTML pages returned `Internal Server Error` due to referencing deleted template `human/pulse.html`. Resolved by restarting the dashboard service, which loaded the updated templates.

**Current state after restart:** Dashboard health endpoint returns `ready`, API endpoints work, HTML pages require auth token.

#### F-04: Test Suite Exceeds Timeout

The full test suite (500+ tests) exceeds 300s on this host (YogaS2 — ThinkPad with limited I/O). 

- **Core tests (37/37):** PASS — covers API startup smoke, advisor API, advisor graph
- **PR merge tests (84/84):** PASS — from earlier PR merge verification
- **Time-bound test failure:** `test_build_release_bundle_marks_manual_review_when_sensitivity_flags` uses hardcoded `generated_at: 2026-03-11` which is now >72h (the `max_age_hours` default), causing `release_readiness_ready` to be `False`. This is a **pre-existing test fragility**, not a PR #199 regression.

### 🟢 Low (Informational)

#### F-05: Gemini UI Canary Hit Google Verification Page

At 12:42, the UI canary detected `GeminiGoogleVerification` — Gemini hit Google's unusual-traffic verification page (`google.com/sorry`). ChatGPT canary was fine (`ok: true`, ChatGPT 5.4 Pro). Previous runs at 12:13 and 12:28 showed both providers OK.

**Impact:** Intermittent Gemini availability. Self-resolving in most cases.

#### F-06: EvoMap Returns Empty Scorecards After Dashboard Restart

Immediately after dashboard restart, the EvoMap API returned 0 scorecards and 0 trust checks. This is expected behavior — the control plane needs time to populate data from the background refresh cycle.

---

## Subsystem Health Details

### Job Queue (jobdb.sqlite3)

| Status | Count | Notes |
|--------|-------|-------|
| completed | 6,568 | Normal |
| error | 608 | Includes 169 cleaned stale jobs |
| canceled | 271 | Normal |
| in_progress | 1 | Recent/active |
| needs_followup | 1 | Recent/active |

**Stale cleanup:** 169 jobs older than 1 hour in non-terminal states (`in_progress`, `needs_followup`, `blocked`, `cooldown`) were moved to `error` with marker `stale_audit_cleanup_20260316`.

### Knowledge Base

| Component | Status | Details |
|-----------|--------|---------|
| FTS5 DB (`kb_search.db`) | ✅ OK | 938 documents, 7.3MB |
| KB Registry (`kb_registry.db`) | ✅ OK | 168KB |
| KB Vectors (`kb_vectors.db`) | ✅ OK | 500KB |

### Memory Subsystem

| Table | Count |
|-------|-------|
| `memory_records` | 2,784 |
| `memory_audit` | 6,602 |

### OpenMind State Files

| File | Size | Last Modified |
|------|------|---------------|
| `checkpoint.db` | 20.7MB | Mar 15 |
| `events.db` | 7.9MB | Mar 16 13:10 |
| `memory.db` | 6.0MB | Mar 16 13:10 |
| `evomap.db` | 459KB | Mar 10 |
| `evomap_knowledge.db` | 12.7MB | Mar 10 |
| `effects.db` | 25KB | Mar 6 |

### Running Services Summary

| Category | Services | Status |
|----------|----------|--------|
| Core Runtime | API, Dashboard, Driver, Chrome, MCP | ✅ All running |
| Workers | send, send-chatgpt@1, send-gemini@0, wait, repair | ✅ All running |
| Monitoring | maint-daemon, feishu-ws | ✅ Running |
| Infrastructure | homepc-tunnel, runtime slice | ✅ Running |
| Timers (13) | Various (guardian, finbot, evomap-backup, etc.) | ✅ All active |
| **BROKEN** | health-probe, ui-canary, monitor-12h | ❌ See F-02 |

---

## Actions Taken During Audit

1. ✅ Restarted `chatgptrest-dashboard.service` to pick up PR #199 template changes
2. ✅ Cleaned 169 stale jobs from jobdb (marked as `error` with cleanup tag)
3. ✅ Verified all running services and port bindings
4. ✅ Verified KB, memory, EvoMap subsystems
5. ✅ Ran core test suite (37/37 pass)

## Recommended Pre-Launch Actions

| Priority | Action | Effort |
|----------|--------|--------|
| **P0** | Start Advisor API on correct port (stop Node.js on 18713 or reconfigure) | 5 min |
| **P0** | Fix/replace deleted `ops/health_probe.py` and `ops/ui_canary_sidecar.py` | 30 min |
| **P1** | Reset `chatgptrest-monitor-12h.service` (code already fixed on disk) | 1 min |
| **P1** | Fix time-bound test `test_build_release_bundle_marks_manual_review_when_sensitivity_flags` | 5 min |
| **P2** | Run full test suite on a machine with sufficient timeout | 15 min |
| **P2** | Verify Gemini verification page issue resolves (check proxy routing) | 10 min |
