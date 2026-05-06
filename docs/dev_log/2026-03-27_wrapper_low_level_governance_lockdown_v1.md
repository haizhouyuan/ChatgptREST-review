# 2026-03-27 Wrapper Low-Level Governance Lockdown v1

## Context

The remaining trust-model gap on ChatgptREST low-level web ask had narrowed to three wrapper-style identities:

- `planning-wrapper`
- `openclaw-wrapper`
- `advisor-automation`

Historically, low-level ask misuse came from more than these callers, but these three still mattered because they were live identities with real or implied `/v1/jobs` access and only registry-mode authentication. That meant the system still depended on policy + prompt guard instead of hard source authentication.

## Decision

Treat wrapper governance as a fail-closed ingress problem, not a documentation problem.

The new target state is:

- `planning-wrapper`: the only approved automation wrapper that still keeps a low-level ask lane
- `planning-wrapper`: must be HMAC-authenticated
- `planning-wrapper`: runtime constrained by concurrency and recent-duplicate suppression
- `openclaw-wrapper`: no external low-level ask lane
- `advisor-automation`: no external low-level ask lane
- `finbot-wrapper`: remains public-agent-only

## Changes

### 1. Registry lockdown

Updated [ops/policies/ask_client_registry.json](/vol1/1000/projects/ChatgptREST/ops/policies/ask_client_registry.json):

- `planning-wrapper`
  - upgraded to `auth_mode=hmac`
  - new secret env: `CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER`
  - new runtime controls:
    - `enabled=true`
    - `max_in_flight_jobs=2`
    - `dedupe_window_seconds=1800`
- `openclaw-wrapper`
  - reduced to `allowed_surfaces=["public_agent_mcp"]`
  - low-level ask disabled
- `advisor-automation`
  - reduced to `allowed_surfaces=["internal_runtime"]`
  - external `/v1/jobs` use disabled

### 2. Hard fail for registry-only automation low-level ask

Updated [chatgptrest/core/ask_guard.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/ask_guard.py):

- `automation_registered` profiles that still declare `low_level_jobs` without `auth_mode=hmac` now fail closed as:
  - `low_level_ask_registry_misconfigured`
  - `reason=automation_low_level_jobs_requires_hmac`

This removes the last supported path where an automation wrapper could keep low-level ask permissions under registry-name-only auth.

### 3. Runtime controls at ingress

Added runtime enforcement in [chatgptrest/core/ask_guard.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/ask_guard.py) and wired it into [chatgptrest/api/routes_jobs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_jobs.py):

- profile kill switch: `enabled=false` => `403 low_level_ask_client_disabled`
- in-flight concurrency limit => `429 low_level_ask_client_concurrency_exceeded`
- recent duplicate suppression => `409 low_level_ask_duplicate_recently_submitted`

The duplicate check fingerprints the final low-level request payload after follow-up inheritance, so it applies to the actual accepted request shape rather than a partial pre-normalized view.

### 4. Wrapper contract sync

Updated external client docs:

- [planning/docs/chatgptREST.md](/vol1/1000/projects/planning/docs/chatgptREST.md)
- [planning/AGENTS.md](/vol1/1000/projects/planning/AGENTS.md)
- [openclaw/docs/chatgptREST.md](/vol1/1000/projects/openclaw/docs/chatgptREST.md)
- [openclaw/AGENTS.md](/vol1/1000/projects/openclaw/AGENTS.md)

The new contract is explicit:

- planning may use low-level ask only through the registered HMAC lane
- openclaw must not use low-level ask for normal model traffic
- advisor aliases must not be reused as external caller identities

## Validation Plan

1. Repo-level tests:
   - low-level HMAC auth
   - planning duplicate suppression
   - planning concurrency limit
   - openclaw low-level denial
   - advisor alias low-level denial
2. Live runtime:
   - configure planning HMAC secret
   - restart API/MCP
   - run expanded live smoke helper

## Expected Outcome

If a wrapper regresses now, it should fail closed at ingress and not produce unmanaged low-level ask load or ambiguous provenance.
