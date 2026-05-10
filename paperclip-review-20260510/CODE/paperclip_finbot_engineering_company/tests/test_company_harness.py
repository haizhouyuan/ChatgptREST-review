from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.company_dry_run import build_manifest
from tools.validate_apply_register_gate import validate_gate
from tools.validate_issue_closeout import validate_closeout
from tools.validate_kimi_smoke_result import validate
from tools.validate_write_scope import ROOT, validate_path


def test_write_scope_allows_company_root_and_blocks_maint():
    assert validate_path(ROOT / "artifacts/dry_run/company_seed_manifest.json")["status"] == "pass"
    blocked = validate_path("/vol1/maint/docs/profinbot批判.md")
    assert blocked["status"] == "blocked"


def test_dry_run_manifest_does_not_apply():
    manifest = build_manifest()
    assert manifest["mode"] == "dry_run"
    assert manifest["apply"] is False
    assert len(manifest["agents"]) == 4
    assert manifest["external_reviewers"] == ["Codex Architecture Reviewer"]


def test_closeout_validator_rejects_plan_only(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"issue_id": "FINBOT-ENG-X", "status": "closed"}), encoding="utf-8")
    result = validate_closeout(path)
    assert result["status"] == "blocked"
    assert result["reason"] == "missing_required_fields"


def test_kimi_blocked_evidence_is_explicit():
    evidence = json.loads((ROOT / "artifacts/kimi_smoke/KIMI_SMOKE_BLOCKED.json").read_text(encoding="utf-8"))
    assert evidence["status"] == "blocked"
    assert evidence["actual_artifact_exists"] is False
    assert evidence["finbot_execution"] is False
    assert evidence["paperclip_apply"] is False


def test_apply_register_gate_fails_closed_until_kimi_passes():
    result = validate_gate(ROOT)
    assert result["status"] == "blocked"
    assert result["apply_allowed"] is False
    assert result["register_allowed"] is False


def test_kimi_smoke_result_passes_after_no_mcp_profile():
    result = validate(ROOT / "artifacts/kimi_smoke/KIMI_SMOKE_RESULT.json")
    assert result["status"] == "pass"
