from __future__ import annotations

import json
from pathlib import Path


def _write_sources(path: Path, manifest_uri: str) -> None:
    path.write_text(
        json.dumps(
            {
                "authority": {"registry_id": "test", "schema_version": "1.0"},
                "sources": [
                    {
                        "source_id": "official_registry",
                        "enabled": True,
                        "kind": "json_manifest",
                        "source_market": "openclaw-official",
                        "trust_level": "official_registry",
                        "manifest_uri": manifest_uri,
                        "allowed_uri_prefixes": ["file://"],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "skill_id": "wechat-article-forge",
                        "source_uri": "https://clawhub.ai/skills/wechat-article-forge",
                        "capability_ids": ["publish_distribution", "social_automation"],
                        "summary": "wechat article drafting and publish flow",
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_import_market_source_registers_and_dedupes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_SKILL_PLATFORM_DB", str(tmp_path / "skill_platform.db"))

    manifest = tmp_path / "market_manifest.json"
    _write_manifest(manifest)
    sources = tmp_path / "skill_market_sources.json"
    _write_sources(sources, manifest.as_uri())

    from ops.import_skill_market_candidates import import_market_source

    first = import_market_source("official_registry", policy_path=str(sources))
    second = import_market_source("official_registry", policy_path=str(sources))

    assert first["imported_count"] == 1
    assert first["imported"][0]["skill_id"] == "wechat-article-forge"
    assert first["imported"][0]["source_market"] == "openclaw-official"
    assert first["imported"][0]["evidence"]["source_id"] == "official_registry"
    assert second["imported_count"] == 0
    assert second["skipped_existing_count"] == 1
