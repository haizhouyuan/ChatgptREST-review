# 2026-03-09 OpenClaw OpenMind Review Hardening Round 18

## Trigger

During the external review wait window, a local consistency check found one remaining documentation drift:

- the supported topology and verifier already removed `env-http-proxy` from the enabled baseline
- the blueprint and rebuild write-up still described it as if it were part of the supported production plugin set

That mismatch was enough to create avoidable review noise even though the live config and public verifier outputs were already correct.

## Changes

- updated `docs/integrations/openclaw_openmind_best_practice_blueprint_20260309.md`
  - removed `env-http-proxy` from the "Keep enabled now" production plugin set
  - moved it to a host-override note under "Do not enable for this deployment"
- updated `docs/dev_log/2026-03-09_openclaw_openmind_best_practice_rebuild.md`
  - clarified that `env-http-proxy` may still exist as an installed local plugin
  - explicitly stated that it is no longer part of the supported enabled baseline

## Validation

```bash
rg -n "env-http-proxy|installed/local|Do not enable" \
  docs/integrations/openclaw_openmind_best_practice_blueprint_20260309.md \
  docs/dev_log/2026-03-09_openclaw_openmind_best_practice_rebuild.md \
  docs/reviews/openclaw_openmind_topology_review_bundle_20260309.md
```

## Outcome

The public review package, blueprint, and rebuild notes now describe the same supported plugin posture: `env-http-proxy` is not part of the accepted production baseline.
