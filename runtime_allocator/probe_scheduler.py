"""Background health probe scheduler.

Periodically probes all configured providers and updates their health
status in RuntimeStateStore. Can be run as a standalone process or
integrated into the service lifespan.

Usage:
    python -m runtime_allocator.probe_scheduler --interval 60
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Optional

from runtime_allocator.runtime_probe import ProbeResult, probe_by_protocol
from runtime_allocator.runtime_state import RuntimeStateStore

logger = logging.getLogger("probe_scheduler")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(_handler)


DEFAULT_PROVIDERS = ["claudekimi", "minimax", "gemini_local", "ollama_gpu0"]


def probe_all(store: RuntimeStateStore, providers: Optional[list[str]] = None):
    """Probe all providers and update health store."""
    targets = providers or DEFAULT_PROVIDERS
    for pid in targets:
        try:
            result = probe_by_protocol(pid)
            status = "healthy" if result.healthy else "down"
            store.update_health(
                provider_id=pid,
                status=status,
                latency_ms=int(result.latency_ms),
                error=result.error,
                circuit_open_seconds=900 if not result.healthy else 0,
            )
            logger.info(
                "probe_complete",
                extra={
                    "provider_id": pid,
                    "status": status,
                    "latency_ms": int(result.latency_ms),
                },
            )
        except Exception as exc:
            logger.error("probe_failed", extra={"provider_id": pid, "error": str(exc)})
            store.update_health(
                provider_id=pid,
                status="down",
                error=str(exc),
                circuit_open_seconds=900,
            )


def run_loop(interval_seconds: int = 60, providers: Optional[list[str]] = None):
    """Run the probe scheduler in an infinite loop."""
    store = RuntimeStateStore()
    logger.info("probe_scheduler_start", extra={"interval": interval_seconds})
    while True:
        probe_all(store, providers)
        time.sleep(interval_seconds)


def main():
    parser = argparse.ArgumentParser(description="Health probe scheduler")
    parser.add_argument("--interval", type=int, default=60, help="Probe interval in seconds")
    parser.add_argument("--providers", default="", help="Comma-separated provider IDs")
    args = parser.parse_args()

    providers = None
    if args.providers:
        providers = [p.strip() for p in args.providers.split(",")]

    try:
        run_loop(interval_seconds=args.interval, providers=providers)
    except KeyboardInterrupt:
        logger.info("probe_scheduler_stop")
        sys.exit(0)


if __name__ == "__main__":
    main()
