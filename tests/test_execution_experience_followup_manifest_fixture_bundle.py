from __future__ import annotations

import json
from pathlib import Path

from ops.build_execution_experience_followup_manifest import build_manifest


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_experience_followup_manifest_fixture_bundle_20260311")


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _normalize_manifest(payload: dict) -> dict:
    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    normalized["branches"]["accept"]["manifest_path"] = Path(
        str(normalized["branches"]["accept"]["manifest_path"])
    ).name
    normalized["branches"]["accept"]["smoke_manifest_path"] = Path(
        str(normalized["branches"]["accept"]["smoke_manifest_path"])
    ).name
    normalized["branches"]["revise"]["worklist_path"] = Path(str(normalized["branches"]["revise"]["worklist_path"])).name
    normalized["branches"]["revise"]["summary_path"] = Path(str(normalized["branches"]["revise"]["summary_path"])).name
    normalized["branches"]["defer"]["queue_path"] = Path(str(normalized["branches"]["defer"]["queue_path"])).name
    normalized["branches"]["defer"]["summary_path"] = Path(str(normalized["branches"]["defer"]["summary_path"])).name
    normalized["branches"]["reject"]["queue_path"] = Path(str(normalized["branches"]["reject"]["queue_path"])).name
    normalized["branches"]["reject"]["summary_path"] = Path(str(normalized["branches"]["reject"]["summary_path"])).name
    return normalized


def test_execution_experience_followup_manifest_fixture_bundle_matches_expected_output(tmp_path: Path) -> None:
    acceptance_pack = _load_json(FIXTURE_DIR / "acceptance_pack_input_v1.json")
    acceptance_pack["manifest_path"] = str(tmp_path / "accepted_pack" / acceptance_pack["manifest_path"])
    acceptance_pack["smoke_manifest_path"] = str(tmp_path / "accepted_pack" / acceptance_pack["smoke_manifest_path"])

    revision_worklist = _load_json(FIXTURE_DIR / "revision_worklist_input_v1.json")
    revision_worklist["output_tsv"] = str(tmp_path / revision_worklist["output_tsv"])
    revision_worklist["summary_path"] = str(tmp_path / revision_worklist["summary_path"])

    deferred_revisit_queue = _load_json(FIXTURE_DIR / "deferred_revisit_queue_input_v1.json")
    deferred_revisit_queue["output_tsv"] = str(tmp_path / deferred_revisit_queue["output_tsv"])
    deferred_revisit_queue["summary_path"] = str(tmp_path / deferred_revisit_queue["summary_path"])

    rejected_archive_queue = _load_json(FIXTURE_DIR / "rejected_archive_queue_input_v1.json")
    rejected_archive_queue["output_tsv"] = str(tmp_path / rejected_archive_queue["output_tsv"])
    rejected_archive_queue["summary_path"] = str(tmp_path / rejected_archive_queue["summary_path"])

    manifest = build_manifest(
        output_path=tmp_path / "followup_manifest.json",
        acceptance_pack=acceptance_pack,
        revision_worklist=revision_worklist,
        deferred_revisit_queue=deferred_revisit_queue,
        rejected_archive_queue=rejected_archive_queue,
    )

    assert manifest["total_followup_candidates"] == 10
    assert Path(str(manifest["output_path"])).name == "followup_manifest.json"
    assert _normalize_manifest(_load_json(tmp_path / "followup_manifest.json")) == _load_json(
        FIXTURE_DIR / "followup_manifest_v1.json"
    )
    returned_manifest = dict(manifest)
    returned_manifest.pop("output_path", None)
    assert _normalize_manifest(returned_manifest) == _load_json(FIXTURE_DIR / "followup_manifest_v1.json")
