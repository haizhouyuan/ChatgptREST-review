"""Tests for FIN-10 Primary Source Evidence Graph and Connector Route Smoke.

These tests validate:
1. The PrimarySourceEvidenceGraph structure and node/edge consistency
2. Connector route smoke test output
3. EvidenceItem artifact checksums match actual files
4. Cross-references between graph nodes are valid
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.connector_route_smoke import run_smoke, _normalize_node_to_record
from tools.minimal_gatekeeper import validate_record


REPO = Path(__file__).resolve().parents[1]
GRAPH_PATH = (
    REPO
    / "runs/2026-05-07_finbot_v2_1_repair_execution"
    / "day10_primary_source_evidence_graph"
    / "primary_source_evidence_graph_v1.json"
)
SMOKE_REPORT_PATH = (
    REPO
    / "runs/2026-05-07_finbot_v2_1_repair_execution"
    / "day10_primary_source_evidence_graph"
    / "connector_smoke_report_v1.json"
)
RUN_DAY3 = REPO / "runs/2026-05-07_finbot_v2_1_repair_execution/day3_connector_spike_a"


def load_graph() -> dict:
    return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))


def test_graph_file_exists_and_is_valid_json():
    assert GRAPH_PATH.exists()
    graph = load_graph()
    assert graph["record_type"] == "PrimarySourceEvidenceGraph"
    assert graph["graph_id"].startswith("PSEG-FINBOT")


def test_graph_has_all_node_types():
    graph = load_graph()
    nodes = graph["nodes"]
    required_types = {
        "SourceRoute", "FetchAttempt", "EvidenceItem", "ContentItem",
        "Claim", "EvidenceGap", "OpportunityCase", "SignalWindow",
    }
    assert required_types.issubset(set(nodes.keys()))


def test_all_nodes_have_node_id_and_node_type():
    graph = load_graph()
    for node_type, node_list in graph["nodes"].items():
        for node in node_list:
            assert "node_id" in node, f"Missing node_id in {node_type}"
            assert "node_type" in node, f"Missing node_type in {node_type}"
            assert node["node_type"] == node_type, f"node_type mismatch for {node['node_id']}"


def test_all_edges_reference_existing_nodes():
    graph = load_graph()
    all_node_ids = set()
    for node_list in graph["nodes"].values():
        for node in node_list:
            all_node_ids.add(node["node_id"])

    for edge in graph["edges"]:
        assert edge["from"] in all_node_ids, f"Edge from non-existent node: {edge['from']}"
        assert edge["to"] in all_node_ids, f"Edge to non-existent node: {edge['to']}"


def test_evidence_items_have_valid_checksums():
    graph = load_graph()
    evidence_items = graph["nodes"]["EvidenceItem"]
    for ei in evidence_items:
        raw_path = ei.get("raw_path")
        expected_sha = ei.get("sha256")
        assert raw_path, f"EvidenceItem {ei['node_id']} missing raw_path"
        assert expected_sha, f"EvidenceItem {ei['node_id']} missing sha256"
        assert len(expected_sha) == 64, f"EvidenceItem {ei['node_id']} sha256 not 64 chars"

        # Resolve path
        candidates = [
            REPO / raw_path,
            RUN_DAY3 / raw_path,
            REPO / "runs/2026-05-07_finbot_v2_1_repair_execution/day3_connector_spike_a" / raw_path,
        ]
        resolved = None
        for candidate in candidates:
            if candidate.exists():
                resolved = candidate
                break
        assert resolved is not None, f"Artifact not found for {ei['node_id']}: {raw_path}"

        import hashlib
        digest = hashlib.sha256()
        with resolved.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        actual_sha = digest.hexdigest()
        assert actual_sha.lower() == expected_sha.lower(), (
            f"Checksum mismatch for {ei['node_id']}: expected {expected_sha}, got {actual_sha}"
        )


def test_graph_statistics_match_actual_counts():
    graph = load_graph()
    stats = graph["graph_statistics"]
    actual_node_count = sum(len(v) for v in graph["nodes"].values())
    actual_edge_count = len(graph["edges"])
    assert stats["total_nodes"] == actual_node_count
    assert stats["total_edges"] == actual_edge_count

    for node_type, node_list in graph["nodes"].items():
        assert stats["node_type_counts"].get(node_type) == len(node_list)


def test_connector_smoke_report_exists_and_valid():
    assert SMOKE_REPORT_PATH.exists()
    report = json.loads(SMOKE_REPORT_PATH.read_text(encoding="utf-8"))
    assert report["status"] in ("pass", "blocked", "partial")
    assert report["graph_id"] == load_graph()["graph_id"]


def test_smoke_tested_success_routes_have_no_issues():
    report = json.loads(SMOKE_REPORT_PATH.read_text(encoding="utf-8"))
    for route_result in report["route_results"]:
        if route_result["status"] == "pass":
            assert route_result["issue_count"] == 0, (
                f"Route {route_result['route_id']} marked pass but has issues"
            )


def test_sec_and_cninfo_routes_pass_smoke():
    report = json.loads(SMOKE_REPORT_PATH.read_text(encoding="utf-8"))
    by_id = {r["route_id"]: r for r in report["route_results"]}
    assert by_id["SR-US-SEC"]["status"] == "pass"
    assert by_id["SR-CN-CNINFO"]["status"] == "pass"
    assert by_id["SR-US-OPENBB"]["status"] == "blocked"


def test_contract_only_routes_are_skipped():
    report = json.loads(SMOKE_REPORT_PATH.read_text(encoding="utf-8"))
    skipped_routes = ["SR-CN-SSE", "SR-CN-SZSE", "SR-HK-HKEX", "SR-KR-DART"]
    by_id = {r["route_id"]: r for r in report["route_results"]}
    for route_id in skipped_routes:
        assert by_id[route_id]["status"] == "skipped"


def test_evidence_items_pass_minimal_gatekeeper():
    graph = load_graph()
    for ei in graph["nodes"]["EvidenceItem"]:
        record = _normalize_node_to_record(ei)
        issues = validate_record(record)
        assert not issues, f"Gatekeeper blocked {ei['node_id']}: {[i.to_dict() for i in issues]}"


def test_smoke_runnable_from_python_api():
    result = run_smoke(GRAPH_PATH, REPO)
    assert result["status"] in ("pass", "blocked", "partial")
    assert result["routes_tested"] == 7
    assert result["summary"]["pass"] == 2
    assert result["summary"]["skipped"] == 4
    assert result["summary"]["blocked"] == 1
