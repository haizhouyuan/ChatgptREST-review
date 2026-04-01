from __future__ import annotations

import json
from pathlib import Path

from ops.run_execution_experience_controller_surfaces_smoke import run_smoke


def test_run_smoke_materializes_controller_surfaces(tmp_path: Path) -> None:
    result = run_smoke(output_dir=tmp_path / "smoke")

    assert result["ok"] is True
    assert result["mode"] == "refresh_merge_only"
    assert result["recommended_action"] == "collect_missing_reviews"
    assert Path(result["paths"]["controller_packet"]).exists()
    assert Path(result["paths"]["controller_action_plan"]).exists()
    assert Path(result["paths"]["review_brief"]).exists()
    assert Path(result["paths"]["review_reply_draft"]).exists()

    written = json.loads(Path(result["summary_path"]).read_text(encoding="utf-8"))
    assert written["reason"] == "review coverage is incomplete"

