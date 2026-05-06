from __future__ import annotations

import json
from pathlib import Path

from ops.run_openmind_production_regression import (
    PRODUCTION_REGRESSION_BUNDLES,
    build_production_regression_summary,
    write_production_regression_artifacts,
)


def test_build_production_regression_summary_can_skip_execution() -> None:
    summary = build_production_regression_summary(execute=False)

    assert summary["ok"] is True
    assert summary["bundles"] == []
    assert summary["surface_contract"]["automation_kernel"] is True
    assert "/v3/agent/*" in summary["surface_contract"]["retired_control_plane"]


def test_default_bundles_cover_backend_surfaces() -> None:
    bundle_names = [bundle["name"] for bundle in PRODUCTION_REGRESSION_BUNDLES]

    assert bundle_names == [
        "core_runtime_surface",
        "public_mcp_surface",
        "openclaw_stack_surface",
    ]


def test_write_production_regression_artifacts_writes_expected_files(tmp_path: Path) -> None:
    summary = {
        "ok": True,
        "surface_contract": {
            "automation_kernel": True,
            "job_queue": True,
            "observability": True,
            "retired_control_plane": ["/v1/advisor/*", "/v2/advisor/*", "/v3/agent/*"],
        },
        "bundles": [{"name": "bundle-a", "ok": True, "duration_seconds": 1.25}],
    }

    written = write_production_regression_artifacts(summary, tmp_path / "out", "sample")

    assert len(written) == 2
    assert all(path.exists() for path in written)
    payload = json.loads((tmp_path / "out" / "openmind_production_regression_sample.json").read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["surface_contract"]["observability"] is True
