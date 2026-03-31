# Bootstrap System — Critical Self-Review (Pre-Implementation)

> Date: 2026-03-31
> Purpose: Address all 5 user findings + identify additional architectural risks before writing code

## Finding Response Matrix

### Finding 1 (HIGH): MCP URL Ingress Drift

**Root cause**: Confused liveness probing with agent entry point. These are two separate concerns.

**Fix**: `runtime_registry.yaml` must separate:
- `liveness_url`: `http://127.0.0.1:18712/` — only used internally by bootstrap health check
- `agent_entry_url`: `http://127.0.0.1:18712/mcp` — what appears in bootstrap JSON output

The bootstrap JSON output will have `agent_entry_url` under `agent_instructions`, and the liveness URL stays internal to the health check logic. An agent reading the bootstrap packet should NEVER see a bare non-`/mcp` URL as a callable surface.

**Verification**: grep the final output JSON for `18712` — every occurrence must end with `/mcp` except inside `runtime_health.checks[]`.

---

### Finding 2 (HIGH): "Relevant Symbols & Tests" Claimed But Not Delivered

**Root cause**: Dishonest scope statement. I listed 5 layers but Phase 1 design only delivers 4.

**Decision**: Include GitNexus integration in Phase 1, with graceful degradation.

**Implementation**:
```python
def _probe_gitnexus(task: str, planes: list[str]) -> dict:
    """Optional GitNexus query via subprocess. Degrades to empty if unavailable."""
    try:
        # Uses the gitnexus MCP stdio binary, same as what agents/AGENTS.md tells agents to use
        result = subprocess.run(
            ["npx", "gitnexus", "query", "--json", "--query", task, "--limit", "3"],
            capture_output=True, timeout=15, cwd=REPO_ROOT
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return {"status": "unavailable", "reason": "gitnexus not running or timed out"}
```

**Degradation model**:
- GitNexus running → `task_relevant_symbols` populated with process matches + file paths
- GitNexus not running → `task_relevant_symbols.status = "unavailable"`, agent gets instruction to query GitNexus manually
- This is honest: Phase 1 delivers the full vision when conditions allow, and degrades explicitly

---

### Finding 3 (MEDIUM): 4-Plane Model Conflicts with Canonical 5-Plane Matrix

**Root cause**: I compressed the model for "simplicity" without checking ground truth.

**Canonical 5-plane model** (from `docs/ops/2026-03-25_agent_maintainer_entry_v1.md` lines 12-16):

| Plane | Description | Key Code Paths |
|---|---|---|
| `execution` | `/v1/jobs`, send/wait, blocked/cooldown, job artifacts | `chatgptrest/api/routes_jobs.py`, `chatgptrest/worker/worker.py`, `chatgptrest/executors/*` |
| `public_agent` | Codex/Claude/Antigravity default entry, public MCP | `chatgptrest/mcp/agent_mcp.py`, `chatgptrest/api/routes_agent_v3.py` |
| `advisor` | Advisor, report, funnel, memory, KB | `chatgptrest/advisor/*`, `chatgptrest/kernel/*`, `chatgptrest/kb/*` |
| `controller_finbot` | Guardian, orch, finbot, controller lane | `ops/openclaw_*`, `chatgptrest/finbot.py` |
| `dashboard` | 8787 dashboard, control plane read model | `chatgptrest/dashboard/*`, `chatgptrest/api/app_dashboard.py` |

**Fix**: plane_registry.yaml uses exactly these 5 planes with the same names and key paths.

---

### Finding 4 (MEDIUM): Obligation Paths Referencing Non-Existent Files

**Verification result**: All 5 test files I referenced DO exist in the current repo:
```
tests/test_mcp_server_entrypoints.py  (3297 bytes)
tests/test_contract_v1.py             (exists)
tests/test_health_probe.py            (exists)
tests/test_e2e.py                     (exists)
tests/test_agent_mcp.py               (exists)
```

However, the **principle is absolutely correct**: registries must not reference phantom paths. I will add a startup-time validation in the bootstrap engine that warns if any obligation path doesn't exist on disk.

**Implementation**: `_validate_obligations()` function that checks all `must_update` and `must_test` paths against the filesystem and emits `obligation_warnings` in the output.

---

### Finding 5 (MEDIUM): Private Function Import Coupling

**Root cause**: Taking a shortcut to avoid touching health_probe.py.

**GitNexus impact analysis** (verified):
- `_check_http`: only d=1 caller is `health_probe.py:main()`
- `_check_db`: only d=1 caller is `health_probe.py:main()`
- `_check_stuck_jobs`: only d=1 caller is `health_probe.py:main()`
- All contained within `ops/health_probe.py`. No external callers anywhere.

**Safe refactor path**:
1. Create `ops/health_checks.py` with public API: `check_http()`, `check_db()`, `check_stuck_jobs()`
2. Make `health_probe.py` import from `health_checks.py`
3. Make `bootstrap.py` import from `health_checks.py`
4. Run `tests/test_health_probe.py` to verify no regression

**Risk**: LOW — all callers are within `health_probe.py`, and tests exist.

---

## Additional Critical Findings I Identified

### Finding 6: YAML Introduces Format Inconsistency?

**Analysis**: The repo already uses YAML extensively via `yaml.safe_load`:
- `chatgptrest/kernel/role_loader.py` — loads `config/agent_roles.yaml`
- `chatgptrest/kernel/team_catalog.py` — loads team configs
- `chatgptrest/kernel/topology_loader.py` — loads topology
- `chatgptrest/kernel/work_memory_policy.py` — loads policy
- `chatgptrest/dashboard/service.py` — dashboard config
- `chatgptrest/finbot.py` — finbot config
- PyYAML confirmed available in `.venv`
- Existing loading pattern: `yaml.safe_load(open(path))` with `FileNotFoundError` handling

**Verdict**: YAML is the established pattern for config/registry in this codebase. Using JSON would be the inconsistency.

### Finding 7: Keyword-Based Plane Detection is Inherently Brittle

**Problem**: "Fix the advisor agent MCP tool" matches both `advisor` (keyword: "advisor") and `public_agent` (keyword: "mcp"). Which wins?

**Mitigation**:
- Return ALL matching planes ranked by confidence score (keyword hit count / total keywords)
- Never claim a single authoritative plane — always return `detected_planes: [{name, confidence}]`
- Include a fallback: `"If uncertain, consult docs/ops/2026-03-25_agent_maintainer_entry_v1.md §2 Step 2"`
- Plane detection is a **hint**, not a gate — all docs are accessible regardless

### Finding 8: Bootstrap Script Discoverability

**Problem**: How does a new agent even know to run `scripts/chatgptrest_bootstrap.py`?

**Mitigation**: Add a 2-line section to AGENTS.md:
```markdown
## Bootstrap (Machine-First Entry)
python scripts/chatgptrest_bootstrap.py --task "your task description" --json
```

This is minimal and doesn't bloat AGENTS.md further.

### Finding 9: Obligation Checker Without Enforcement is Informational-Only

**Reality check**: Phase 1's obligation output is advisory. Agents CAN ignore it. Real enforcement requires:
- Phase 2: Wire into task-closeout workflow
- Future: Pre-commit hook that checks obligations

For Phase 1, this is acceptable — the bootstrap packet at least surfaces the obligations. But I should NOT claim it "enforces" anything.

---

## Revised Architecture Decision Record

| Decision | Rationale |
|---|---|
| 5 planes matching canonical model | Ground truth alignment; zero "second truth" drift |
| YAML for registries | Matches existing codebase pattern (role_loader, team_catalog, etc.) |
| GitNexus integration with graceful degradation | Delivers on "code graph" goal; doesn't create hard dependency |
| Thin `health_checks.py` public API | Stable contract; both health_probe and bootstrap share it |
| Separate liveness_url / agent_entry_url | Prevents ingress drift; MCP entry is always `/mcp` |
| Keyword plane detection returns ranked list | No false certainty; agent can override |
| Obligation validation against filesystem | Prevents phantom path references |

## Risk Assessment

| Risk | Level | Mitigation |
|---|---|---|
| health_checks.py extraction breaks health_probe timer | LOW | All callers internal; tests exist; run before commit |
| GitNexus subprocess hangs | LOW | 15s timeout; graceful degradation |
| Keyword plane detection gives wrong result | MEDIUM | Returns ranked list, not single answer; includes fallback doc reference |
| PyYAML import fails | LOW | Already used by 6+ modules; venv-confirmed |
| Bootstrap output becomes stale | MEDIUM | `generated_at` + `head_commit` let consumers detect staleness |
