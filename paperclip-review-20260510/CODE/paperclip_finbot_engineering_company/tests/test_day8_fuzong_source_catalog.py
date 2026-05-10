import json
import pathlib


BASE = pathlib.Path("runs/2026-05-07_finbot_v2_1_repair_execution/day8_fuzong_source_catalog")


def load_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_day8_catalog_marks_latest_rows_as_not_claim_ready():
    rows = load_jsonl(BASE / "fuzong_source_catalog_v1.jsonl")
    latest_rows = [row for row in rows if row["platform"] == "douyin_jingxuan"]

    assert latest_rows
    assert all(row["claim_ready"] is False for row in latest_rows)
    assert all(row["material_state"] == "metadata_only_not_claim_ready" for row in latest_rows)
    assert any(row["published_at"] == "2026-04-28" for row in latest_rows)
    assert any(row.get("observed_relative_published_label") == "1小时前" for row in latest_rows)


def test_day8_summary_keeps_not_complete_verdict():
    summary = json.loads((BASE / "fuzong_material_state_summary.json").read_text(encoding="utf-8"))

    assert summary["verdict"] == "FUZONG_LATEST_SOURCE_CATALOG_NOT_COMPLETE_TRANSCRIPT_BLOCKED"
    assert summary["total_catalog_items"] == 26
    assert summary["claim_ready_items"] == 1
    assert summary["source_url_status_counts"]["related_item_visible_no_direct_url"] == 10
    assert summary["source_url_status_counts"]["verified_jingxuan_anchor_page"] == 1


def test_day8_bilibili_metadata_has_raw_snapshot_hashes():
    rows = load_jsonl(BASE / "fuzong_source_catalog_v1.jsonl")
    bilibili_rows = [row for row in rows if row["platform"] == "bilibili"]

    assert len(bilibili_rows) == 10
    for row in bilibili_rows:
        raw_path = pathlib.Path(row["raw_metadata_path"])
        assert raw_path.exists()
        assert len(row["raw_metadata_sha256"]) == 64
        assert row["source_account_name"] == "机构一手调研-福总"
        assert row["source_url_status"] == "verified_bilibili_view_api"
