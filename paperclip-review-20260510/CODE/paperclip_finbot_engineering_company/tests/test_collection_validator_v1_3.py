import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validators.collection_v1_3 import load_collection, validate_collection


REPO = Path(__file__).resolve().parents[1]
RUN = REPO / "runs/2026-05-07_finbot_v2_1_repair_execution"


def _result(paths: list[Path]):
    records = load_collection(paths)
    return validate_collection(records, REPO)


def _write_json(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_actual_day3_day5_day6_bundle_passes_collection_gate():
    result = _result(
        [
            RUN / "day3_connector_spike_a/connector_spike_results_day3.jsonl",
            RUN / "day5_claim_extraction/content_items_fuzong_v2_1.jsonl",
            RUN / "day5_claim_extraction/claims_fuzong_v2_1.jsonl",
            RUN / "day5_claim_extraction/evidence_gaps_fuzong_v2_1.jsonl",
            RUN / "day6_historical_replay_signalwindow/opportunity_case_replay_v2_1.json",
            RUN / "day6_historical_replay_signalwindow/signal_window_dry_run_v2_1.json",
            RUN / "day6_historical_replay_signalwindow/evidence_gate_verdict_v2_1.json",
        ]
    )
    assert result["status"] == "pass", result
    assert result["record_type_counts"]["EvidenceGap"] == 10


def test_unknown_record_type_hard_fails(tmp_path: Path):
    path = _write_json(
        tmp_path,
        "unknown.json",
        {"record_type": "OfficialEvidence", "source_account_id": "SA-D-FUZONG"},
    )
    result = _result([path])
    assert result["status"] == "blocked"
    assert any(issue["code"] == "UNKNOWN_RECORD_TYPE" for issue in result["issues"])


def test_fake_candidate_without_corroboration_hard_fails(tmp_path: Path):
    source = json.loads(
        (RUN / "day6_historical_replay_signalwindow/opportunity_case_replay_v2_1.json").read_text(
            encoding="utf-8"
        )
    )
    source["case_status"] = "candidate"
    path = _write_json(tmp_path, "fake_candidate.json", source)
    result = _result([path])
    codes = {issue["code"] for issue in result["issues"]}
    assert result["status"] == "blocked"
    assert "CANDIDATE_WITHOUT_CORROBORATED_EVIDENCE" in codes
    assert "CANDIDATE_WITH_MISSING_PRIMARY_EVIDENCE" in codes


def test_live_window_and_uncorroborated_candidate_ref_hard_fail(tmp_path: Path):
    source = json.loads(
        (RUN / "day6_historical_replay_signalwindow/signal_window_dry_run_v2_1.json").read_text(
            encoding="utf-8"
        )
    )
    source["window_label"] = "live"
    source["opportunity_case_ref"]["case_status"] = "candidate"
    path = _write_json(tmp_path, "fake_live_window.json", source)
    result = _result([path])
    codes = {issue["code"] for issue in result["issues"]}
    assert result["status"] == "blocked"
    assert "LIVE_WINDOW_FORBIDDEN_IN_REPAIR_LANE" in codes
    assert "SIGNAL_WINDOW_CANDIDATE_WITHOUT_CORROBORATION" in codes


def test_money_unit_normalization_required_for_chinese_usd_yi(tmp_path: Path):
    content = RUN / "day5_claim_extraction/content_items_fuzong_v2_1.jsonl"
    claim = json.loads(
        (RUN / "day5_claim_extraction/claims_fuzong_v2_1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    claim.pop("numeric_values", None)
    path = _write_json(tmp_path, "claim_without_numeric.json", claim)
    result = _result([content, path])
    assert result["status"] == "blocked"
    assert any(issue["code"] == "NUMERIC_NORMALIZATION_MISSING" for issue in result["issues"])


def test_field_aware_forbidden_language_allows_source_names():
    result = _result(
        [
            RUN / "day5_claim_extraction/content_items_fuzong_v2_1.jsonl",
            RUN / "day5_claim_extraction/claims_fuzong_v2_1.jsonl",
            RUN / "day5_claim_extraction/evidence_gaps_fuzong_v2_1.jsonl",
        ]
    )
    assert result["status"] == "pass", result


def test_connector_capability_used_as_claim_evidence_hard_fails(tmp_path: Path):
    source = json.loads(
        (RUN / "day6_historical_replay_signalwindow/opportunity_case_replay_v2_1.json").read_text(
            encoding="utf-8"
        )
    )
    # Mutate connector_capability_evidence to also claim corroboration
    for ref in source.get("evidence_item_refs", []):
        if ref.get("used_for") == "connector_capability_evidence":
            ref["corroborates_claim_ids"] = ["CLM-FUZONG-20260117-001"]
    path = _write_json(tmp_path, "connector_as_claim_evidence.json", source)
    result = _result([path])
    codes = {issue["code"] for issue in result["issues"]}
    assert result["status"] == "blocked"
    assert "CONNECTOR_CAPABILITY_USED_AS_CLAIM_EVIDENCE" in codes


def test_review_window_missing_trigger_hard_fails(tmp_path: Path):
    rw = {
        "record_type": "ReviewWindow",
        "review_window_id": "RW-TEST-001",
        "opportunity_case_id": "OC-FUZONG-ADVPROC-20260117-001",
        "window_label": "60D",
        "access_tag": "research_only",
        "generated_at": "2026-05-07T00:00:00Z",
    }
    oc = json.loads(
        (RUN / "day6_historical_replay_signalwindow/opportunity_case_replay_v2_1.json").read_text(
            encoding="utf-8"
        )
    )
    path_oc = _write_json(tmp_path, "oc.json", oc)
    path_rw = _write_json(tmp_path, "rw.json", rw)
    result = _result([path_oc, path_rw])
    codes = {issue["code"] for issue in result["issues"]}
    assert result["status"] == "blocked"
    assert "REVIEW_WINDOW_MISSING_TRIGGER" in codes


def test_review_window_timing_for_field_hard_fails(tmp_path: Path):
    rw = {
        "record_type": "ReviewWindow",
        "review_window_id": "RW-TEST-002",
        "opportunity_case_id": "OC-FUZONG-ADVPROC-20260117-001",
        "window_label": "60D",
        "access_tag": "research_only",
        "review_trigger": "Q2 2026 earnings disclosure",
        "timing_for": "entry_before_earnings",
        "generated_at": "2026-05-07T00:00:00Z",
    }
    oc = json.loads(
        (RUN / "day6_historical_replay_signalwindow/opportunity_case_replay_v2_1.json").read_text(
            encoding="utf-8"
        )
    )
    path_oc = _write_json(tmp_path, "oc.json", oc)
    path_rw = _write_json(tmp_path, "rw.json", rw)
    result = _result([path_oc, path_rw])
    codes = {issue["code"] for issue in result["issues"]}
    assert result["status"] == "blocked"
    assert "REVIEW_WINDOW_TIMING_FORBIDDEN" in codes


def test_evidence_item_sha256_mismatch_hard_fails(tmp_path: Path):
    ev = {
        "record_type": "EvidenceItem",
        "evidence_item_id": "EI-TEST-20260507-001",
        "source_route_id": "SR-US-SEC",
        "raw_path": "nonexistent_file.txt",
        "sha256": "a" * 64,
        "fetched_at": "2026-05-01T00:00:00Z",
        "published_at": "2026-05-01T00:00:00Z",
        "available_at": "2026-05-01T00:00:00Z",
    }
    path = _write_json(tmp_path, "evidence_bad_sha.json", ev)
    result = _result([path])
    codes = {issue["code"] for issue in result["issues"]}
    assert result["status"] == "blocked"
    assert "EV_RAW_PATH_NOT_FOUND" in codes
