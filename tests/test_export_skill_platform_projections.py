from __future__ import annotations

import json

from ops.export_skill_platform_projections import export_skill_platform_projections


def test_export_skill_platform_projections_writes_all_frontend_views(tmp_path) -> None:
    written = export_skill_platform_projections(out_dir=tmp_path)

    names = {path.name for path in written}
    assert {
        "openclaw_skill_projection_v1.json",
        "codex_skill_projection_v1.json",
        "claude_code_skill_projection_v1.json",
        "antigravity_skill_projection_v1.json",
    }.issubset(names)

    payload = json.loads((tmp_path / "openclaw_skill_projection_v1.json").read_text(encoding="utf-8"))
    assert payload["adapter"]["projection_mode"] == "agent_bundles_with_runtime_skills"
    assert {item["agent_id"] for item in payload["agents"]} == {"main", "maintagent", "finbot"}
