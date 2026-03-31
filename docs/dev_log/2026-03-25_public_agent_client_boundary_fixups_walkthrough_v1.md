# 2026-03-25 Public Agent Client Boundary Fixups Walkthrough v1

## Why this was necessary

The client had already identified the right failure pattern: this was not one isolated bug, but a cluster of ambiguous boundaries that kept causing the same drift:

- public repo review was being overfit to a review-repo workflow
- Gemini web review was being conflated with Gemini CLI
- agent-mode timeout knobs looked like legacy jobs knobs
- provider choice was not auditable enough

## Implementation notes

1. Kept the blast radius small on the agent route.
   - `gitnexus_impact` showed `_run_turn`, `_build_agent_response`, and the wrapper entrypoints were low-risk.
   - `_finalize_public_agent_surface` and `_session_response` remained high-risk, so the change was pushed into provenance helpers and `_run_turn` instead of rewriting the global response finalizer.

2. Fixed the hidden context drop first.
   - The main root cause was that `task_intake.context` was not being merged back into the live `context` inside `agent_turn`.
   - Without that merge, wrapper-carried fields looked present from the client side but were effectively ignored by the server.

3. Added service-side provider handling instead of relying on docs alone.
   - Gemini provider requests now route to a direct `gemini_web.ask` path.
   - Imported-code misuse now fails fast with a structured error instead of degrading into an unrelated lane.

4. Tightened wrapper semantics.
   - Agent mode now rejects legacy-only wait/export flags.
   - Agent timeouts keep enough recovery metadata for clients to continue with the same `session_id`.

## Files touched

- `chatgptrest/api/routes_agent_v3.py`
- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
- `tests/test_routes_agent_v3.py`
- `tests/test_skill_chatgptrest_call.py`
- `docs/contract_v1.md`
- `docs/runbook.md`
- `skills-src/chatgptrest-call/SKILL.md`

## Follow-on expectation

After this change, a client asking for Gemini review should either:

- actually get a Gemini web lane, with provider selection visible in response provenance, or
- fail fast with a structured conflict that tells the client which boundary it violated.
