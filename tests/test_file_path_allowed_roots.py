from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "0")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"tmp_path": tmp_path}


def _post_with_file(client: TestClient, *, file_path: Path, idem: str):
    return client.post(
        "/v1/jobs",
        json={
            "kind": "dummy.echo",
            "input": {"text": "use attached file", "file_paths": [str(file_path)]},
            "params": {},
        },
        headers={"Idempotency-Key": idem},
    )


def test_arbitrary_tmp_file_paths_are_rejected(env: dict[str, Path]) -> None:
    outside = env["tmp_path"] / "outside.md"
    outside.write_text("not a sanctioned staging path", encoding="utf-8")

    client = TestClient(create_app())
    res = _post_with_file(client, file_path=outside, idem="tmp-file-root-rejected")

    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "file_paths_outside_allowed_directory"
    assert "outside allowed directory" in detail["detail"]
    assert detail["safe_next_action"]


def test_sanctioned_tmp_upload_root_is_allowed(env: dict[str, Path]) -> None:
    root = Path("/tmp/chatgptrest_uploads") / f"test-{env['tmp_path'].name}"
    root.mkdir(parents=True, exist_ok=True)
    file_path = root / "bundle.md"
    file_path.write_text("sanctioned staging path", encoding="utf-8")

    client = TestClient(create_app())
    res = _post_with_file(client, file_path=file_path, idem="tmp-file-root-allowed")

    assert res.status_code == 200
    assert res.json()["kind"] == "dummy.echo"


def test_extra_allowed_file_roots_allow_project_attachments(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = env["tmp_path"] / "project"
    project_root.mkdir(parents=True)
    file_path = project_root / "bundle.md"
    file_path.write_text("project attachment", encoding="utf-8")
    monkeypatch.setenv("CHATGPTREST_EXTRA_ALLOWED_FILE_ROOTS", str(project_root))

    client = TestClient(create_app())
    res = _post_with_file(client, file_path=file_path, idem="extra-file-root-allowed")

    assert res.status_code == 200
    assert res.json()["kind"] == "dummy.echo"
