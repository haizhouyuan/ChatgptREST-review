# Productionization Residual Risk Note V1

Date: 2026-04-08

Related completion record:

- [Productionization Corrective Wave Completion V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_productionization_corrective_wave_completion_v1.md)

## 1. Residual risks after V5

The productionization corrective wave removed the concrete runtime blockers called out by review, but several broader risks remain intentionally open.

## 2. Residual risk inventory

### R1. Fresh Deep Research end-to-end wall-clock remains nondeterministic

Even after the primary-path fix, a brand-new Deep Research run can still remain in:

- `running`
- `completion_guard_downgraded`
- `provisional`

for a long time, depending on provider/runtime behavior.

This is not a public-lane contract bug anymore, but it remains a runtime characteristic that operators need to understand.

### R2. `scope_project` live broad write remains blocked

The repo now has:

- high coverage on `scope_project`
- backfill tooling
- better project-scoped retrieval substrate

But live broad write is still blocked until mismatch families are adjudicated and approved.

### R3. Promotion throughput is not yet solved

The maintenance scheduler is now installed and active, but this does not mean promotion throughput is solved.

Current status:

1. scheduling absence is no longer an acceptable explanation
2. throughput/coverage tuning still remains a later diagnosis and optimization problem

### R4. Broad surface simplification is still incomplete

The default lane is now clearer, but the broader surface still exists:

- internal/broad MCP
- advisor compatibility lane
- coding-agent narrow lane

That is acceptable for now, but it is not the final simplified surface state.

## 3. Operational reading

The right operational reading is:

1. `coding-agent-v1` is now safe to treat as the default production lane
2. the wider platform is still in staged consolidation
3. future waves should avoid reopening solved runtime blockers unless new evidence appears
