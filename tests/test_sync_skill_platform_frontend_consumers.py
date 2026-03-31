from __future__ import annotations

import json

from ops.sync_skill_platform_frontend_consumers import (
    MANIFEST_NAME,
    inspect_frontend_skill_platform_consumers,
    sync_frontend_skill_platform_consumers,
)


def test_sync_frontend_skill_platform_consumers_writes_runtime_manifests(
    monkeypatch,
    tmp_path,
) -> None:
    codex_dir = tmp_path / "codex"
    claude_dir = tmp_path / "claude"
    antigravity_dir = tmp_path / "antigravity"

    monkeypatch.setenv("CHATGPTREST_CODEX_SKILL_CONSUMER_TARGETS", str(codex_dir))
    monkeypatch.setenv("CHATGPTREST_CLAUDE_CODE_SKILL_CONSUMER_TARGETS", str(claude_dir))
    monkeypatch.setenv("CHATGPTREST_ANTIGRAVITY_SKILL_CONSUMER_TARGETS", str(antigravity_dir))

    written = sync_frontend_skill_platform_consumers()
    assert {row["platform"] for row in written} == {"codex", "claude_code", "antigravity"}

    codex_manifest = json.loads((codex_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert codex_manifest["platform"] == "codex"
    assert codex_manifest["projection_file"] == "codex_skill_projection_v1.json"
    assert codex_manifest["skill_count"] > 0

    status_rows = inspect_frontend_skill_platform_consumers()
    assert {row["status"] for row in status_rows} == {"ok"}


def test_sync_frontend_skill_platform_consumers_reports_stale_projection(
    monkeypatch,
    tmp_path,
) -> None:
    codex_dir = tmp_path / "codex"
    monkeypatch.setenv("CHATGPTREST_CODEX_SKILL_CONSUMER_TARGETS", str(codex_dir))
    monkeypatch.setenv("CHATGPTREST_CLAUDE_CODE_SKILL_CONSUMER_TARGETS", "")
    monkeypatch.setenv("CHATGPTREST_ANTIGRAVITY_SKILL_CONSUMER_TARGETS", "")

    sync_frontend_skill_platform_consumers(platforms=["codex"])
    projection_path = codex_dir / "codex_skill_projection_v1.json"
    payload = json.loads(projection_path.read_text(encoding="utf-8"))
    payload["skills"] = []
    projection_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    [row] = inspect_frontend_skill_platform_consumers(platforms=["codex"])
    assert row["status"] == "stale"
    assert row["exists"] is True
