# Phase 20 Pack: OpenClaw Dynamic Replay Gate v1

## Goal

Prove that the shipped OpenClaw `openmind-advisor` plugin can execute dynamically against the current public ChatgptREST surface, rather than relying on source inspection or manually reconstructed payloads.

## Scope

This pack is intentionally scoped to three checks:

1. Dynamic tool registration
   - Load `openclaw_extensions/openmind-advisor/index.ts` through a real `tsx` runtime
   - Confirm that it registers `openmind_advisor_ask`
2. Dynamic contract capture
   - Replay the tool against a local fake HTTP endpoint
   - Verify the real emitted request path, headers, and `task_intake`
3. Live public replay
   - Replay the tool against live `POST /v3/agent/turn`
   - Verify a planning sample still lands on `needs_followup + route=clarify`

## Non-goals

This pack does not prove:

- full-stack external-provider delivery
- OpenClaw full session replay
- heavy execution lane readiness
- auth-hardening completeness

## Required runtime assumptions

- `npx --yes tsx` is available locally
- `@sinclair/typebox` runtime is available from the installed OpenClaw tree
- `OPENMIND_API_KEY` is available via environment or `~/.config/chatgptrest/chatgptrest.env`
- live API allowlist explicitly includes `openclaw-advisor`

## Artifact target

- `docs/dev_log/artifacts/phase20_openclaw_dynamic_replay_gate_20260322/report_v1.json`
- `docs/dev_log/artifacts/phase20_openclaw_dynamic_replay_gate_20260322/report_v1.md`
