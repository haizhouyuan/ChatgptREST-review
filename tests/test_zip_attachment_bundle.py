import zipfile
from pathlib import Path

from chatgptrest.worker.worker import (
    _CHATGPT_MAX_FILES_PER_PROMPT,
    _export_answer_is_connector_tool_call_stub,
    _maybe_bundle_many_attachments_for_chatgpt,
    _maybe_expand_zip_attachments_for_chatgpt,
)


def test_export_answer_is_connector_tool_call_stub_acrobat() -> None:
    text = '{\n  "path": "/Adobe Acrobat/link_deadbeef/document_upload",\n  "args": {}\n}'
    ok, info = _export_answer_is_connector_tool_call_stub(text)
    assert ok is True
    assert info.get("connector") == "Adobe Acrobat"


def test_export_answer_is_connector_tool_call_stub_non_acrobat() -> None:
    text = '{\n  "path": "/Some Other Tool/do",\n  "args": {}\n}'
    ok, info = _export_answer_is_connector_tool_call_stub(text)
    assert ok is False
    assert info == {}


def test_expand_zip_attachments_builds_bundle_and_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CHATGPTREST_EXPAND_ZIP_ATTACHMENTS", "1")

    zip_path = tmp_path / "sample.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("CONTEXT.md", "# Context\n\nhello\n")
        zf.writestr("run/results.json", '{"ok": true}\n')
        zf.writestr("bin.bin", b"\x00\x01\x02")

    new_paths, info = _maybe_expand_zip_attachments_for_chatgpt(
        artifacts_dir=tmp_path,
        job_id="job123",
        file_paths=[zip_path.as_posix()],
    )
    assert isinstance(info, dict) and info.get("ok") is True
    assert zip_path.as_posix() not in new_paths

    manifest = tmp_path / "jobs" / "job123" / "inputs" / "ZIP_MANIFEST.md"
    bundle = tmp_path / "jobs" / "job123" / "inputs" / "ZIP_BUNDLE.md"
    assert manifest.exists()
    assert bundle.exists()

    manifest_text = manifest.read_text(encoding="utf-8", errors="replace")
    bundle_text = bundle.read_text(encoding="utf-8", errors="replace")

    # No absolute path leaks into model-facing manifest.
    assert str(zip_path) not in manifest_text
    assert "sample.zip" in manifest_text

    # Bundle contains text contents.
    assert "CONTEXT.md" in bundle_text
    assert "hello" in bundle_text
    assert "results.json" in bundle_text


def test_bundle_many_chatgpt_attachments_collapses_text_inputs(tmp_path: Path) -> None:
    paths: list[str] = []
    for idx in range(_CHATGPT_MAX_FILES_PER_PROMPT + 6):
        path = tmp_path / f"doc_{idx:02d}.md"
        path.write_text(f"# File {idx}\n\nhello {idx}\n", encoding="utf-8")
        paths.append(path.as_posix())

    new_paths, info = _maybe_bundle_many_attachments_for_chatgpt(
        artifacts_dir=tmp_path,
        job_id="job456",
        file_paths=paths,
    )

    assert isinstance(info, dict) and info.get("ok") is True
    assert len(new_paths) == 2

    bundle = tmp_path / "jobs" / "job456" / "inputs" / "CHATGPT_ATTACH_BUNDLE.md"
    index = tmp_path / "jobs" / "job456" / "inputs" / "CHATGPT_ATTACH_INDEX.md"
    assert bundle.exists()
    assert index.exists()

    bundle_text = bundle.read_text(encoding="utf-8", errors="replace")
    index_text = index.read_text(encoding="utf-8", errors="replace")
    assert "doc_00.md" in bundle_text
    assert f"doc_{_CHATGPT_MAX_FILES_PER_PROMPT + 5:02d}.md" in bundle_text
    assert str(tmp_path) not in index_text
    assert "CHATGPT_ATTACH_BUNDLE.md" in "\n".join(Path(p).name for p in new_paths)
