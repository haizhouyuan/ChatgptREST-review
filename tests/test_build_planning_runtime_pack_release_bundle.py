from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ops.build_planning_runtime_pack_release_bundle import build_release_bundle


def _recent_iso() -> str:
    """Generate a timestamp 1 hour ago — always fresh for max_age_hours=72."""
    return (datetime.now(UTC) - timedelta(hours=1)).isoformat()


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_build_release_bundle_marks_manual_review_when_sensitivity_flags(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    validation = tmp_path / "validation"
    sensitivity = tmp_path / "sensitivity"
    observability = tmp_path / "observability"
    out = tmp_path / "out"
    pack.mkdir()
    validation.mkdir()
    sensitivity.mkdir()
    observability.mkdir()

    _write(
        pack / "manifest.json",
        {
            "generated_at": _recent_iso(),
            "ok": True,
            "scope": {"opt_in_only": True, "default_runtime_cutover": False},
        },
    )
    for name in ["docs.tsv", "atoms.tsv", "retrieval_pack.json", "smoke_manifest.json", "README.md"]:
        (pack / name).write_text("x\n", encoding="utf-8")

    _write(validation / "summary.json", {"ok": True})
    _write(sensitivity / "summary.json", {"ok": False, "flagged_docs": 0, "flagged_atoms": 2})
    _write(observability / "event_schema.json", {"event_types": ["planning.runtime_pack.hit"], "source_label": "explicit_planning_pack"})

    result = build_release_bundle(
        pack_dir=pack,
        validation_dir=validation,
        sensitivity_dir=sensitivity,
        observability_dir=observability,
        output_dir=out,
    )

    assert result["ok"] is True
    assert result["ready_for_explicit_consumption"] is False
    assert "sensitivity_manual_review_required" in result["blocking_findings"]
    manifest = json.loads((out / "release_bundle_manifest.json").read_text(encoding="utf-8"))
    assert manifest["manual_review_required"] is True
    assert manifest["checks"]["release_readiness_ready"] is True
    assert manifest["checks"]["offline_validation_ok"] is True
    assert manifest["checks"]["observability_schema_present"] is True
    assert manifest["checks"]["sensitivity_clear"] is False
    assert (out / "rollback_runbook.md").exists()


def test_build_release_bundle_ready_when_all_checks_are_green(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    validation = tmp_path / "validation"
    sensitivity = tmp_path / "sensitivity"
    observability = tmp_path / "observability"
    out = tmp_path / "out"
    pack.mkdir()
    validation.mkdir()
    sensitivity.mkdir()
    observability.mkdir()

    _write(
        pack / "manifest.json",
        {
            "generated_at": _recent_iso(),
            "ok": True,
            "scope": {"opt_in_only": True, "default_runtime_cutover": False},
        },
    )
    for name in ["docs.tsv", "atoms.tsv", "retrieval_pack.json", "smoke_manifest.json", "README.md"]:
        (pack / name).write_text("x\n", encoding="utf-8")

    _write(validation / "summary.json", {"ok": True})
    _write(
        sensitivity / "summary.json",
        {
            "ok": True,
            "flagged_docs": 0,
            "flagged_atoms": 2,
            "approved_flagged_docs": 0,
            "approved_flagged_atoms": 2,
            "unresolved_flagged_docs": 0,
            "unresolved_flagged_atoms": 0,
        },
    )
    _write(observability / "event_schema.json", {"event_types": ["planning.runtime_pack.hit"], "source_label": "explicit_planning_pack"})

    result = build_release_bundle(
        pack_dir=pack,
        validation_dir=validation,
        sensitivity_dir=sensitivity,
        observability_dir=observability,
        output_dir=out,
    )

    manifest = json.loads((out / "release_bundle_manifest.json").read_text(encoding="utf-8"))
    assert result["ready_for_explicit_consumption"] is True
    assert manifest["ready_for_explicit_consumption"] is True
    assert manifest["blocking_findings"] == []
    assert manifest["sensitivity_summary"]["approved_flagged_atoms"] == 2
