"""
Tests for KB ingestion pipeline (S2).
"""

import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chatgptrest.kb.registry import (
    Artifact,
    ArtifactRegistry,
    ContentType,
    DupStatus,
    PARABucket,
    StructuralRole,
)
from chatgptrest.kb.hub import KBHub
from chatgptrest.kb.scanner import FileScanner, ScanRoot


def test_registry_register_file():
    """Registry: register a real file and retrieve it."""
    print("test_registry_register_file...", end=" ")

    reg = ArtifactRegistry(":memory:")

    # Create a temp file
    with tempfile.NamedTemporaryFile(
        suffix=".md", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write("# Test Document\n\nThis is a test markdown file for KB registry.\n")
        f.flush()
        fpath = f.name

    try:
        art = reg.register_file(
            fpath,
            source_system="manual",
            project_id="test_proj",
            para_bucket="project",
        )
        assert art.artifact_id
        assert art.source_path == str(Path(fpath).resolve())
        assert art.content_type == "markdown"
        assert art.project_id == "test_proj"
        assert art.para_bucket == "project"
        assert art.word_count > 5

        # Re-register same file → should return same artifact (idempotent)
        art2 = reg.register_file(fpath, source_system="manual")
        assert art2.content_hash == art.content_hash
    finally:
        os.unlink(fpath)

    print("PASS ✓")


def test_registry_register_file_computes_quality():
    """Registry: register_file computes and stores quality for runtime callers."""
    reg = ArtifactRegistry(":memory:")

    with tempfile.NamedTemporaryFile(
        suffix=".md", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write("# Decision\n\n" + "structured content " * 20)
        f.flush()
        fpath = f.name

    try:
        art = reg.register_file(
            fpath,
            source_system="manual",
            project_id="test_proj",
            para_bucket="project",
            structural_role="decision",
        )
        stored = reg.get(art.artifact_id)
        assert art.quality_score > 0.0
        assert stored is not None
        assert stored.quality_score == art.quality_score
    finally:
        os.unlink(fpath)


def test_registry_search():
    """Registry: search with filters."""
    print("test_registry_search...", end=" ")

    reg = ArtifactRegistry(":memory:")

    # Register some artifacts directly
    for i in range(5):
        art = Artifact(
            artifact_id=f"art_{i:03d}",
            source_system="test",
            source_path=f"/fake/path/doc_{i}.md",
            content_hash=f"hash_{i:03d}",
            content_type="markdown",
            para_bucket="project" if i < 3 else "resource",
            structural_role="analysis" if i < 2 else "code",
            quality_score=0.5 + i * 0.1,
        )
        reg.register_artifact(art)

    # Search by para_bucket
    projects = reg.search(para_bucket="project")
    assert len(projects) == 3

    resources = reg.search(para_bucket="resource")
    assert len(resources) == 2

    # Search by role
    analysis = reg.search(structural_role="analysis")
    assert len(analysis) == 2

    # Search by quality
    high_q = reg.search(min_quality=0.8)
    assert len(high_q) == 2  # quality 0.8 and 0.9

    print("PASS ✓")


def test_registry_dedup():
    """Registry: exact duplicate detection via content hash."""
    print("test_registry_dedup...", end=" ")

    reg = ArtifactRegistry(":memory:")

    art1 = Artifact(
        artifact_id="dup_1",
        source_path="/path/a/doc.md",
        content_hash="same_hash_123",
    )
    art2 = Artifact(
        artifact_id="dup_2",
        source_path="/path/b/doc_copy.md",
        content_hash="same_hash_123",
    )

    reg.register_artifact(art1)
    reg.register_artifact(art2)

    dups = reg.find_by_hash("same_hash_123")
    assert len(dups) == 2
    assert {d.artifact_id for d in dups} == {"dup_1", "dup_2"}

    print("PASS ✓")


def test_registry_quality_scoring():
    """Registry: quality score computation."""
    print("test_registry_quality_scoring...", end=" ")

    reg = ArtifactRegistry(":memory:")

    # High-quality: manual, recent, structured, markdown, decision
    art = Artifact(
        artifact_id="hq_01",
        source_system="manual",
        source_path="/fake/decision.md",
        content_hash="hq_hash",
        content_type="markdown",
        modified_at=Artifact().modified_at or __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        word_count=200,
        structural_role="decision",
    )

    score = reg.compute_quality(art)
    assert score > 0.7, f"Expected > 0.7, got {score}"

    # Low-quality: agent, old, short, other type, raw role
    from datetime import datetime, timezone, timedelta
    old_date = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
    art_low = Artifact(
        artifact_id="lq_01",
        source_system="unknown-agent",
        source_path="/fake/old_log.txt",
        content_hash="lq_hash",
        content_type="other",
        modified_at=old_date,
        word_count=10,
        structural_role="raw",
    )

    score_low = reg.compute_quality(art_low)
    assert score_low < 0.5, f"Expected < 0.5, got {score_low}"
    assert score_low < score, "Low quality should be lower than high quality"

    print(f"  high={score}, low={score_low} → PASS ✓")


def test_registry_count():
    """Registry: count with filters."""
    print("test_registry_count...", end=" ")

    reg = ArtifactRegistry(":memory:")
    for i in range(10):
        reg.register_artifact(Artifact(
            artifact_id=f"cnt_{i}",
            source_path=f"/fake/cnt_{i}.md",
            content_hash=f"cnt_hash_{i}",
            para_bucket="project" if i % 2 == 0 else "area",
        ))

    assert reg.count() == 10
    assert reg.count(para_bucket="project") == 5
    assert reg.count(para_bucket="area") == 5

    print("PASS ✓")


def test_scanner_backfill():
    """Scanner: backfill scan of a temporary directory."""
    print("test_scanner_backfill...", end=" ")

    reg = ArtifactRegistry(":memory:")

    # Create temp directory with test files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        for i in range(5):
            p = Path(tmpdir) / f"test_{i}.md"
            p.write_text(f"# Test {i}\n\nContent for test document {i}.\n")

        # Create a file that should be excluded
        (Path(tmpdir) / "test.pyc").write_bytes(b"fake bytecode")

        # Create a subdirectory with more files
        subdir = Path(tmpdir) / "sub"
        subdir.mkdir()
        (subdir / "nested.json").write_text('{"key": "value"}')

        # Wait for debounce
        import time
        time.sleep(2.5)

        root = ScanRoot(
            path=tmpdir,
            source_system="test",
            project_id="test_scan",
            para_bucket="project",
            include_extensions=[".md", ".json"],
        )

        scanner = FileScanner(reg, [root], debounce_seconds=2.0)
        stats = scanner.backfill_scan()

        assert stats["total"] == 6, f"Expected 6 files, got {stats['total']}"
        assert stats["new"] == 6
        assert stats["errors"] == 0

        # Re-scan → all should be skipped
        stats2 = scanner.backfill_scan()
        assert stats2["skipped"] == 6
        assert stats2["new"] == 0

    print(f"  {stats} → PASS ✓")


def test_scanner_incremental():
    """Scanner: detect changes since timestamp."""
    print("test_scanner_incremental...", end=" ")

    import time

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create initial files
        (Path(tmpdir) / "old.md").write_text("old content")
        time.sleep(1)
        checkpoint = time.time()
        time.sleep(1)
        (Path(tmpdir) / "new.md").write_text("new content")

        reg = ArtifactRegistry(":memory:")
        root = ScanRoot(
            path=tmpdir,
            include_extensions=[".md"],
        )
        scanner = FileScanner(reg, [root], debounce_seconds=0)

        changed = scanner.detect_changes(root, checkpoint)
        assert len(changed) == 1
        assert changed[0].name == "new.md"

    print("PASS ✓")


def test_kb_hub_version_tracking_is_safe_across_threads(tmp_path, caplog):
    """Concurrent KBHub.index_document calls should not trip version-tracking warnings."""
    hub = KBHub(tmp_path / "kb_search.db")

    def _index(idx: int) -> None:
        hub.index_document(
            artifact_id=f"doc_{idx}",
            title=f"Doc {idx}",
            content=f"并发写入内容 {idx}",
            quality_score=0.9,
        )

    with caplog.at_level("WARNING", logger="chatgptrest.kb.hub"):
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(_index, range(6)))

    warnings = [rec.message for rec in caplog.records if "Version tracking failed" in rec.message]
    assert warnings == []
    assert hub.versions.get_version("doc_0") is not None
    hub.close()


def test_content_type_detection():
    """Content type detection from file extensions."""
    print("test_content_type_detection...", end=" ")

    from chatgptrest.kb.registry import _detect_content_type
    assert _detect_content_type("/foo/bar.md") == "markdown"
    assert _detect_content_type("/foo/bar.json") == "json"
    assert _detect_content_type("/foo/bar.py") == "python"
    assert _detect_content_type("/foo/bar.ts") == "typescript"
    assert _detect_content_type("/foo/bar.xyz") == "other"

    print("PASS ✓")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_registry_register_file,
        test_registry_search,
        test_registry_dedup,
        test_registry_quality_scoring,
        test_registry_count,
        test_scanner_backfill,
        test_scanner_incremental,
        test_content_type_detection,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            import traceback
            print(f"FAIL ✗ → {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*60}")
    sys.exit(1 if failed else 0)
