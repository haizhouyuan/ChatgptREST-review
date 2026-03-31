from __future__ import annotations

import json
from pathlib import Path

from chatgptrest import autoorch
from chatgptrest import finbot


def test_watchlist_scout_writes_pending_inbox_item(tmp_path: Path, monkeypatch) -> None:
    def _fake_snapshot(**_: object) -> dict[str, object]:
        return {
            "scope": "today",
            "priority_targets": [
                {
                    "thesis_id": "transformer-supercycle",
                    "thesis_title": "变压器超级周期",
                    "target_case_id": "tc_transformer_tbea",
                    "action_state": "starter",
                    "validation_state": "evidence_backed",
                    "reason": "订单交期仍在高位。",
                }
            ],
            "queue_summary": {"decision_maintenance": 3, "review_remediation": 0},
            "summary": {"theses": 14},
            "top_theses": [{"thesis_id": "transformer-supercycle"}],
        }

    monkeypatch.setattr(finbot, "_run_finagent_snapshot", _fake_snapshot)

    payload = autoorch.watchlist_scout(root=tmp_path)

    assert payload["ok"] is True
    assert payload["created"] is True
    json_path = Path(payload["json_path"])
    md_path = Path(payload["markdown_path"])
    assert json_path.exists()
    assert md_path.exists()
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["category"] == "watchlist_scout"
    assert "decision_maintenance" in saved["payload"]["queue_summary"]


def test_watchlist_scout_dedupes_identical_payload(tmp_path: Path, monkeypatch) -> None:
    def _fake_snapshot(**_: object) -> dict[str, object]:
        return {
            "scope": "today",
            "priority_targets": [{"thesis_id": "memory-bifurcation", "thesis_title": "存储分化", "reason": "same"}],
            "queue_summary": {},
            "summary": {},
            "top_theses": [],
        }

    monkeypatch.setattr(finbot, "_run_finagent_snapshot", _fake_snapshot)

    first = autoorch.watchlist_scout(root=tmp_path)
    second = autoorch.watchlist_scout(root=tmp_path)

    assert first["created"] is True
    assert second["created"] is False
    assert first["item_id"] == second["item_id"]


def test_ack_inbox_item_moves_files_to_archive(tmp_path: Path) -> None:
    item = autoorch.InboxItem(
        item_id="watchlist-scout-demo",
        created_at=1.0,
        title="demo",
        summary="summary",
        category="watchlist_scout",
        severity="accent",
        source="test",
        action_hint="read it",
        payload={},
    )
    write_payload = autoorch.write_inbox_item(item, root=tmp_path)
    json_path = Path(write_payload["json_path"])
    assert json_path.exists()

    result = autoorch.ack_inbox_item(item.item_id, root=tmp_path)

    assert result["ok"] is True
    assert not json_path.exists()
    assert Path(result["archived_json"]).exists()
