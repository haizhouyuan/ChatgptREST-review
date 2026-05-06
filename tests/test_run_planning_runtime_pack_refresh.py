from __future__ import annotations

import json
from pathlib import Path

from ops.run_planning_runtime_pack_refresh import refresh_runtime_pack


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_refresh_runtime_pack_runs_release_pipeline_and_uses_manifest_counts(tmp_path: Path, monkeypatch) -> None:
    refresh_root = tmp_path / "refresh"
    output_root = tmp_path / "packs"
    validation_root = tmp_path / "validation"
    sensitivity_root = tmp_path / "sensitivity"
    observability_root = tmp_path / "observability"
    release_root = tmp_path / "release"

    allowlist_dir = refresh_root / "20260408T000000Z"
    allowlist_dir.mkdir(parents=True)
    (allowlist_dir / "planning_review_decisions_v3_allowlist.tsv").write_text("doc_id\nfoo\n", encoding="utf-8")

    before_pack = output_root / "20260407T235959Z"
    _write_json(before_pack / "manifest.json", {"counts": {"exported_docs": 100, "exported_atoms": 200}})

    status_sequence = [
        {
            "available": True,
            "ready_for_explicit_consumption": True,
            "bundle_dir": str(release_root / "old_ready"),
            "pack_dir": str(before_pack),
        },
        {
            "available": True,
            "ready_for_explicit_consumption": True,
            "bundle_dir": "",
            "pack_dir": "",
        },
    ]
    latest_status = status_sequence[1]

    def fake_export_runtime_pack(*, db_path, allowlist_path, output_dir, require_consistent):
        _write_json(
            Path(output_dir) / "manifest.json",
            {
                "ok": True,
                "counts": {"exported_docs": 116, "exported_atoms": 258},
                "scope": {"opt_in_only": True, "default_runtime_cutover": False},
            },
        )
        return {
            "ok": True,
            "output_dir": str(output_dir),
            "manifest_path": str(Path(output_dir) / "manifest.json"),
            "exported_docs": 116,
            "exported_atoms": 258,
        }

    def fake_validation(*, pack_dir, output_dir, **kwargs):
        _write_json(Path(output_dir) / "summary.json", {"ok": True, "docs": 116, "atoms": 258})
        return {"ok": True, "output_dir": str(output_dir), "summary_path": str(Path(output_dir) / "summary.json")}

    def fake_sensitivity(*, pack_dir, output_dir, **kwargs):
        _write_json(
            Path(output_dir) / "summary.json",
            {"ok": True, "flagged_docs": 0, "flagged_atoms": 0, "unresolved_flagged_docs": 0, "unresolved_flagged_atoms": 0},
        )
        return {"ok": True, "output_dir": str(output_dir), "summary_path": str(Path(output_dir) / "summary.json")}

    def fake_observability(*, pack_dir, output_dir, **kwargs):
        _write_json(Path(output_dir) / "event_schema.json", {"event_types": ["planning.runtime_pack.hit"], "source_label": "explicit_planning_pack"})
        return {"ok": True, "output_dir": str(output_dir), "sample_event_count": 1}

    def fake_build_release_bundle(*, pack_dir, validation_dir, sensitivity_dir, observability_dir, output_dir, **kwargs):
        _write_json(
            Path(output_dir) / "release_bundle_manifest.json",
            {
                "generated_at": "2026-04-08T03:20:00+00:00",
                "pack_dir": str(pack_dir),
                "checks": {
                    "release_readiness_ready": True,
                    "offline_validation_ok": True,
                    "observability_schema_present": True,
                    "sensitivity_clear": True,
                },
                "scope": {"opt_in_only": True, "default_runtime_cutover": False},
                "ready_for_explicit_consumption": True,
            },
        )
        latest_status["bundle_dir"] = str(output_dir)
        latest_status["pack_dir"] = str(pack_dir)
        return {
            "ok": True,
            "output_dir": str(output_dir),
            "manifest_path": str(Path(output_dir) / "release_bundle_manifest.json"),
            "ready_for_explicit_consumption": True,
            "blocking_findings": [],
        }

    def fake_bundle_status(_bundle_dir: str | Path = ""):
        return status_sequence.pop(0)

    monkeypatch.setattr("ops.run_planning_runtime_pack_refresh.export_runtime_pack", fake_export_runtime_pack)
    monkeypatch.setattr("ops.run_planning_runtime_pack_refresh.run_validation", fake_validation)
    monkeypatch.setattr("ops.run_planning_runtime_pack_refresh.audit_pack", fake_sensitivity)
    monkeypatch.setattr("ops.run_planning_runtime_pack_refresh.build_samples", fake_observability)
    monkeypatch.setattr("ops.run_planning_runtime_pack_refresh.build_release_bundle", fake_build_release_bundle)
    monkeypatch.setattr("ops.run_planning_runtime_pack_refresh.planning_runtime_pack_bundle_status", fake_bundle_status)

    payload = refresh_runtime_pack(
        db_path=tmp_path / "evomap.sqlite",
        refresh_root=refresh_root,
        output_root=output_root,
        validation_root=validation_root,
        sensitivity_root=sensitivity_root,
        observability_root=observability_root,
        release_bundle_root=release_root,
        require_consistent=True,
    )

    assert payload["ok"] is True
    assert payload["before_counts"] == {"exported_docs": 100, "exported_atoms": 200}
    assert payload["after_counts"] == {"exported_docs": 116, "exported_atoms": 258}
    assert payload["delta"] == {"exported_docs": 16, "exported_atoms": 58}
    assert payload["ready_bundle_advanced"] is True
    assert payload["release_bundle_manifest"]["ready_for_explicit_consumption"] is True

    pack_dir = Path(payload["pack_dir"])
    assert (pack_dir / "refresh_summary.json").exists()
    assert (pack_dir / "README.md").exists()
