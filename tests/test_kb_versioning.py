"""Tests for KB versioning module."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from chatgptrest.kb.versioning import KBVersionManager, KBVersion


@pytest.fixture
def vm():
    """Create in-memory version manager."""
    return KBVersionManager(":memory:")


def test_create_version(vm):
    """Test creating a new version."""
    v = vm.create_version(
        doc_id="doc_001",
        content="Hello world",
        author="alice",
        change_note="Initial version"
    )
    assert v.doc_id == "doc_001"
    assert v.version == 1
    assert v.content == "Hello world"
    assert v.author == "alice"


def test_create_multiple_versions(vm):
    """Test creating multiple versions increments version number."""
    v1 = vm.create_version("doc_001", "Version 1", "alice")
    v2 = vm.create_version("doc_001", "Version 2", "bob")

    assert v1.version == 1
    assert v2.version == 2
    assert v2.content == "Version 2"


def test_get_version_latest(vm):
    """Test getting latest version."""
    vm.create_version("doc_001", "Content 1", "alice")
    vm.create_version("doc_001", "Content 2", "bob")
    vm.create_version("doc_001", "Content 3", "charlie")

    latest = vm.get_version("doc_001")
    assert latest.version == 3
    assert latest.content == "Content 3"


def test_get_version_specific(vm):
    """Test getting specific version."""
    vm.create_version("doc_001", "Content 1", "alice")
    vm.create_version("doc_001", "Content 2", "bob")

    v1 = vm.get_version("doc_001", version=1)
    assert v1.version == 1
    assert v1.content == "Content 1"


def test_get_version_not_found(vm):
    """Test getting non-existent version returns None."""
    result = vm.get_version("nonexistent")
    assert result is None


def test_list_versions(vm):
    """Test listing all versions."""
    vm.create_version("doc_001", "Content 1", "alice")
    vm.create_version("doc_001", "Content 2", "bob")

    versions = vm.list_versions("doc_001")
    assert len(versions) == 2
    assert versions[0].version == 2  # Newest first
    assert versions[1].version == 1


def test_diff(vm):
    """Test diff between versions."""
    vm.create_version("doc_001", "Line 1\nLine 2\nLine 3", "alice")
    vm.create_version("doc_001", "Line 1\nModified Line 2\nLine 3", "bob")

    diff_text = vm.diff("doc_001", 1, 2)
    assert "Modified Line 2" in diff_text or "Line 2" in diff_text


def test_rollback(vm):
    """Test rollback to previous version."""
    vm.create_version("doc_001", "Original", "alice")
    vm.create_version("doc_001", "Modified", "bob")

    restored = vm.rollback("doc_001", 1)
    assert restored.version == 3
    assert restored.content == "Original"
    assert "Rollback" in restored.change_note


def test_different_documents(vm):
    """Test versions are independent for different documents."""
    vm.create_version("doc_001", "Content A", "alice")
    vm.create_version("doc_002", "Content B", "bob")

    v1 = vm.get_version("doc_001")
    v2 = vm.get_version("doc_002")

    assert v1.content == "Content A"
    assert v2.content == "Content B"
    assert v1.version == 1
    assert v2.version == 1


def test_create_version_is_thread_safe(tmp_path):
    """Version creation should be safe when the same manager is used across threads."""
    vm = KBVersionManager(tmp_path / "kb_versions.db")

    def _create(idx: int) -> int:
        version = vm.create_version(
            "doc_concurrent",
            f"并发内容 {idx}",
            author=f"user_{idx}",
            change_note=f"write {idx}",
        )
        return version.version

    with ThreadPoolExecutor(max_workers=8) as pool:
        versions = sorted(pool.map(_create, range(8)))

    latest = vm.get_version("doc_concurrent")
    all_versions = vm.list_versions("doc_concurrent")

    assert versions == list(range(1, 9))
    assert latest is not None
    assert latest.version == 8
    assert len(all_versions) == 8
