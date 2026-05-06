from __future__ import annotations

import json
import sys
from pathlib import Path

from ops.run_next_stage_release_gate_pack import run_release_gate_pack


def _write_manifest(path: Path, command_code: str, *, failing: bool = False) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "next-stage-release-gate-pack-v1",
                "description": "test manifest",
                "gates": [
                    {
                        "gate_id": "gate_alpha",
                        "description": "alpha",
                        "commands": [
                            {
                                "label": "alpha_cmd",
                                "argv": [
                                    sys.executable,
                                    "-c",
                                    command_code,
                                ],
                            }
                        ],
                    },
                    {
                        "gate_id": "gate_beta",
                        "description": "beta",
                        "commands": [
                            {
                                "label": "beta_cmd",
                                "argv": [
                                    sys.executable,
                                    "-c",
                                    "import sys; sys.exit(1)" if failing else "print('beta ok')",
                                ],
                            }
                        ],
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_run_release_gate_pack_writes_gate_artifacts_and_summary(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(
        manifest_path,
        "from pathlib import Path; Path(r'{gate_dir}/artifact.txt').write_text('ok', encoding='utf-8'); print('alpha ok')",
        failing=False,
    )

    summary = run_release_gate_pack(manifest_path=manifest_path, output_root=tmp_path / "out", repo_root=tmp_path)

    assert summary["ok"] is True
    assert summary["num_gates"] == 2
    run_dir = Path(summary["run_dir"])
    assert (run_dir / "summary.json").exists()
    assert (run_dir / "summary.md").exists()
    assert (run_dir / "gate_alpha" / "artifact.txt").exists()
    assert (run_dir / "gate_alpha" / "manifest.json").exists()
    assert (run_dir / "gate_beta" / "manifest.json").exists()


def test_run_release_gate_pack_marks_failed_gate_and_keeps_full_report(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(
        manifest_path,
        "print('alpha ok')",
        failing=True,
    )

    summary = run_release_gate_pack(manifest_path=manifest_path, output_root=tmp_path / "out", repo_root=tmp_path)

    assert summary["ok"] is False
    assert summary["num_failed"] == 1
    failed_gate = next(gate for gate in summary["gates"] if gate["gate_id"] == "gate_beta")
    assert failed_gate["passed"] is False
    assert any(command["returncode"] == 1 for command in failed_gate["commands"])
