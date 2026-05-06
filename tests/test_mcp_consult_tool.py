from __future__ import annotations

import asyncio
import importlib
from pathlib import Path


def _load_mcp_server_module():
    import chatgptrest.mcp.server as mod

    return importlib.reload(mod)


def test_chatgptrest_consult_submits_dual_model_jobs_and_persists_record(monkeypatch, tmp_path: Path):
    mod = _load_mcp_server_module()
    created: list[dict[str, object]] = []
    bg_wait_jobs: list[str] = []

    async def fake_job_create(*, idempotency_key, kind, input, params, client, ctx=None):  # noqa: ANN001,ARG001,A002
        created.append(
            {
                "idempotency_key": idempotency_key,
                "kind": kind,
                "input": input,
                "params": params,
                "client": client,
            }
        )
        return {"ok": True, "job_id": f"job-{len(created)}", "kind": kind, "status": "queued"}

    async def fake_background_wait_start(*, job_id, cfg, ctx=None):  # noqa: ANN001,ARG001
        bg_wait_jobs.append(str(job_id))
        return {"watch_id": f"wait-{job_id}"}

    monkeypatch.setattr(mod, "chatgptrest_job_create", fake_job_create)
    monkeypatch.setattr(mod, "_background_wait_start", fake_background_wait_start)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)
    monkeypatch.setattr(mod, "_consult_store_dir", lambda: tmp_path)

    out = asyncio.run(
        mod.chatgptrest_consult(
            question="请给出双模型评审",
            mode="default",
            timeout_seconds=120,
            auto_context=False,
            persist_answer=False,
        )
    )

    assert out["ok"] is True
    assert out["status"] == "submitted"
    assert out["models"] == ["chatgpt_pro", "gemini_deepthink"]
    assert len(created) == 2
    assert [item["kind"] for item in created] == ["chatgpt_web.ask", "gemini_web.ask"]
    assert [item["params"]["preset"] for item in created] == ["pro_extended", "deep_think"]
    assert bg_wait_jobs == ["job-1", "job-2"]
    store_path = tmp_path / f"{out['consultation_id']}.json"
    assert store_path.exists()


def test_chatgptrest_consult_result_reads_persisted_jobs(monkeypatch, tmp_path: Path):
    mod = _load_mcp_server_module()
    monkeypatch.setattr(mod, "_consult_store_dir", lambda: tmp_path)
    monkeypatch.setattr(mod, "_load_config", lambda: type("Cfg", (), {"artifacts_dir": str(tmp_path), "db_path": str(tmp_path / "jobdb.sqlite3")})())

    consultation_id = "cons-test"
    record = {
        "consultation_id": consultation_id,
        "question": "q",
        "models": ["chatgpt_pro"],
        "jobs": [{"model": "chatgpt_pro", "job_id": "job-1", "status": "queued"}],
        "created_at": 1.0,
        "status": "submitted",
    }
    mod._write_consultation_record(consultation_id, record)

    answer_dir = tmp_path / "jobs" / "job-1"
    answer_dir.mkdir(parents=True, exist_ok=True)
    (answer_dir / "answer.md").write_text("final answer", encoding="utf-8")

    class _Status:
        value = "completed"

    class _Job:
        status = _Status()
        answer_path = "jobs/job-1/answer.md"

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(mod, "_db_connect", lambda _path: _Conn())
    monkeypatch.setattr(mod, "_get_job", lambda conn, job_id: _Job())  # noqa: ARG005

    out = asyncio.run(mod.chatgptrest_consult_result(consultation_id))
    assert out["ok"] is True
    assert out["status"] == "completed"
    assert out["all_completed"] is True
    assert out["answers"]["chatgpt_pro"] == "final answer"

