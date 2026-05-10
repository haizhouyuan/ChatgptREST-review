#!/usr/bin/env python3
"""Finbot v2.1 connector route smoke test.

This tool smoke-tests primary source connector routes by:
1. Reading the PrimarySourceEvidenceGraph
2. Verifying EvidenceItem raw artifacts exist and checksums match
3. Running artifacts through the minimal gatekeeper
4. Checking cross-references between FetchAttempt, EvidenceItem, and SourceRoute
5. Producing a smoke test report

Usage:
    python3 tools/connector_route_smoke.py
    python3 tools/connector_route_smoke.py --graph path/to/graph.json --repo-root .
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Import minimal gatekeeper
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.minimal_gatekeeper import validate_record


REPO = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = (
    REPO
    / "runs/2026-05-07_finbot_v2_1_repair_execution"
    / "day10_primary_source_evidence_graph"
    / "primary_source_evidence_graph_v1.json"
)


@dataclass
class SmokeIssue:
    code: str
    node_id: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "node_id": self.node_id, "message": self.message}


@dataclass
class SmokeResult:
    route_id: str
    status: str  # "pass", "blocked", "skipped"
    issues: list[SmokeIssue] = field(default_factory=list)
    evidence_items_checked: list[str] = field(default_factory=list)
    fetch_attempts_checked: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "status": self.status,
            "issue_count": len(self.issues),
            "issues": [issue.to_dict() for issue in self.issues],
            "evidence_items_checked": self.evidence_items_checked,
            "fetch_attempts_checked": self.fetch_attempts_checked,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_artifact_path(raw_path: str, repo_root: Path) -> Path | None:
    """Resolve artifact path relative to repo root or run directories."""
    candidates = [
        repo_root / raw_path,
        repo_root / "runs/2026-05-07_finbot_v2_1_repair_execution/day3_connector_spike_a" / raw_path,
        repo_root / "runs/2026-05-07_finbot_v2_1_repair_execution/day5_claim_extraction" / raw_path,
        repo_root / "runs/2026-05-07_finbot_v2_1_repair_execution/day6_historical_replay_signalwindow" / raw_path,
        repo_root / "runs/2026-05-07_finbot_full_system_execution_v2" / raw_path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _find_nodes_by_type(graph: dict[str, Any], node_type: str) -> list[dict[str, Any]]:
    nodes = graph.get("nodes", {})
    return nodes.get(node_type, [])


def _find_node_by_id(graph: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for node_type, node_list in graph.get("nodes", {}).items():
        for node in node_list:
            if node.get("node_id") == node_id:
                return node
    return None


def _edges_from(graph: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    return [e for e in graph.get("edges", []) if e.get("from") == node_id]


def _edges_to(graph: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    return [e for e in graph.get("edges", []) if e.get("to") == node_id]


def _normalize_node_to_record(node: dict[str, Any]) -> dict[str, Any]:
    """Convert graph node to flat record for gatekeeper validation."""
    record = dict(node)
    node_type = record.get("node_type")
    node_id = record.pop("node_id", None)

    # Map node_id to type-specific ID field
    id_field_map = {
        "EvidenceItem": "evidence_item_id",
        "FetchAttempt": "fetch_attempt_id",
        "ContentItem": "content_item_id",
        "Claim": "claim_id",
        "EvidenceGap": "evidence_gap_id",
        "OpportunityCase": "opportunity_case_id",
        "SignalWindow": "signal_window_id",
        "SourceRoute": "source_route_id",
    }
    if node_type and node_id:
        id_field = id_field_map.get(node_type)
        if id_field:
            record[id_field] = node_id

    # Map node_type to record_type
    if node_type:
        record["record_type"] = node_type

    return record


def smoke_test_route(
    route: dict[str, Any],
    graph: dict[str, Any],
    repo_root: Path,
) -> SmokeResult:
    route_id = route["node_id"]
    connector_status = route.get("connector_status", "")
    result = SmokeResult(route_id=route_id, status="skipped")

    if connector_status == "contract_only_not_smoke_tested":
        result.status = "skipped"
        result.issues.append(
            SmokeIssue(
                "NOT_SMOKE_TESTED",
                route_id,
                "Route is contract-only; no smoke test artifact exists",
            )
        )
        return result

    if connector_status == "smoke_tested_blocked":
        result.status = "blocked"
        # Find the blocked fetch attempt
        fetch_attempts = _find_nodes_by_type(graph, "FetchAttempt")
        for fa in fetch_attempts:
            if fa.get("source_route_id") == route_id and fa.get("status") == "blocked":
                result.fetch_attempts_checked.append(fa["node_id"])
                if not fa.get("block_reason"):
                    result.issues.append(
                        SmokeIssue(
                            "BLOCKED_FETCH_MISSING_REASON",
                            fa["node_id"],
                            "Blocked FetchAttempt missing block_reason",
                        )
                    )
        return result

    if connector_status != "smoke_tested_success":
        result.status = "blocked"
        result.issues.append(
            SmokeIssue(
                "UNKNOWN_CONNECTOR_STATUS",
                route_id,
                f"Unexpected connector_status: {connector_status}",
            )
        )
        return result

    # Smoke tested success — verify artifacts
    result.status = "pass"

    # Find EvidenceItems for this route
    evidence_items = _find_nodes_by_type(graph, "EvidenceItem")
    route_evidence = [ei for ei in evidence_items if ei.get("source_route_id") == route_id]

    if not route_evidence:
        result.status = "blocked"
        result.issues.append(
            SmokeIssue(
                "SMOKE_SUCCESS_BUT_NO_EVIDENCE",
                route_id,
                "Route marked smoke_tested_success but no EvidenceItem found",
            )
        )
        return result

    for ei in route_evidence:
        result.evidence_items_checked.append(ei["node_id"])
        normalized = _normalize_node_to_record(ei)

        # Check required fields
        required = ["evidence_item_id", "source_route_id", "raw_path", "sha256", "published_at", "available_at"]
        for field in required:
            if not normalized.get(field):
                result.status = "blocked"
                result.issues.append(
                    SmokeIssue(
                        "EV_MISSING_REQUIRED_FIELD",
                        ei["node_id"],
                        f"EvidenceItem missing required field: {field}",
                    )
                )

        # Validate through minimal gatekeeper
        gate_issues = validate_record(normalized)
        for issue in gate_issues:
            result.status = "blocked"
            result.issues.append(
                SmokeIssue(
                    issue.code,
                    ei["node_id"],
                    issue.message,
                )
            )

        # Check raw artifact exists and checksum matches
        raw_path = ei.get("raw_path")
        expected_sha = ei.get("sha256")
        if raw_path and expected_sha:
            resolved = resolve_artifact_path(raw_path, repo_root)
            if not resolved:
                result.status = "blocked"
                result.issues.append(
                    SmokeIssue(
                        "EV_RAW_PATH_NOT_FOUND",
                        ei["node_id"],
                        f"raw_path not found: {raw_path}",
                    )
                )
            else:
                actual_sha = sha256_file(resolved)
                if actual_sha.lower() != expected_sha.lower():
                    result.status = "blocked"
                    result.issues.append(
                        SmokeIssue(
                            "EV_SHA256_MISMATCH",
                            ei["node_id"],
                            f"sha256 mismatch: expected {expected_sha}, got {actual_sha}",
                        )
                    )

    # Find FetchAttempts for this route
    fetch_attempts = _find_nodes_by_type(graph, "FetchAttempt")
    route_fetches = [fa for fa in fetch_attempts if fa.get("source_route_id") == route_id]
    for fa in route_fetches:
        result.fetch_attempts_checked.append(fa["node_id"])
        if fa.get("status") == "blocked" and not fa.get("block_reason"):
            result.status = "blocked"
            result.issues.append(
                SmokeIssue(
                    "BLOCKED_FETCH_MISSING_REASON",
                    fa["node_id"],
                    "Blocked FetchAttempt missing block_reason",
                )
            )

    # Verify edge consistency: every EvidenceItem should have an edge to its SourceRoute
    for ei in route_evidence:
        edges = _edges_from(graph, ei["node_id"])
        route_edges = [e for e in edges if e.get("to") == route_id and e.get("edge_type") == "evidence_to_source_route"]
        if not route_edges:
            result.status = "blocked"
            result.issues.append(
                SmokeIssue(
                    "GRAPH_EDGE_MISSING",
                    ei["node_id"],
                    f"Missing evidence_to_source_route edge to {route_id}",
                )
            )

    return result


def run_smoke(graph_path: Path, repo_root: Path) -> dict[str, Any]:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    if graph.get("record_type") != "PrimarySourceEvidenceGraph":
        return {
            "status": "blocked",
            "error": "Input file is not a PrimarySourceEvidenceGraph",
        }

    routes = _find_nodes_by_type(graph, "SourceRoute")
    results: list[SmokeResult] = []

    for route in routes:
        results.append(smoke_test_route(route, graph, repo_root))

    # Overall status
    any_blocked = any(r.status == "blocked" for r in results)
    all_pass = all(r.status == "pass" for r in results if r.status != "skipped")
    overall_status = "blocked" if any_blocked else ("pass" if all_pass else "partial")

    summary = {
        "pass": sum(1 for r in results if r.status == "pass"),
        "blocked": sum(1 for r in results if r.status == "blocked"),
        "skipped": sum(1 for r in results if r.status == "skipped"),
    }

    return {
        "status": overall_status,
        "graph_id": graph.get("graph_id"),
        "routes_tested": len(results),
        "summary": summary,
        "route_results": [r.to_dict() for r in results],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finbot v2.1 connector route smoke test")
    parser.add_argument(
        "--graph",
        type=Path,
        default=DEFAULT_GRAPH,
        help="Path to PrimarySourceEvidenceGraph JSON",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO,
        help="Repository root for resolving artifact paths",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for smoke test report JSON",
    )
    args = parser.parse_args(argv)

    result = run_smoke(args.graph, args.repo_root.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
