# Comprehensive Test Plan for Product Convergence Backlog

Date: 2026-03-13  
Repo: ChatgptREST  
Backlog: `2026-03-12_product_convergence_execution_backlog_v1.md`  
Status: plan_draft

---

## Current Test Baseline

| Category | File Count | Coverage Level |
|----------|-----------|---------------|
| Advisor (graph, API, runtime, orchestrate) | 31 | Strong — happy path + integration |
| Report (graph, planning, execution) | 23 | Strong — report pipeline covered |
| OpenClaw (adapter, guardian, orch, telemetry) | 23 | Moderate — unit + smoke |
| Security (auth, rate limit, webhook) | 21 | Moderate — auth modes, rate limit |
| E2E (phase3/4/5, advisor e2e, evomap e2e) | 21 | Moderate — but tests are independent, not chained |
| Feishu (gateway, async, pipeline, webhook) | 20 | Moderate — gateway + webhook |
| KB (hub, retrieval, versioning) | 12 | Moderate — hub + vector |
| Memory (tenant isolation, business flow) | 6 | **WEAK** — only isolation + business flow |
| Health/Startup | 1 | **WEAK** — only `test_api_startup_smoke.py` |
| Contract compliance | 0 | **MISSING** — no cross-entry envelope test |
| Restart/Recovery | 0 | **MISSING** — no durable store survival test |
| Chaos/Resilience | 0 | **MISSING** — no process-crash simulation |
| Migration | 0 | **MISSING** — no schema migration test |

**Total: 325 files. Estimated 40% of convergence backlog tasks are testable with current infrastructure.**

---

## Test Plan Architecture

Seven layers, each with a clear purpose and a mapping to backlog Epics.

```
┌─────────────────────────────────────────────────┐
│ L7: Production Shadowing / Canary Test          │ → E11
├─────────────────────────────────────────────────┤
│ L6: Chaos / Resilience / Recovery Simulation    │ → E0, E3, E10-T5
├─────────────────────────────────────────────────┤
│ L5: Business Flow Simulation (E2E)              │ → E4, E8, E10-T4
├─────────────────────────────────────────────────┤
│ L4: Cross-Module Integration Tests              │ → E1, E2, E3, E4, E7
├─────────────────────────────────────────────────┤
│ L3: API Contract Compliance Tests               │ → E1, E10-T3
├─────────────────────────────────────────────────┤
│ L2: Security / Auth / Rate-Limit Tests          │ → E2, E9
├─────────────────────────────────────────────────┤
│ L1: Unit / Module Tests                         │ → E0, E3, E5, E6, E7
└─────────────────────────────────────────────────┘
```

---

## L1: Unit / Module Tests

### Purpose
Validate each module works correctly in isolation.

### L1-1: Health endpoint separation (E0-T3)

**File**: `tests/test_health_endpoints.py`

Scenarios:

1. `livez` returns 200 even when DB is down (process alive = pass)
2. `healthz` returns 503 when DB is unreachable
3. `readyz` returns 503 when DB is up but driver is not ready
4. `readyz` returns 200 only when both DB and driver are ready
5. Health response includes component-level status (`available/degraded/not_ready/broken`)

```python
# Simulation approach: mock sqlite3.connect to raise, mock _driver_readiness
def test_livez_always_200(client):
    """livez proves process is alive, even if DB is down."""
    with patch("sqlite3.connect", side_effect=Exception("DB gone")):
        resp = client.get("/livez")
    assert resp.status_code == 200

def test_readyz_fails_without_driver(client):
    """readyz checks both DB and driver."""
    with patch("chatgptrest.api.routes_jobs._driver_readiness", return_value={"ok": False}):
        resp = client.get("/readyz")
    assert resp.status_code == 503
    assert resp.json()["checks"]["driver"]["ok"] is False
```

### L1-2: Fail-closed startup (E0-T2)

**File**: `tests/test_startup_fail_closed.py`

Scenarios:

1. If v3 advisor router fails to load, process startup raises (not just warns)
2. If cognitive router fails to load, process startup raises
3. Startup logs include failed module name and exception type
4. Boot manifest lists all loaded routers

```python
def test_advisor_router_failure_crashes_startup():
    """Core router failure must crash the process, not silently degrade."""
    with patch("chatgptrest.api.routes_advisor_v3.make_v3_advisor_router",
               side_effect=ImportError("broken")):
        with pytest.raises(SystemExit):
            create_app()
```

### L1-3: Memory manager hardening (E3/E7)

**File**: `tests/test_memory_manager_comprehensive.py`

Scenarios:

1. Cross-tier dedup: staging a record that already exists in `episodic` does NOT overwrite it
2. Working capacity: after `WORKING_CAPACITY` records, oldest turn-pair is evicted
3. Conversation history: `limit=5` returns exactly 5 turns (10 messages)
4. TTL enforcement: expired records are not returned by any query
5. Promotion gate: `min_occurrences=2` blocks promotion if occurrence count is 1
6. Tenant isolation: two different `session_id` values never see each other's records
7. Identity where clause: records with different `agent`/`session_id` are not deduped

```python
def test_cross_tier_dedup_does_not_overwrite_existing(mm):
    """Staging a record MUST NOT overwrite an existing episodic record."""
    record = MemoryRecord(category="fact", key="fact:a", value={"v": 1}, confidence=0.8,
                          source={"type": "test", "session_id": "s1", "agent": "a1"})
    rid = mm.stage(record)
    mm.promote(rid, MemoryTier.EPISODIC)
    
    # Stage same fingerprint again — should create NEW staging record, not touch episodic
    record2 = MemoryRecord(category="fact", key="fact:a", value={"v": 2}, confidence=0.9,
                           source={"type": "test", "session_id": "s1", "agent": "a1"})
    rid2 = mm.stage(record2)
    
    # Original episodic record must be untouched
    episodic = mm.get_episodic(query="fact", limit=10)
    assert any(r["value"]["v"] == 1 for r in episodic)

def test_capacity_evicts_paired_turns(mm):
    """When capacity is full, eviction removes user+assistant pair."""
    for i in range(mm.WORKING_CAPACITY // 2 + 1):
        mm.add_conversation_turn("sess1", f"msg_{i}", f"reply_{i}", agent="a1")
    
    history = mm.get_conversation_history("sess1", limit=100)
    assert len(history) <= mm.WORKING_CAPACITY // 2  # turn count, not msg count
```

### L1-4: TraceStore durability (E3-T4)

**File**: `tests/test_trace_store_durable.py`

Scenarios:

1. Trace data survives simulated process "restart" (write → close → reopen → read)
2. Trace store handles concurrent writes without data loss
3. Trace list pagination works

### L1-5: Consult store durability (E3-T5)

**File**: `tests/test_consult_store_durable.py`

Scenarios:

1. Consultation state survives simulated restart
2. LRU eviction preserves most recent consultations
3. Concurrent consult creation is thread-safe

### L1-6: Rate limit durability (E3-T6)

**File**: `tests/test_rate_limit_durable.py`

Scenarios:

1. Rate limit state survives restart (or at least degrades safely)
2. Rate limit is per-IP, not per-request
3. Window expiry works correctly across midnight boundary

---

## L2: Security / Auth / Rate-Limit Tests

### L2-1: cc-control auth behind proxy (E2-T3)

**File**: `tests/test_cc_control_proxy_bypass.py`

Scenarios:

1. When `OPENMIND_CONTROL_API_KEY` is set: all requests require the key header
2. When key is NOT set + reverse proxy forwards as 127.0.0.1: request is REJECTED (not passed)
3. When key is NOT set + direct loopback: request is allowed
4. `_require_cc_control_access` uses `get_client_ip()` not `request.client.host`

```python
def test_cc_control_rejects_proxy_forwarded_loopback(client):
    """Reverse proxy makes everything look like 127.0.0.1 — cc-control must use real IP."""
    headers = {"X-Forwarded-For": "203.0.113.42"}
    # Mock request.client.host to return 127.0.0.1 (reverse proxy)
    resp = client.post("/v2/advisor/cc-control-test",
                       headers=headers)
    assert resp.status_code == 403  # NOT 200
```

### L2-2: Unified auth model (E2-T3)

**File**: `tests/test_unified_auth.py`

Scenarios:

1. All `/v2/advisor/*` endpoints enforce the same auth middleware
2. All `/v2/cognitive/*` endpoints enforce the same auth middleware
3. `/v1/jobs/*` endpoints enforce their own v1 auth
4. Auth-mode `strict` rejects unauthenticated requests with 503
5. Auth-mode `open` allows unauthenticated requests (development only)

### L2-3: Redact gate full-document coverage (security)

**File**: `tests/test_redact_gate_boundary.py`

Scenarios:

1. Sensitive content at position 0 is caught
2. Sensitive content at position 2999 (chunk boundary - 1) is caught
3. Sensitive content at position 3000 (chunk boundary) is caught
4. Sensitive content spanning positions 2998-3002 (cross-boundary) — verify detection
5. 10KB document with sensitive content at byte 9500 is caught

```python
def test_redact_catches_cross_boundary_secret():
    """api_key split across chunk boundary must still be detected."""
    safe_prefix = "A" * 2995
    poison = "api_key=sk-REAL_SECRET_KEY_12345"
    doc = safe_prefix + poison + "A" * 1000
    
    result = redact_gate({"internal_draft": doc, "external_draft": doc})
    assert result.get("redact_pass") is False
```

---

## L3: API Contract Compliance Tests

### L3-1: Unified envelope compliance (E1-T1)

**File**: `tests/test_api_contract_envelope.py`

Scenarios:

1. Every public endpoint returns the same top-level fields: `{status, data, error, trace_id, timestamp}`
2. Error responses follow the same shape: `{error: {code, message, detail}}`
3. Pagination responses include `{items, next_cursor, total}`
4. All endpoints include `X-Trace-Id` response header

### L3-2: Entry point inventory (E1-T2/T3)

**File**: `tests/test_entry_point_inventory.py`

Scenarios:

1. List all registered routes and assert against a whitelist
2. Every public route belongs to exactly one versioned family
3. No route handles both v1 and v2 semantics in the same handler
4. Legacy routes return deprecation warnings

```python
def test_no_duplicate_route_semantics(app):
    """Each business operation has exactly one canonical route."""
    routes = {r.path for r in app.routes if hasattr(r, 'path')}
    advise_routes = [r for r in routes if "advise" in r]
    # Should converge to one family
    assert len(advise_routes) <= 2, f"Too many advise routes: {advise_routes}"
```

---

## L4: Cross-Module Integration Tests

### L4-1: Identity resolution integration (E2-T2)

**File**: `tests/test_identity_resolution_integration.py`

Scenarios:

1. Request via `/v2/advisor/advise` resolves to canonical identity object
2. Request via Feishu gateway resolves to **same** identity format
3. Request via OpenClaw plugin resolves to **same** identity format
4. Degraded identity (missing fields) is typed and logged, not silently empty
5. Same `user_id` from different channels creates the same identity

### L4-2: Task → Run → Job lifecycle integration (E3)

**File**: `tests/test_lifecycle_integration.py`

Scenarios:

1. Submitting an advisor request creates: 1 task → 1 run → N jobs
2. Task status reflects run status: `run.COMPLETED → task.COMPLETED`
3. Task status reflects run failure: `run.FAILED → task.FAILED`
4. Recovery: orphaned run (no terminal status) triggers reconciliation
5. Replay: given `final_job_id`, the entire chain `job → run → task` can be replayed

```python
def test_full_lifecycle_happy_path(advisor_client, mock_llm):
    """Submit → task → run → job → answer → task.COMPLETED."""
    resp = advisor_client.post("/v2/advisor/advise", json={"message": "hello"})
    assert resp.status_code == 200
    trace_id = resp.json()["trace_id"]
    
    # Task created
    task = get_task_by_trace(trace_id)
    assert task["status"] in ("PENDING", "IN_PROGRESS")
    
    # Wait for completion
    wait_for_task_terminal(trace_id, timeout=30)
    task = get_task_by_trace(trace_id)
    assert task["status"] == "COMPLETED"
    assert task["runs"][-1]["status"] == "COMPLETED"
```

### L4-3: Feishu → Task pipeline integration (E4)

**File**: `tests/test_feishu_task_integration.py`

Scenarios:

1. Feishu message → task creation → advisor execution → reply delivery
2. Duplicate Feishu message_id → no duplicate task created
3. Attachment upload → task with attachment metadata
4. Fast ack → callback with interim status → final reply

### L4-4: Knowledge retrieval in hot path (E7)

**File**: `tests/test_knowledge_hot_path_integration.py`

Scenarios:

1. Advisor request triggers KB retrieval → context appears in LLM prompt
2. KB miss → advisor still produces answer (degraded, not broken)
3. Repo-aware context (GitNexus) participates when available
4. Retrieval precedence: canonical entry > fragmentary snippet

---

## L5: Business Flow Simulation (E2E)

### L5-1: Full product flow: user question → answer delivery

**File**: `tests/test_business_flow_advise.py`

```
Actors: User (Feishu), System (ChatgptREST), LLM (mocked)

1. User sends "分析今天的市场情况" to Feishu group
2. Feishu WS gateway receives message
3. System creates task with canonical identity
4. System routes to `quick_ask` pipeline
5. KB retrieval checks for existing market analysis
6. LLM generates answer
7. System stores answer, closes run, closes task
8. Feishu gateway delivers formatted reply
9. Memory captures conversation turn
10. Assertions:
    - task.status == COMPLETED
    - advisor_run.status == COMPLETED  
    - answer artifact exists
    - conversation turn in working memory
    - Feishu reply was sent
```

```python
def test_business_flow_feishu_to_answer(feishu_gateway, mock_llm, memory_manager):
    """Full business flow: Feishu message → task → LLM → answer → reply."""
    mock_llm.set_response("市场今天整体上涨，主要受AI板块带动...")
    
    # Simulate Feishu message
    msg = make_feishu_message(text="分析今天的市场情况", user_id="u_test", chat_id="c_test")
    feishu_gateway._process_and_reply(msg)
    
    # Verify: answer delivered
    replies = feishu_gateway._sent_replies
    assert len(replies) == 1
    assert "市场" in replies[0]["content"]
    
    # Verify: memory captured
    history = memory_manager.get_conversation_history("c_test", limit=1)
    assert len(history) == 1
    assert history[0]["user_message"] == "分析今天的市场情况"
```

### L5-2: Full product flow: deep research → report delivery

**File**: `tests/test_business_flow_deep_research.py`

```
1. User requests deep research task
2. System creates task, routes to `deep_research` pipeline
3. LLM generates internal draft → external draft → redact gate
4. Report delivery: Google Docs creation + email (via outbox)
5. Assertions:
    - Three drafts exist (internal, external, redacted)
    - Outbox effects are idempotent (re-run doesn't duplicate)
    - Delivery artifacts reference stable delivery_id
```

### L5-3: Full product flow: OpenClaw plugin → async answer

**File**: `tests/test_business_flow_openclaw.py`

```
1. OpenClaw plugin sends POST /v2/advisor/ask
2. System returns {job_id, status: "pending"}
3. Plugin polls GET /v1/jobs/{job_id}/wait
4. System completes → plugin fetches GET /v1/jobs/{job_id}/answer
5. Assertions:
    - Cross-version (/v2 submit + /v1 wait) works
    - Answer is complete and unfragmented
    - Task lifecycle closed
```

### L5-4: Multi-turn conversation with memory continuity

**File**: `tests/test_business_flow_multi_turn.py`

```
1. Turn 1: User asks "什么是 PE ratio"
2. System answers, captures to working memory
3. Turn 2: User asks "那 PB ratio 呢" (requires context from turn 1)
4. System retrieves conversation history, includes in LLM prompt
5. Answer references previous turn context
6. After 60 turns: working memory capacity enforcement engaged
7. Assertions:
    - Turn 2 prompt includes turn 1 context
    - Working memory count ≤ WORKING_CAPACITY
    - Oldest turns evicted correctly
```

### L5-5: Planning lane: full lifecycle

**File**: `tests/test_business_flow_planning_lane.py`

```
1. Create planning task with project context
2. System executes planning pipeline (evidence → draft → review → gate)
3. Human gate: simulate approval/rejection
4. Approval → artifact delivery
5. Rejection → revision loop
6. Assertions:
    - Each checkpoint logged
    - Gate decision recorded
    - Artifact has stable delivery_id
```

---

## L6: Chaos / Resilience / Recovery

### L6-1: Process restart recovery (E3-T4/T5, E10-T5)

**File**: `tests/test_restart_recovery.py`

Scenarios:

1. Create N in-progress advise tasks
2. Simulate process crash (kill worker)
3. Restart process
4. Assertions:
    - All durable state (advisor_runs, steps, events) intact
    - In-memory state (traces, consultations, rate limits) lost but system functional
    - Orphaned runs are detected and reconciled
    - No duplicate task creation on restart

```python
def test_restart_preserves_advisor_runs(db_path, advisor_api):
    """Advisor runs in SQLite survive process restart."""
    # Create a run
    run_id = advisor_api.create_run(task_id="t1", config={})
    advisor_api.record_step(run_id, step_id="s1", status="EXECUTING")
    
    # Simulate restart: close all connections, re-init
    advisor_api = None
    gc.collect()
    advisor_api2 = AdvisorAPI(db_path=db_path)
    
    # Run still exists
    run = advisor_api2.get_run(run_id)
    assert run is not None
    assert run["status"] != "COMPLETED"  # Not lost
```

### L6-2: DB corruption recovery

**File**: `tests/test_db_corruption_recovery.py`

Scenarios:

1. Corrupt `state/jobdb.sqlite3` → system detects and reports, doesn't silently serve stale data
2. Corrupt `~/.openmind/memory.db` → memory operations degrade, don't crash the process
3. Write to read-only DB → system reports error, doesn't hang

### L6-3: Network partition simulation

**File**: `tests/test_network_partition.py`

Scenarios:

1. LLM API unreachable → advisor returns error, task marked FAILED
2. Feishu API unreachable → reply queued, not lost
3. KB retrieval timeout → advisor continues without context (degraded)
4. Google Docs API unreachable → outbox retries, report not lost

---

## L7: Production Shadowing / Canary

### L7-1: Shadow mode validation (E11-T3)

**File**: `ops/shadow_test.py`

Scenarios:

1. Enable shadow mode: new entry receives requests but old entry still serves answers
2. Compare shadow vs production responses for N requests
3. Measure latency delta, error rate delta, answer quality delta

### L7-2: Canary cutover validation (E11-T3)

**File**: `ops/canary_test.py`

Scenarios:

1. Route 10% of traffic to new entry, 90% to old
2. Monitor error rate for new entry
3. If error rate > threshold → automatic rollback

---

## Test Fixture Infrastructure (New)

### F1: `MockLLMConnector`

Controllable LLM responses for deterministic testing.

```python
class MockLLMConnector:
    def __init__(self):
        self.responses = []
        self.call_log = []
    
    def set_response(self, text: str, delay: float = 0):
        self.responses.append({"text": text, "delay": delay})
    
    async def generate(self, prompt: str, **kwargs) -> str:
        self.call_log.append({"prompt": prompt, **kwargs})
        resp = self.responses.pop(0) if self.responses else {"text": "mock default"}
        if resp["delay"]:
            await asyncio.sleep(resp["delay"])
        return resp["text"]
```

### F2: `InMemoryAdvisorClient`

FastAPI TestClient pre-wired with mock LLM and in-memory DB.

```python
@pytest.fixture
def advisor_client(tmp_path):
    db_path = str(tmp_path / "test.db")
    mock_llm = MockLLMConnector()
    app = create_test_app(db_path=db_path, llm=mock_llm)
    return TestClient(app), mock_llm, db_path
```

### F3: `FeishuGatewaySimulator`

Fake Feishu WS connection that captures outbound replies.

```python
@pytest.fixture
def feishu_sim():
    class FakeWS:
        sent = []
        async def send(self, msg): self.sent.append(msg)
    
    gateway = FeishuWSGateway(ws=FakeWS(), advisor_url="http://test")
    return gateway, FakeWS
```

### F4: `MemoryManagerFixture`

In-memory MemoryManager for isolated tests.

```python
@pytest.fixture
def mm():
    return MemoryManager(db_path=":memory:")
```

---

## Epic-to-Test Matrix

| Epic | L1 | L2 | L3 | L4 | L5 | L6 | L7 |
|------|----|----|----|----|----|----|-----|
| E0 Release Safety | L1-1, L1-2 | — | — | — | — | L6-1 | — |
| E1 Entry Convergence | — | — | L3-1, L3-2 | — | — | — | — |
| E2 Identity/Auth | — | L2-1, L2-2 | — | L4-1 | — | — | — |
| E3 Lifecycle | L1-4, L1-5, L1-6 | — | — | L4-2 | L5-1 | L6-1 | — |
| E4 Feishu/OpenClaw | — | — | — | L4-3 | L5-1, L5-3 | L6-3 | — |
| E5 Knowledge Authority | — | — | — | — | — | — | — |
| E6 Promotion Pipelines | — | — | — | — | — | — | — |
| E7 Repo/Memory | L1-3 | — | — | L4-4 | L5-4 | — | — |
| E8 Delivery Lanes | — | — | — | — | L5-5 | — | — |
| E9 Health/Observability | L1-1 | — | — | — | — | — | — |
| E10 CI/Release | — | — | L3-1, L3-2 | — | — | L6-1, L6-2 | — |
| E11 Migration/Canary | — | — | — | — | — | — | L7-1, L7-2 |
| E12 Docs/Governance | — | — | — | — | — | — | — |

---

## Execution Order

### Phase 1: Foundation (Week 1)

1. Build test fixture infrastructure (F1-F4)
2. L1-1: Health endpoint tests
3. L1-2: Fail-closed startup tests
4. L2-1: cc-control auth tests
5. Run existing 325 tests to establish baseline pass rate

### Phase 2: Hardening (Week 2)

1. L1-3: Memory manager comprehensive tests
2. L1-4/5/6: Durable store tests
3. L2-2: Unified auth tests
4. L2-3: Redact boundary tests
5. L3-1/2: Contract compliance tests

### Phase 3: Integration (Week 3)

1. L4-1: Identity resolution integration
2. L4-2: Lifecycle integration
3. L4-3: Feishu task integration
4. L4-4: Knowledge hot path integration

### Phase 4: Business Simulation (Week 4)

1. L5-1: Feishu → answer flow
2. L5-2: Deep research → report delivery
3. L5-3: OpenClaw async flow
4. L5-4: Multi-turn conversation
5. L5-5: Planning lane

### Phase 5: Resilience (Week 5)

1. L6-1: Process restart recovery
2. L6-2: DB corruption recovery
3. L6-3: Network partition
4. L7-1/2: Shadow/canary (requires staging environment)

---

## Test Execution Commands

```bash
# Phase 1: Foundation
pytest tests/test_health_endpoints.py tests/test_startup_fail_closed.py tests/test_cc_control_proxy_bypass.py -v

# Phase 2: Hardening
pytest tests/test_memory_manager_comprehensive.py tests/test_trace_store_durable.py tests/test_consult_store_durable.py tests/test_rate_limit_durable.py tests/test_redact_gate_boundary.py -v

# Phase 3: Integration
pytest tests/test_identity_resolution_integration.py tests/test_lifecycle_integration.py tests/test_feishu_task_integration.py tests/test_knowledge_hot_path_integration.py -v

# Phase 4: Business simulation
pytest tests/test_business_flow_advise.py tests/test_business_flow_deep_research.py tests/test_business_flow_openclaw.py tests/test_business_flow_multi_turn.py tests/test_business_flow_planning_lane.py -v

# Phase 5: Resilience
pytest tests/test_restart_recovery.py tests/test_db_corruption_recovery.py tests/test_network_partition.py -v

# Full regression (all layers)
pytest tests/ -v --tb=short
```

---

## Definition of Test-Complete

All conditions must be true:

- [ ] All L1-L3 tests pass (unit + security + contract)
- [ ] All L4 integration tests pass
- [ ] All L5 business flow simulations pass end-to-end
- [ ] L6 resilience: restart recovery proven, DB corruption handled
- [ ] Existing 325 tests still pass (no regression)
- [ ] Coverage for each P0 epic has at least one L5 simulation
- [ ] No test passes by accident (each test must fail when the target behavior is broken)
