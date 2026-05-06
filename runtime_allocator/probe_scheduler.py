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
import os
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


def probe_all(
    store: RuntimeStateStore,
    providers: Optional[list[str]] = None,
    profiles: Optional[dict] = None,
):
    """Probe all providers and update health store."""
    if profiles is None:
        try:
            from runtime_allocator.skill_agent import load_profiles
        except ImportError:
            from skill_agent import load_profiles
        profiles = load_profiles()

    targets = providers or list(profiles.get("runtimes", {}).keys()) or DEFAULT_PROVIDERS
    for pid in targets:
        rt = profiles.get("runtimes", {}).get(pid) if profiles else None
        if rt is None:
            logger.warning("probe_skip_unknown_provider", extra={"provider_id": pid})
            continue
        if not rt.get("enabled", True):
            store.update_health(provider_id=pid, status="disabled")
            continue

        endpoint = rt.get("endpoint", "")
        protocol = rt.get("protocol", "openai_compatible")
        timeout = rt.get("health_timeout_ms", 5000) / 1000.0
        api_key_env = rt.get("api_key_env")
        api_key = os.getenv(api_key_env, "") if api_key_env else None

        try:
            result = probe_by_protocol(endpoint, pid, protocol, timeout=timeout, api_key=api_key or None)
            status = "healthy" if result.available else "down"
            store.update_health(
                provider_id=pid,
                status=status,
                latency_ms=int(result.latency_ms),
                error=result.error,
                circuit_open_seconds=900 if not result.available else 0,
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
