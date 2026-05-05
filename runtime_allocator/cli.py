"""Admin CLI for Paperclip Runtime Allocator operations.

Commands:
    health          Show service and provider health
    summary         Show runtime state summary
    billing         Show daily cost attribution
    audit           Export audit trail to NDJSON
    cleanup         Apply data retention policy
    probe           Probe a specific provider

Usage:
    python -m runtime_allocator.cli health
    python -m runtime_allocator.cli billing --company-id acme
    python -m runtime_allocator.cli audit --output /tmp/audit.ndjson
    python -m runtime_allocator.cli cleanup --retention-days 30
    python -m runtime_allocator.cli probe --provider-id minimax
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from runtime_allocator.compliance import AuditTrailExporter, RetentionPolicy
from runtime_allocator.cost_attribution import CostAttribution
from runtime_allocator.runtime_state import RuntimeStateStore
from runtime_allocator.runtime_probe import probe_by_protocol


def _get_store() -> RuntimeStateStore:
    return RuntimeStateStore()


def cmd_health(args: argparse.Namespace):
    store = _get_store()
    with store._connect() as conn:
        health_rows = conn.execute("SELECT * FROM runtime_health").fetchall()
        print("Provider Health:")
        for row in health_rows:
            print(f"  {row['provider_id']}: {row['status']} (failures={row['consecutive_failures']})")


def cmd_summary(args: argparse.Namespace):
    store = _get_store()
    summary = store.summary()
    print(json.dumps(summary, indent=2, default=str))


def cmd_billing(args: argparse.Namespace):
    store = _get_store()
    ca = CostAttribution(store)
    result = ca.daily_summary(company_id=args.company_id or "", date=args.date)
    print(json.dumps(result, indent=2, default=str))


def cmd_audit(args: argparse.Namespace):
    store = _get_store()
    exporter = AuditTrailExporter(store)
    path = exporter.export_range(
        start=args.start,
        end=args.end,
        output_path=args.output,
    )
    print(f"Audit trail exported to: {path}")


def cmd_cleanup(args: argparse.Namespace):
    store = _get_store()
    policy = RetentionPolicy(store)
    result = policy.apply(retention_days=args.retention_days)
    print(json.dumps(result, indent=2))


def cmd_probe(args: argparse.Namespace):
    store = _get_store()
    result = probe_by_protocol(args.provider_id)
    print(json.dumps(result, indent=2, default=str))
    # Update health store
    store.update_health(
        args.provider_id,
        status="healthy" if result.healthy else "down",
        latency_ms=int(result.latency_ms),
        error=result.error,
        circuit_open_seconds=900 if not result.healthy else 0,
    )


def main():
    parser = argparse.ArgumentParser(description="Paperclip Runtime Allocator CLI")
    subparsers = parser.add_subparsers(dest="command")

    # health
    subparsers.add_parser("health", help="Show provider health status")

    # summary
    subparsers.add_parser("summary", help="Show runtime state summary")

    # billing
    billing_parser = subparsers.add_parser("billing", help="Show daily cost attribution")
    billing_parser.add_argument("--company-id", default="", help="Filter by company")
    billing_parser.add_argument("--date", default=None, help="YYYY-MM-DD (default today)")

    # audit
    audit_parser = subparsers.add_parser("audit", help="Export audit trail")
    audit_parser.add_argument("--output", required=True, help="Output NDJSON file path")
    audit_parser.add_argument("--start", default=None, help="Start ISO datetime")
    audit_parser.add_argument("--end", default=None, help="End ISO datetime")

    # cleanup
    cleanup_parser = subparsers.add_parser("cleanup", help="Apply retention policy")
    cleanup_parser.add_argument("--retention-days", type=int, default=90, help="Retention period in days")

    # probe
    probe_parser = subparsers.add_parser("probe", help="Probe a provider")
    probe_parser.add_argument("--provider-id", required=True, help="Provider to probe")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    handlers = {
        "health": cmd_health,
        "summary": cmd_summary,
        "billing": cmd_billing,
        "audit": cmd_audit,
        "cleanup": cmd_cleanup,
        "probe": cmd_probe,
    }

    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
