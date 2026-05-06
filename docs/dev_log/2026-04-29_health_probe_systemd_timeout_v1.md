# 2026-04-29 Health Probe Systemd Timeout

## Context

During the 10 hour client-usage watch, `chatgptrest-health-probe.service` timed out three times:

- 2026-04-29 00:33 CST
- 2026-04-29 00:47 CST
- 2026-04-29 01:03 CST

Manual `ops/health_probe.py --fix --json` runs completed in about 0.5 seconds afterward, so the service failures were not caused by a persistent broken check.

## Root Cause

The live user unit had `TimeoutStartSec=60`. Under the same host memory/swap pressure that caused the earlyoom incident, the oneshot process could be delayed long enough for systemd to terminate it before it emitted probe output.

This is a monitoring-plane failure: it does not directly break ChatgptREST job execution, but it makes health telemetry unreliable during exactly the kind of host pressure where telemetry matters.

## Fix

- Added tracked systemd units:
  - `ops/systemd/chatgptrest-health-probe.service`
  - `ops/systemd/chatgptrest-health-probe.timer`
- Set tracked service timeout to `TimeoutStartSec=180`.
- Added live drop-in:
  - `/home/yuanhaizhou/.config/systemd/user/chatgptrest-health-probe.service.d/10-timeout.conf`
- Ran `systemctl --user daemon-reload`.
- Reset failed state and manually started `chatgptrest-health-probe.service`.

## Validation

Manual service start completed successfully at 2026-04-29 01:20 CST:

- health probe PASS
- API, dashboard, MCP, jobdb, KB, memory, earlyoom recent kills, public MCP ingress, and maintenance timers OK
- one stale `needs_followup` remained as a candidate but did not fail health

## Follow-Up

Do not reduce the timer service timeout back to 60 seconds. If probes become genuinely stuck, add per-check timeout instrumentation instead of relying on a short systemd kill window.
