# Agent Telemetry → EvoMap Integration: Best Practices & Current State Survey

**Date:** 2026-03-10  
**Author:** Antigravity  
**Purpose:** Research best practices, survey existing agent telemetry, and propose architecture for unifying multi-agent observability with EvoMap knowledge evolution.

---

## 1. Industry Best Practices (2025-2026)

### 1.1 Agent Observability Stack

The emerging standard has three layers:

| Layer | What it captures | Tools |
|---|---|---|
| **Tracing** | Every LLM call, tool use, decision point as spans in a trace | OpenTelemetry GenAI SIG, Langfuse, LangSmith, Arize Phoenix |
| **Evaluation** | Quality scores + user feedback on agent outputs | Langfuse Scores, Maxim AI evals, human-in-the-loop |
| **Analytics** | Cost, latency, success rate aggregated over time | Portkey, Helicone, SourceTrail |

**Key insight from OpenTelemetry GenAI SIG:** Standardized semantic conventions for LLM agents are being defined. Key attributes include: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.response.finish_reasons`. These are the primitives any telemetry system should capture.

### 1.2 AgentRR: Record & Replay Paradigm

From [arxiv, 2025]:
1. **Record** agent interactions and internal decisions during task execution
2. **Summarize** the trace into structured "experience" that captures workflow + constraints
3. **Replay** experiences in future similar tasks to guide behavior

Key design choices:
- **Multi-level abstraction**: raw logs → summarized steps → generalized patterns
- **Check functions**: verify completeness and safety during replay
- **Balance specificity vs generality**: too specific = brittle, too general = useless

### 1.3 Reflection & Self-Improvement Patterns

LangGraph's reflection pattern:
```
generate → execute → debug → reflect → generate (improved)
```

The "reflect" step produces **meta-knowledge**: not what the agent did, but **why it succeeded or failed**. This meta-knowledge is the highest-value input to EvoMap.

### 1.4 Knowledge Distillation from Agent Traces

From multi-teacher distillation research:
- Use large models (GPT Pro, Gemini DT) as "teachers" that generate high-quality reasoning
- Distill their traces into smaller, reusable knowledge atoms
- **Critical**: distillation is NOT extraction — it requires understanding and compression

---

## 2. Current State Survey: Each Agent's Telemetry

### 2.1 ChatgptREST Job Queue (Gemini + ChatGPT + Qwen)

**Data location:** `state/jobdb.sqlite3` + `artifacts/jobs/<job_id>/`

| Metric | Value |
|---|---|
| Total jobs | 6,823 |
| Date range | 2025-12-26 to 2026-03-10 |
| ChatGPT asks | 2,520 (79% success, 7% error) |
| Gemini asks | 951 (73% success, 13% error) |
| Qwen asks | 34 (0% completed, 68% error) |
| Repair checks | 2,684 |
| Autofix jobs | 426 (99% success) |
| Image generation | 120 (78% success) |

**What's already captured per job:**
- `question` (full prompt text)
- `answer` (full response, artifact files)
- `status`, `created_at`, `completed_at` (timing)
- `conversation_url` (session continuity)
- `events.jsonl` (state transitions with timestamps)
- `client_json` (who submitted: agent name, project)
- `params` (model, preset, parent_job_id for follow-ups)

**What's NOT captured:**
- No "was this answer useful?" feedback loop
- No link to downstream action (did the agent use this answer?)
- No quality scoring of answers
- `chat_followup` extractor exists but only runs on closeout, not online

**EvoMap integration:** Partial. `chat_followup.py` extracts atoms from completed jobs, but with heuristic scoring only (no LLM review). The `client_issues.py` issue-close sink writes resolution atoms (fixed in today's commit `4193e49`).

### 2.2 Codex (OpenAI)

**Data locations:**
- `~/.codex/history.jsonl` — 5.7MB, user prompts only (no agent responses)
- `~/.codex/sessions/2026/{MM}/{DD}/rollout-*.jsonl` — full session traces
- `~/.codex/state_5.sqlite` — 248MB state database
- `~/.codex/agents/` — agent configs

**Session count:** 46 sessions in 2026 (20 in Jan, 26 in Feb, 6+ in Mar)

**Session format:** NDJSON with typed events:
```json
{"timestamp": "2026-03-05T16:25:00.523Z", "type": "session_meta", "payload": {"id": "...", "cwd": "/home/yuanhaizhou", "originator": "code..."}}
```

**What's captured:**
- Full conversation history (user prompts + agent responses)
- Tool calls and their results
- File modifications (diffs)
- Session metadata (cwd, start time, duration)
- Git commits made during session

**What's NOT captured:**
- No structured "what did I learn?" output
- No quality scoring of decisions
- No cross-session knowledge persistence (each session starts fresh)
- `state_5.sqlite` structure unknown — may contain useful aggregations

**EvoMap integration:** None. Codex sessions are completely isolated from EvoMap.

### 2.3 Antigravity (Google DeepMind)

**Data location:** `~/.gemini/antigravity/brain/<conversation-id>/`

**Conversation count:** 92 conversations

**Artifact structure per conversation:**
```
<conversation-id>/
  task.md                          # Task checklist (living document)
  task.md.resolved                 # Resolved versions (multiple)
  implementation_plan.md           # Design document
  walkthrough.md                   # Post-completion summary
  *.metadata.json                  # Artifact metadata
  .system_generated/
    steps/                         # Step-by-step execution logs
    logs/overview.txt              # Conversation summary
```

**What's captured:**
- Full task planning (implementation_plan.md)
- Task progress tracking (task.md with checkboxes)
- Post-completion walkthrough (walkthrough.md)
- System-generated step logs
- Conversation summaries (for cross-conversation context)

**What's NOT captured:**
- No machine-readable event stream (artifacts are markdown, not structured data)
- No explicit "lesson learned" extraction
- No cross-conversation knowledge persistence (summaries are brief)

**EvoMap integration:** None currently — but Antigravity artifacts are the richest source of structured agent telemetry (task plans, execution traces, walkthroughs).

### 2.4 Claude Code (Anthropic)

**Data locations:**
- `~/.claude/history.jsonl` — 208 entries, user prompts only
- `~/.claude/projects/` — 10 project-specific directories
- `~/.claude.json` — configuration with project metadata

**History format:**
```json
{"display": "继续", "pastedContents": {}, "timestamp": 1760321256664, "project": "/home/yuanhaizhou/projects/storyapp"}
```

**What's captured:**
- User prompts with timestamps and project context
- Project-level settings and memory (CLAUDE.md equivalent)
- Session-level tool call logs (in `~/.claudecode/` directory)

**What's NOT captured:**
- Agent responses not in `history.jsonl` (only user inputs)
- No structured decision/outcome tracking
- No cross-session learning

**EvoMap integration:** None.

### 2.5 OpenClaw Guardian / Orch

**Data locations:**
- `artifacts/monitor/ui_canary/` — UI health checks
- `artifacts/monitor/guardian/` — guardian reports
- `artifacts/monitor/orch/` — orchestration reports
- Issue Ledger (`state/jobdb.sqlite3` `client_issues` table)

**What's captured:**
- Health check results (pass/fail, error details)
- Incident lifecycle (report → investigate → mitigate → close)
- Qualifying usage evidence per issue
- Verification records

**EvoMap integration:** Partial — issue close → evomap atom sink exists (fixed today).

---

## 3. Analysis: Where the Gaps Are

### 3.1 Gap Matrix

| Capability | ChatgptREST | Codex | Antigravity | Claude Code | OpenClaw |
|---|---|---|---|---|---|
| Raw event capture | ✅ JSONL/DB | ✅ JSONL | ✅ Markdown | ⚠️ Prompts only | ✅ JSONL |
| Structured schema | ✅ SQL schema | ⚠️ Proprietary | ❌ Unstructured | ❌ Minimal | ✅ SQL schema |
| Quality scoring | ⚠️ Heuristic only | ❌ | ❌ | ❌ | ✅ (issue severity) |
| User feedback loop | ❌ | ❌ | ❌ | ❌ | ⚠️ (manual) |
| Cross-session memory | ❌ | ❌ | ⚠️ (summaries) | ⚠️ (CLAUDE.md) | ❌ |
| EvoMap integration | ⚠️ Partial | ❌ | ❌ | ❌ | ⚠️ Partial |
| AI-driven extraction | ❌ | ❌ | ❌ | ❌ | ❌ |

### 3.2 The Core Problem

**Every agent generates valuable execution traces, but none of them feed back into a unified knowledge system.** The knowledge dies with the session.

Specifically:
1. **No unified event schema** — each agent has a different data format
2. **No AI-driven knowledge extraction** — only heuristic scoring exists
3. **No feedback loop** — agent outputs aren't evaluated for quality
4. **No cross-agent learning** — Codex's mistake can't prevent Antigravity's repeat

---

## 4. Recommended Architecture

### 4.1 Three-Layer Design

```
┌─────────────────────────────────────────────────────────┐
│  Layer 0: RAW TELEMETRY (per agent, existing formats)   │
│  Codex JSONL │ AG artifacts │ CC history │ CRest jobs   │
└──────────┬──────────┬──────────┬──────────┬─────────────┘
           │          │          │          │
           ▼          ▼          ▼          ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 1: UNIFIED EVENT BUS                             │
│  Agent → Adapter → AgentEvent schema → event_store.db   │
│  (one adapter per agent, runs at closeout)              │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 2: EXPERIENCE EXTRACTOR (LLM-driven)             │
│  Batch events → AI review → lesson/correction/pattern   │
│  atoms → EvoMap (source=agent_experience)               │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Layer 1: Unified Event Schema

```python
@dataclass
class AgentEvent:
    agent: str          # "codex" | "antigravity" | "cc" | "gemini" | "openclaw"
    session_id: str     # conversation/session ID
    timestamp: str      # ISO8601
    event_type: str     # task_start | task_complete | code_change | claim | correction | error | decision
    target: dict        # {files: [], symbols: [], component: str}
    outcome: dict       # {status: str, user_feedback: str|None, quality_signal: float|None}
    content: dict       # {summary: str, detail: str, artifacts: [str]}
    provenance: dict    # {conversation_id, job_id, commit_hash}
```

### 4.3 Layer 1: Adapters (Per Agent)

| Agent | Adapter approach | Trigger |
|---|---|---|
| **Codex** | Parse `sessions/*/rollout-*.jsonl` → extract tool calls, file changes, decisions | `agent_task_closeout.sh` |
| **Antigravity** | Parse `brain/<id>/task.md` + `walkthrough.md` → extract completed items, outcomes | `agent_task_closeout.sh` |
| **Claude Code** | Parse `~/.claude/history.jsonl` + session logs → extract prompts, outcomes | `agent_task_closeout.sh` |
| **ChatgptREST** | Query `jobdb` for completed jobs → extract Q&A pairs, model, timing, success | Already exists (extend `chat_followup.py`) |
| **OpenClaw** | Parse `artifacts/monitor/` JSONL + Issue Ledger → extract incidents, resolutions | Guardian cycle |

### 4.4 Layer 2: Experience Extractor

The Experience Extractor reads batched events and produces knowledge atoms via LLM:

**Input:** 10-50 events from a single agent session

**LLM Prompt Template:**
```
You are reviewing an AI agent's session. Extract reusable knowledge:

Session events:
{events}

For each piece of reusable knowledge, output:
- type: correction | lesson | procedure | pattern | decision
- question: what question does this answer?
- answer: the knowledge (actionable, self-contained)
- confidence: 0.0-1.0
- shelf_life: evergreen | months | weeks | days
- reasoning: why this is worth keeping
```

**Output:** EvoMap atoms with `source=agent_experience`, `agent={agent_name}`, `session_id={session_id}`

### 4.5 Feedback Loop (Self-Purification)

```
EvoMap atom retrieved → used in advisor response → user accepts/rejects
    ↓
usage_evidence record (job_id, outcome)
    ↓
atom quality_auto adjusted (+ for accept, - for reject)
    ↓
low-quality atoms auto-demoted after N rejections
```

---

## 5. Implementation Priority

| Priority | What | Effort | Impact |
|---|---|---|---|
| **P0** | Add `agent_events.jsonl` emit to `agent_task_closeout.sh` | 1 day | Foundation — all future work depends on this |
| **P1** | Codex adapter (parse rollout JSONL → agent events) | 1 day | Access richest session data |
| **P1** | Antigravity adapter (parse artifacts → agent events) | 1 day | Access design reasoning + outcomes |
| **P2** | Experience Extractor prototype (LLM batch → atoms) | 2-3 days | First AI-driven knowledge creation |
| **P2** | Retrieval feedback loop (usage_evidence → quality adjustment) | 1 day | Self-purification start |
| **P3** | Claude Code adapter | 0.5 day | Extend coverage |
| **P3** | Cross-agent conflict detection | 2 days | "Codex said X, AG said Y" resolution |
| **P4** | Real-time event streaming (vs batch) | 3+ days | Low priority — batch is fine for now |

---

## 6. Trial: What Experience Extraction Looks Like

Taking today's session (this conversation) as an example, here are the kind of lesson atoms that an Experience Extractor would produce:

### Atom 1: Correction
```
Q: How many _review_pack documents are in the main EvoMap DB?
A: 25 documents match '_review_pack' in titles. Codex incorrectly reported 1,101 (44× error).
   Root cause: Codex likely queried a different DB snapshot or used wrong SQL.
   Lesson: Always verify agent-reported counts with direct DB queries.
type: correction
confidence: 1.0
shelf_life: months
agent: antigravity (correcting codex)
```

### Atom 2: Procedure
```
Q: How to seal a dual-DB path leak in KnowledgeDB?
A: Change KnowledgeDB.__init__ to use resolve_evomap_knowledge_runtime_db_path()
   instead of raw EVOMAP_DB_PATH env. This function has a built-in legacy guard
   that rejects ~/.openmind/ paths. Same fix for RelationManager.__init__.
   Verified: env override rejected, bare calls resolve to canonical.
type: procedure
confidence: 1.0
shelf_life: evergreen
agent: antigravity
commit: 4193e49
```

### Atom 3: Design Decision
```
Q: Should retrieval serve staged atoms?
A: No. Current retrieval includes staged atoms (95K, all unaudited) alongside
   active atoms (0). This violates the principle that only curated knowledge
   should be in the serving path. Fix: change retrieval default to active-only,
   but FIRST run P4 batch promotion to ensure active != empty.
type: decision
confidence: 0.9
shelf_life: months
agent: antigravity + codex (consensus)
```

### Atom 4: Pattern
```
Q: What's the effective multi-agent review pattern for ChatgptREST?
A: Codex proposes plan → Antigravity independently verifies against actual code/DB 
   → User makes final judgment. Key: verification must include direct code reads
   and DB queries, not just reviewing Codex's claims at face value.
   Codex's strategic direction is usually correct; factual details often have errors.
type: pattern
confidence: 0.85
shelf_life: evergreen
agent: meta (cross-agent observation)
```

These four atoms capture more actionable knowledge from this single session than the entire heuristic extractor produces from 100 chat_followup jobs.

---

## 7. Conclusion

**Current state:** Rich telemetry data exists across 5 agent types but is completely siloed. No unified schema, no AI-driven extraction, no feedback loop.

**Key best practice from industry:** The AgentRR (Record & Replay) paradigm — record interactions, summarize into structured experience, replay in future tasks — is exactly what EvoMap should become.

**Recommended next step:** Don't build the full architecture. Start with P0 (unified event emit at closeout) + one trial run of the Experience Extractor on 3-5 recent sessions. Validate that the extracted atoms are genuinely useful before building adapters.
