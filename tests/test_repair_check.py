from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.config import load_config
from chatgptrest.worker.worker import _run_once


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_OPS_TOKEN", "ops-token")
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "200")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def _auth_headers(idempotency_key: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer ops-token",
        "Idempotency-Key": idempotency_key,
    }


def test_repair_check_completes(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    r = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "test"}, "params": {"mode": "quick"}},
        headers=_auth_headers("repair-1"),
    )
    assert r.status_code == 200
    repair_job_id = r.json()["job_id"]

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60))
    assert ran is True

    job = client.get(f"/v1/jobs/{repair_job_id}", headers={"Authorization": "Bearer ops-token"}).json()
    assert job["status"] == "completed"

    ans = client.get(
        f"/v1/jobs/{repair_job_id}/answer?offset=0&max_chars=2000",
        headers={"Authorization": "Bearer ops-token"},
    )
    assert ans.status_code == 200
    chunk = ans.json()["chunk"]
    assert "repair.check report" in chunk

    report_path = env["artifacts_dir"] / "jobs" / repair_job_id / "repair_report.json"
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload.get("repair_job_id") == repair_job_id


def test_repair_check_target_job(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    r1 = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1, "delay_ms": 1}},
        headers=_auth_headers("dummy-1"),
    )
    assert r1.status_code == 200
    target_job_id = r1.json()["job_id"]

    ran1 = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60))
    assert ran1 is True

    r2 = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"job_id": target_job_id}, "params": {"mode": "quick"}},
        headers=_auth_headers("repair-2"),
    )
    assert r2.status_code == 200
    repair_job_id = r2.json()["job_id"]

    ran2 = asyncio.run(_run_once(cfg=load_config(), worker_id="w2", lease_ttl_seconds=60))
    assert ran2 is True

    ans = client.get(
        f"/v1/jobs/{repair_job_id}/answer?offset=0&max_chars=4000",
        headers={"Authorization": "Bearer ops-token"},
    )
    assert ans.status_code == 200
    chunk = ans.json()["chunk"]
    assert target_job_id in chunk


def test_worker_kind_prefix_claims_only_matching_jobs(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    d = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "dummy"}, "params": {"repeat": 1}},
        headers=_auth_headers("dummy-2"),
    )
    assert d.status_code == 200
    dummy_job_id = d.json()["job_id"]

    r = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "test"}, "params": {"mode": "quick"}},
        headers=_auth_headers("repair-3"),
    )
    assert r.status_code == 200
    repair_job_id = r.json()["job_id"]

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w-repair", lease_ttl_seconds=60, kind_prefix="repair."))
    assert ran is True

    repair_job = client.get(f"/v1/jobs/{repair_job_id}", headers={"Authorization": "Bearer ops-token"}).json()
    assert repair_job["status"] == "completed"

    dummy_job = client.get(f"/v1/jobs/{dummy_job_id}", headers={"Authorization": "Bearer ops-token"}).json()
    assert dummy_job["status"] == "queued"


def test_repair_check_reports_gemini_mihomo_probe(monkeypatch: pytest.MonkeyPatch, env: dict[str, Path]) -> None:
    from chatgptrest.executors import repair as repair_mod

    monkeypatch.setenv("CHATGPTREST_GEMINI_MIHOMO_PROXY_GROUP", "💻 Codex")
    monkeypatch.setenv("CHATGPTREST_GEMINI_MIHOMO_CANDIDATES", "🇺🇲 美国 01,🇯🇵 日本 03")
    monkeypatch.setattr(
        repair_mod,
        "_mihomo_get_proxy",
        lambda group, timeout_seconds=5.0: {  # noqa: ARG005
            "ok": True,
            "group": group,
            "now": "🇨🇳 中国 01",
            "all": ["🇺🇲 美国 01", "🇯🇵 日本 03", "🇨🇳 中国 01"],
        },
    )
    monkeypatch.setattr(
        repair_mod,
        "_mihomo_find_connections",
        lambda **kwargs: {  # noqa: ARG005
            "ok": True,
            "matches": [
                {
                    "host": "gemini.google.com",
                    "chains": ["🇨🇳 中国 01", "💻 Codex-AUTO", "💻 Codex"],
                }
            ],
        },
    )

    ex = repair_mod.RepairExecutor(cfg=load_config(), tool_caller=None, tool_caller_init_error=None)
    result = asyncio.run(
        ex.run(
            job_id="repair-gemini-region-1",
            kind="repair.check",
            input={
                "conversation_url": "https://gemini.google.com/app/abc123",
                "symptom": "Gemini is not available in this region.",
            },
            params={"mode": "quick", "probe_driver": False},
        )
    )
    assert result.status == "completed"
    assert result.answer is not None
    assert "Mihomo / Gemini Egress" in result.answer
    assert "Current mihomo selection" in result.answer
