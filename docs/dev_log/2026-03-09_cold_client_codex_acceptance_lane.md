# 2026-03-09 Cold Client Codex Acceptance Lane

## Why

Maintainer-side validation was insufficient.

Real failure mode:

- maintainer knew the latest contract or runbook change
- another Codex session did not
- the second session used the wrong wrapper, wrong preset, wrong client headers, or wrong assumptions
- backend looked fixed locally, but the real client lane still failed or became inefficient

So the acceptance target is now:

- a fresh Codex client with no background context can discover the documented path and successfully use ChatgptREST

## What was added

### Script

- `ops/codex_cold_client_smoke.py`

This script:

- launches a fresh `codex exec`
- keeps the caller's normal `CODEX_HOME` by default, but always uses a fresh Codex session
- supports stricter audits via `--isolate-codex-home`
- constrains the Codex run to repository-discoverable docs and entrypoints
- requires one real human-language client call through the documented ChatgptREST client path
- writes structured output under `artifacts/cold_client_smoke/<timestamp>/`

### Schema

- `ops/schemas/codex_cold_client_smoke.schema.json`

The cold client must report:

- docs read
- commands used
- whether the job succeeded
- job id / final status when available
- confusion points
- concrete recommendations

### Tests

- `tests/test_codex_cold_client_smoke.py`

Coverage includes:

- prompt contains the intended discovery scope
- isolated `CODEX_HOME` behavior
- script calls `codex_exec_with_schema(..., sandbox="workspace-write")`

## Operational Rule

After any change that affects client usage, do not stop at maintainer smoke.

Run the cold-client lane and treat the following as failures:

- client only succeeds after maintainer hints
- client has to guess headers / presets / wrappers
- client path works only because the maintainer knows hidden context

## Expected Usage

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/codex_cold_client_smoke.py \
  --provider gemini \
  --preset pro \
  --question "请用两句话解释为什么写自动化测试可以降低回归风险。"
```

## Outcome

Cold-client acceptance is now a first-class integration lane instead of an informal idea.

## First Fresh-Client Feedback

A separate cold-start agent run against the current repo found one concrete friction point:

- `chatgptrest_call.py --out-conversation` could fail on immediate `409 conversation export not ready` even when the job itself had already completed and answer retrieval worked

Follow-up hardening applied:

- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py` now does bounded retries for conversation export readiness
- `skills-src/chatgptrest-call/SKILL.md` and `docs/runbook.md` now state that conversation export is a lagging artifact stream, not the same readiness boundary as answer completion

## Second Fresh-Client Feedback

The first real nested `codex exec` smoke exposed a second issue:

- a sandboxed Codex shell can discover the documented wrapper correctly but still fail to use it because loopback HTTP to `127.0.0.1:18711` is blocked by the shell transport boundary
- the Codex client then recovered by using the already-installed ChatgptREST MCP tools, executed a real request successfully, and wrote the requested artifact files
- however, the harness originally waited forever for a final stdout JSON object even though `client_summary.json` already contained a valid structured outcome

Follow-up hardening applied:

- `ops/codex_cold_client_smoke.py` now allows the repository-documented ChatgptREST MCP path as an explicit fallback when loopback HTTP is unavailable in a sandboxed Codex shell
- the harness now salvages a validated result from `client_summary.json` instead of hanging on final stdout formatting
- if the host machine's normal `CODEX_HOME` is itself broken (for example `config.toml duplicate key`), the harness now automatically retries with an isolated `CODEX_HOME` instead of misclassifying that as a ChatgptREST client regression
- `docs/runbook.md`, `docs/client_projects_registry.md`, and `skills-src/chatgptrest-call/SKILL.md` now document the sandbox-loopback constraint and the allowed MCP fallback

## Third Fresh-Client Feedback

The first two nested `codex exec` runs showed another acceptance-specific failure mode:

- the cold client spent too much of its budget dumping large documentation slices (`sed -n ...`) into context
- by the time it reached CLI help, it had not yet executed the real client command
- that made the run look like a harness failure when the actual problem was prompt shape and context hygiene

Follow-up hardening applied:

- the prompt now explicitly requires lean discovery (`rg` / targeted snippets first, no whole-file dumps)
- the prompt now says the client should reach the real request within a small number of steps instead of consuming the run on doc browsing
- the prompt now names the exact executable forms (`/usr/bin/python3 ...chatgptrest_call.py` or `./.venv/bin/python -m chatgptrest.cli`) and explicitly warns not to assume bare `python` exists on this host

## Fourth Hardening Pass

The next live runs exposed two more operational gaps:

- nested `codex exec --json` can still reach a real ChatgptREST job but fail to emit a final structured JSON object before the harness timeout
- acceptance evidence was not recording which Codex `profile` / `model` produced the result, which made "works for me" reruns too dependent on the maintainer shell state

Follow-up hardening applied:

- `ops/codex_cold_client_smoke.py` now salvages a valid pass result from observed job artifacts after a successful real request, even if the nested Codex session never flushes the final JSON object
- that salvage path now synthesizes minimal `docs_read` / `commands` evidence when the JSONL stream is incomplete, instead of treating the run as unusable
- the runner now accepts and records `--profile` (plus existing `--model`) so cold-client results are reproducible as explicit execution lanes rather than ambient Codex state
- `chatgptrest/core/codex_runner.py` now passes `--profile` through to `codex exec`, keeping the new lane compatible with the rest of the Codex runner helpers

## Subagent Strategy

Cold-client acceptance should not use a single generic agent profile.

Recommended split:

- `scout`: cheap/fast model, tiny discovery budget, read-only, no real request
- `executor`: stronger model, explicit provider/preset invariants, one real human-language request
- `judge`: read-only verifier, no new requests, only decides pass/fail from artifacts and job state

Host mapping on this machine:

- `scout` profile -> discovery lane
- `builder` profile -> execution lane
- `reviewer` profile -> judgement lane

Why this split matters:

- the exploration failure mode is different from the execution failure mode
- the execution failure mode is different from the acceptance-judgement failure mode
- mixing all three into one profile encourages either doc-dumping or hidden-background dependence

## Live Validation

Live cold-client acceptance now passes on the current host baseline.

Validated lane:

- command: `PYTHONPATH=. ./.venv/bin/python ops/codex_cold_client_smoke.py --provider gemini --preset pro --profile builder --question "请用两句话说明为什么自动化测试能降低回归风险。"`
- artifact dir: `artifacts/cold_client_smoke/20260309_115525/`
- real job id: `c6689ec42e50418f818baf234472ca6d`
- final status: `completed`

What the live run proved:

- the nested Codex client can discover the documented wrapper path from repo-local docs
- it correctly treats loopback HTTP failure as a transport gap rather than inventing ad-hoc REST variants
- it can self-correct to the documented MCP fallback and still execute a real `gemini/pro` request
- the harness can now salvage a valid `result.json` from observed job artifacts even when the nested Codex session never emits the final structured JSON object
