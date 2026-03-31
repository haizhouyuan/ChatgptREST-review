from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chatgptrest.api.routes_dashboard import make_dashboard_router
from chatgptrest.core.config import load_config
from chatgptrest.dashboard.shared_cognition_scoreboard import build_shared_cognition_status_board
from ops.run_skill_market_candidate_lifecycle_validation import run_skill_market_candidate_lifecycle_validation
from ops.sync_skill_platform_frontend_consumers import sync_frontend_skill_platform_consumers


def _write_multi_ingress_report(artifact_root: Path) -> Path:
    out_dir = artifact_root / "phase8_multi_ingress_work_sample_validation_20260328"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report_v1.json"
    report_path.write_text(
        json.dumps(
            {
                "dataset_name": "phase8_multi_ingress_work_samples_v1",
                "num_items": 7,
                "num_cases": 28,
                "num_passed": 28,
                "num_failed": 0,
                "results": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return report_path


def _write_four_terminal_report(artifact_root: Path, *, prefix: str) -> Path:
    out_dir = artifact_root / f"{prefix}20260329"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report_v1.json"
    report_path.write_text(
        json.dumps(
            {
                "summary": "four_terminal_acceptance_green",
                "checks": {
                    "all_terminals_green": True,
                    "codex_green": True,
                    "claude_code_green": True,
                    "openclaw_green": True,
                    "antigravity_green": True,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return report_path


def test_build_shared_cognition_status_board_reports_owner_scope_ready(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    _write_multi_ingress_report(artifact_root)

    codex_dir = tmp_path / "codex"
    claude_dir = tmp_path / "claude"
    antigravity_dir = tmp_path / "antigravity"
    monkeypatch.setenv("CHATGPTREST_CODEX_SKILL_CONSUMER_TARGETS", str(codex_dir))
    monkeypatch.setenv("CHATGPTREST_CLAUDE_CODE_SKILL_CONSUMER_TARGETS", str(claude_dir))
    monkeypatch.setenv("CHATGPTREST_ANTIGRAVITY_SKILL_CONSUMER_TARGETS", str(antigravity_dir))
    sync_frontend_skill_platform_consumers()

    db_path = tmp_path / "skill_platform.db"
    evomap_db_path = tmp_path / "evomap.db"
    monkeypatch.setenv("OPENMIND_SKILL_PLATFORM_DB", str(db_path))
    monkeypatch.setenv("OPENMIND_EVOMAP_DB", str(evomap_db_path))
    run_skill_market_candidate_lifecycle_validation(
        out_dir=artifact_root / "skill_market_candidate_lifecycle_validation_20260328",
        db_path=db_path,
        evomap_db_path=evomap_db_path,
    )

    monkeypatch.setenv("CHATGPTREST_SHARED_COGNITION_ARTIFACT_ROOT", str(artifact_root))
    board = build_shared_cognition_status_board()

    shared = board["shared_cognition"]
    assert shared["semantic_validation"]["status"] == "ok"
    assert shared["skill_platform_runtime_consumers"]["status"] == "ok"
    assert shared["market_candidate_runtime"]["status"] == "ok"
    assert shared["owner_scope_ready"] is True
    assert shared["system_scope_ready"] is False
    assert shared["remaining_blockers"] == ["four_terminal_live_acceptance_pending"]


def test_dashboard_status_api_surfaces_shared_cognition_board(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    _write_multi_ingress_report(artifact_root)
    monkeypatch.setenv("CHATGPTREST_SHARED_COGNITION_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("CHATGPTREST_CODEX_SKILL_CONSUMER_TARGETS", str(tmp_path / "codex"))
    monkeypatch.setenv("CHATGPTREST_CLAUDE_CODE_SKILL_CONSUMER_TARGETS", str(tmp_path / "claude"))
    monkeypatch.setenv("CHATGPTREST_ANTIGRAVITY_SKILL_CONSUMER_TARGETS", str(tmp_path / "antigravity"))
    sync_frontend_skill_platform_consumers()

    app = FastAPI()
    app.include_router(make_dashboard_router(load_config(), service=object()))
    client = TestClient(app)

    response = client.get("/v2/dashboard/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["refresh_status"] == "ok"
    assert "shared_cognition" in payload
    assert payload["shared_cognition"]["semantic_validation"]["status"] == "ok"


def test_build_shared_cognition_status_board_accepts_new_four_terminal_prefix(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    _write_multi_ingress_report(artifact_root)
    _write_four_terminal_report(artifact_root, prefix="four_terminal_live_acceptance_")

    codex_dir = tmp_path / "codex"
    claude_dir = tmp_path / "claude"
    antigravity_dir = tmp_path / "antigravity"
    monkeypatch.setenv("CHATGPTREST_CODEX_SKILL_CONSUMER_TARGETS", str(codex_dir))
    monkeypatch.setenv("CHATGPTREST_CLAUDE_CODE_SKILL_CONSUMER_TARGETS", str(claude_dir))
    monkeypatch.setenv("CHATGPTREST_ANTIGRAVITY_SKILL_CONSUMER_TARGETS", str(antigravity_dir))
    sync_frontend_skill_platform_consumers()

    db_path = tmp_path / "skill_platform.db"
    evomap_db_path = tmp_path / "evomap.db"
    monkeypatch.setenv("OPENMIND_SKILL_PLATFORM_DB", str(db_path))
    monkeypatch.setenv("OPENMIND_EVOMAP_DB", str(evomap_db_path))
    run_skill_market_candidate_lifecycle_validation(
        out_dir=artifact_root / "skill_market_candidate_lifecycle_validation_20260328",
        db_path=db_path,
        evomap_db_path=evomap_db_path,
    )

    monkeypatch.setenv("CHATGPTREST_SHARED_COGNITION_ARTIFACT_ROOT", str(artifact_root))
    board = build_shared_cognition_status_board()

    shared = board["shared_cognition"]
    assert shared["four_terminal_acceptance"]["status"] == "ok"
    assert shared["system_scope_ready"] is True
    assert shared["remaining_blockers"] == []
