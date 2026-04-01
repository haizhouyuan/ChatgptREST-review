# ADR-003: Identity Contract

**Status**: Draft v2
**Date**: 2026-03-08 (revised after Codex R3/R4 review)
**Depends on**: ADR-001 (State Model)

## Context

v1 proposed generating default session_id from client_ip + hour bucket.
Review identified this as dangerous: most traffic comes from localhost,
causing unrelated calls to merge into one session.

## Decision

### Identity Dimensions

| Dimension | Semantic | Enforcement |
|-----------|---------|-------------|
| `account_id` | User identity (individual/org) | **Reserved** — not enforced in single-user mode |
| `session_id` | Conversation thread | **Enforced** — see fallback rules below |
| `agent_id` | AI persona / execution frontend | **Optional filter** — empty = cross-agent recall (single-user mode only) |
| `thread_id` | Sub-task tracking | **Optional** — empty collapses into session_id |

### session_id Fallback (CHANGED from v1)

When a caller provides empty or missing `session_id`:

**Option A (strict, preferred)**: Fail-closed. Return HTTP 400 / raise ValueError.
```python
if not session_id.strip():
    raise ValueError("session_id is required for cognitive API calls")
```

**Option B (lenient)**: Generate ephemeral UUID, mark as non-persistent.
```python
if not session_id.strip():
    session_id = f"ephemeral-{uuid.uuid4().hex[:16]}"
    # Ephemeral sessions: working memory only, no episodic/semantic recall
```

> **Decision**: Use **Option A** for external HTTP callers. Use **Option B**
> for in-process callers during testing or migration. The option is
> configurable via `OPENMIND_SESSION_FALLBACK=strict|ephemeral`.

### agent_id Cross-Recall Semantics

- **Single-user mode** (current): Empty agent_id = show records from all agents.
  This is intentional — you are the same person across OpenClaw, Antigravity, Codex.
- **Multi-user mode** (future): Empty agent_id behavior must be re-evaluated.
  This decision is scoped to single-user deployment only.

> **Note**: This default MUST be documented as single-user-only behavior.
> It is NOT a permanent architectural principle.

### Isolation Matrix

| Query Type | Required Dimensions | Optional Dimensions |
|-----------|-------------------|-------------------|
| Working memory recall | session_id | — |
| Episodic memory recall | session_id | agent_id, category |
| Semantic memory recall | — | agent_id, domain |
| KB search | — | — (no identity filtering) |
| EvoMap atom retrieval | — | — (no identity filtering) |
| Telemetry ingestion | session_id | agent_id, thread_id |

## Consequences

- No anonymous full-memory dump is possible.
- Cross-agent recall is explicit feature of single-user mode.
- Multi-user migration has clear activation point (enforce account_id).
- Ephemeral sessions don't pollute persistent recall.
