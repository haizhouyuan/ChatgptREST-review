from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.config import load_config
from chatgptrest.executors.base import ExecutorResult
from chatgptrest.worker import worker as worker_mod
from chatgptrest.worker.worker import _run_once


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"tmp_path": tmp_path, "db_path": db_path, "artifacts_dir": artifacts_dir}


def test_worker_gemini_generate_image_attaches_and_formats_answer(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "gemini_web.generate_image", "input": {"prompt": "a cat"}, "params": {}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "gemini-img-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    src_img = env["tmp_path"] / "source.png"
    src_img.write_bytes(b"fakepng")

    class _StubExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002, ARG002
            assert kind == "gemini_web.generate_image"
            assert input.get("prompt") == "a cat"
            return ExecutorResult(
                status="completed",
                answer="raw",
                answer_format="markdown",
                meta={
                    "conversation_url": "https://gemini.google.com/app/abc123def456",
                    "images": [
                        {
                            "path": str(src_img),
                            "mime_type": "image/png",
                            "bytes": int(src_img.stat().st_size),
                            "width": 1,
                            "height": 1,
                        }
                    ],
                },
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _StubExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert str(job.get("path") or "").endswith("answer.md")

    answer_path = env["artifacts_dir"] / str(job["path"])
    content = answer_path.read_text(encoding="utf-8", errors="replace")
    assert "# Generated images" in content
    assert "![image 1](" in content
    assert "](images/" in content

    img_dir = env["artifacts_dir"] / "jobs" / job_id / "images"
    copied = list(img_dir.glob("*"))
    assert copied, "expected images to be copied under artifacts/jobs/<job_id>/images/"
