# 1A Role Pack Core — Walkthrough

**Commit**: `21cefb6` on `master`  
**Date**: 2026-03-10

## What Was Built

Role-based memory isolation for the OpenMind cognitive substrate. Business roles (devops, research) can now tag and scope memory independently from component identity (advisor, openclaw).

### Key Design Decision

`source.agent` = **component identity** (who wrote it)  
`source.role` = **business role** (why it was written)

These are independent dimensions. A record can have `agent=advisor, role=devops` — meaning the advisor component created it while serving the devops role.

## Changes Made

### Core: [memory_manager.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/kernel/memory_manager.py)
- `MemorySource` dataclass: added `role` field (default `""`)
- `stage()`: auto-injects `source.role` from contextvars if not already set
- `stage()` dedup branch: **now updates `source`** on merge (was only updating value/confidence/updated_at — role would have been silently dropped)
- `get_episodic()` / `get_semantic()`: new `role_id` query parameter

### New: [role_context.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/kernel/role_context.py)
- `with_role(RoleSpec)` context manager for contextvars binding
- `get_current_role_name()` reads active role's `memory_namespace`

### New: [role_loader.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/kernel/role_loader.py)
- YAML config loader with caching + env override (`$CHATGPTREST_ROLES_PATH`)

### New: [agent_roles.yaml](file:///vol1/1000/projects/ChatgptREST/config/agent_roles.yaml)
- `devops` and `research` role definitions with `memory_namespace` and `kb_scope_tags`

### Extended: [team_types.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/kernel/team_types.py)
- `RoleSpec`: +`memory_namespace` +`kb_scope_tags` fields

### Integrated: [context_service.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
- `_LocalOnlyContextAssembler.build()`: passes `role_id` to all memory queries
- Auto-resolves from contextvars if not explicitly provided

## Testing

**21 tests, all passing** ([test_role_pack.py](file:///vol1/1000/projects/ChatgptREST/tests/test_role_pack.py)):

| Scenario | Tests | Status |
|----------|-------|--------|
| Cold start empty | 2 | ✅ |
| Role isolation (cross-role invisible) | 3 | ✅ |
| Component identity preserved | 2 | ✅ |
| Dedup merge preserves role | 2 | ✅ |
| No-role backward compat | 2 | ✅ |
| Contextvars auto-inject | 3 | ✅ |
| RoleSpec + loader | 4 | ✅ |
| MemorySource dataclass | 3 | ✅ |

**Full regression**: 0 failures across entire suite.

## Verification

- **GitNexus `detect_changes`**: 12 affected processes, all expected downstream consumers of the modified symbols
- **Risk**: Semantically low — all changes are additive with backward-compatible defaults

## What's Next

| Phase | Description | Status |
|-------|-------------|--------|
| **1A** | Core role pack (this PR) | ✅ Done |
| **1B** | Memory identity governance (audit gaps, fix high-frequency missing paths) | Pending |
| **1C** | KB governance (tag vocabulary, backfill scripts, `off→hint` transition) | Pending |

> [!NOTE]
> KB filtering remains `off` by default. `ContextResolver` has the `role_id` plumbing ready, but no hard filtering is applied until KB tags are governed (Phase 1C).
