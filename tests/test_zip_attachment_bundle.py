import zipfile
from pathlib import Path

from chatgptrest.worker.worker import _export_answer_is_connector_tool_call_stub, _maybe_expand_zip_attachments_for_chatgpt


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
