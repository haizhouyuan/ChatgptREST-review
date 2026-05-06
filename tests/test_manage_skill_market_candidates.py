from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_manage_skill_market_candidates_cli_register_and_list(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_SKILL_PLATFORM_DB", str(tmp_path / "skill_platform.db"))

    register = subprocess.run(
        [
            PYTHON,
            "ops/manage_skill_market_candidates.py",
            "register",
            "--skill-id",
            "community-web-search",
            "--source-market",
            "clawhub",
            "--source-uri",
            "https://example.invalid/community-web-search",
            "--capability",
            "web_search",
        ],
        cwd=str(REPO_ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(register.stdout)
    assert payload["skill_id"] == "community-web-search"

    listed = subprocess.run(
        [
            PYTHON,
            "ops/manage_skill_market_candidates.py",
            "list",
            "--capability-id",
            "web_search",
        ],
        cwd=str(REPO_ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    rows = json.loads(listed.stdout)
    assert rows[0]["skill_id"] == "community-web-search"


def test_manage_skill_market_candidates_cli_import_source(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_SKILL_PLATFORM_DB", str(tmp_path / "skill_platform.db"))

    manifest = tmp_path / "market_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "skill_id": "wechat-sender",
                        "source_uri": "https://clawhub.ai/skills/wechat-sender",
                        "capability_ids": ["social_automation"],
                        "summary": "wechat message sender",
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    sources = tmp_path / "skill_market_sources.json"
    sources.write_text(
        json.dumps(
            {
                "authority": {"registry_id": "test", "schema_version": "1.0"},
                "sources": [
                    {
                        "source_id": "curated_market",
                        "enabled": True,
                        "kind": "json_manifest",
                        "source_market": "curated-github",
                        "trust_level": "curated_registry",
                        "manifest_uri": manifest.as_uri(),
                        "allowed_uri_prefixes": ["file://"],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["OPENMIND_SKILL_PLATFORM_DB"] = str(tmp_path / "skill_platform.db")
    env["CHATGPTREST_SKILL_MARKET_SOURCES_PATH"] = str(sources)

    imported = subprocess.run(
        [
            PYTHON,
            "ops/manage_skill_market_candidates.py",
            "import-source",
            "--source-id",
            "curated_market",
        ],
        cwd=str(REPO_ROOT),
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(imported.stdout)
    assert payload["imported_count"] == 1
    assert payload["imported"][0]["skill_id"] == "wechat-sender"
