# Phase 20 Walkthrough: OpenClaw Dynamic Replay Gate v1

## Why this phase existed

`Phase 19 v3` had already proven the scoped public launch candidate gate, but one explicit boundary remained: there was still no proof that the actual shipped OpenClaw plugin could execute dynamically against the live public surface.

Source inspection and payload snapshots were no longer enough.

## What I did

1. Read the shipped plugin:
   - [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
2. Confirmed a dynamic execution path was feasible with:
   - `node`
   - `npx --yes tsx`
   - the installed OpenClaw TypeBox runtime
3. Added a scoped gate that:
   - loads the plugin dynamically through `tsx`
   - registers `openmind_advisor_ask`
   - replays the tool against a fake HTTP endpoint and captures the emitted request
   - replays the tool against live `POST /v3/agent/turn`
4. Ran the live replay once and hit a real `403 client_not_allowed`
5. Traced that to the current service env:
   - `~/.config/chatgptrest/chatgptrest.env`
   - `CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST=chatgptrest-mcp,chatgptrestctl`
6. Added `openclaw-advisor` to the live allowlist, restarted `chatgptrest-api.service`, and reran the gate

## Commands run

```bash
./.venv/bin/pytest -q tests/test_openclaw_dynamic_replay_gate.py
python3 -m py_compile \
  chatgptrest/eval/openclaw_dynamic_replay_gate.py \
  ops/run_openclaw_dynamic_replay_gate.py \
  tests/test_openclaw_dynamic_replay_gate.py
PYTHONPATH=. ./.venv/bin/python ops/run_openclaw_dynamic_replay_gate.py
systemctl --user restart chatgptrest-api.service
curl -s http://127.0.0.1:18711/healthz
```

## Evidence

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase20_openclaw_dynamic_replay_gate_20260322/report_v1.json)
- [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase20_openclaw_dynamic_replay_gate_20260322/report_v1.md)

## Final judgment

`Phase 20 = GO`

The important distinction is that this is no longer a static adapter assertion. It is a real dynamic plugin replay proof against the current public surface.
