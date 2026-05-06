# Productionization Corrective Wave Walkthrough V1

Date: 2026-04-08

Related plan:

- [Refined Next-Stage Full Execution Plan V5](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v5.md)

Related completion:

- [Productionization Corrective Wave Completion V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_productionization_corrective_wave_completion_v1.md)

## 1. Why this wave was opened

The latest runtime review said the architecture was no longer the main problem.

The remaining blockers were runtime-production blockers:

1. jobs-answer primary path not healthy
2. promotion maintenance timer not installed in live systemd
3. one route-validation suite still red
4. no public MCP `/health`

The wave was therefore executed as a narrow productionization repair, not as another architecture refactor.

## 2. What changed first

The first pass split auth domains and added public MCP health.

That fixed the original `401` class of issue, but live verification immediately exposed a second hidden problem:

- once bearer auth was correct
- the jobs-answer endpoint returned the chunk contract
- `agent_mcp.py` still assumed an older normalized answer shape

That parser defect was then fixed in the same wave.

## 3. What was installed in live runtime

The repo-reviewed planning-review maintenance units were installed into the live user systemd runtime and enabled.

This moved maintenance from:

- “repo contains reviewed units”

to:

- “the live runtime actually has the timer installed and active”

## 4. How live validation was handled

Live validation was intentionally split into two evidence lanes.

### Lane A: completed-session primary-path smoke

This was used to answer the most important production question directly:

> can the live public MCP return `source=job_answer_api` now?

Answer:

- yes

### Lane B: fresh-run provisional guard observation

This was used to confirm that the finality guard still behaves correctly on a new live Deep Research run:

- provisional stays provisional
- early observation does not masquerade as final

This lane was not promoted to the only acceptance gate because fresh third-party Deep Research completion timing remains nondeterministic.

## 5. Why the wave is considered complete

The wave is complete because the production blockers were removed at the lane level:

1. primary path works
2. degraded path is explicit
3. health surface exists
4. timer is installed and active
5. route-validation is green
6. targeted regression suites are green

## 6. What remains intentionally outside this wave

This wave did not attempt to finish:

1. broad platform simplification
2. `scope_project` live backfill
3. promotion throughput tuning
4. retirement of advisor compatibility surfaces

That separation was intentional and should be preserved.
