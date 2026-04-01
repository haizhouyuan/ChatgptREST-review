# Full Stack Linkage Gap Scan Todo v1

Date: 2026-03-12
Repo: ChatgptREST
Branch: `codex/issue156-personal-assistant-design`
Status: in_progress

## Objective

Produce a full-stack scan of broken, partial, or islanded functional linkages across ChatgptREST, OpenClaw integration, Feishu ingress, task closure, advisor/runtime execution, delivery lanes, memory/KB/event surfaces, and ops/self-heal loops.

## Deliverables

- [x] Create versioned todo anchor for the scan
- [ ] Map intake and ingress surfaces
- [ ] Map task, run, job, and issue closure surfaces
- [ ] Map delivery-lane connectivity for planning and finagent
- [ ] Map memory, KB, telemetry, and event-bus connectivity
- [ ] Map ops, incident, repair, and self-heal connectivity
- [ ] Consolidate all broken or islanded chains into one versioned analysis doc
- [ ] Write walkthrough and review trace
- [ ] Push updates to the existing PR

## Scan Rules

- Prefer code-path evidence over narrative assumptions.
- Distinguish:
  - merged clean baseline on `origin/master`
  - local in-flight implementation context
  - live/runtime observations documented in issue and runbook material
- Treat "孤岛" as one of:
  - no upstream/downstream consumer
  - duplicated parallel entry plane
  - partial persistence chain
  - state truth split
  - recovery loop disconnected from business task loop
  - domain lane exists but is not wired to shared task truth

## Expected Output Shape

- One master analysis doc with:
  - system map
  - broken-chain inventory
  - island inventory
  - severity / leverage ranking
  - recommended repair order

## Working Log

- 2026-03-12: started full-stack linkage gap scan on top of issue156 design branch.
