"""Unit tests for ObsidianClient (obsidian_api.py).

Uses responses library to mock HTTP calls to the Local REST API plugin.
Tests cover: ping, list_files, read_file, write_file, search, content_hash,
folder/tag filtering, and error handling.
"""

import os
import unittest
from unittest.mock import patch

import responses

from chatgptrest.integrations.obsidian_api import (
    ObsidianClient,
    ObsidianAPIError,
    ObsidianAuthError,
    ObsidianNotConnected,
)


BASE_URL = "https://127.0.0.1:27124"


class TestObsidianPing(unittest.TestCase):
    """Test connection checking."""

    def test_not_configured(self):
        """Should return False if API key is missing."""
        client = ObsidianClient(api_url=BASE_URL, api_key="")
        self.assertFalse(client.ping())

    @responses.activate
    def test_ping_success(self):
        responses.add(responses.GET, f"{BASE_URL}/", json={"status": "OK"}, status=200)
        client = ObsidianClient(api_url=BASE_URL, api_key="test-key")
        self.assertTrue(client.ping())

    @responses.activate
    def test_ping_auth_failure(self):
        responses.add(responses.GET, f"{BASE_URL}/", status=401)
        client = ObsidianClient(api_url=BASE_URL, api_key="bad-key")
        self.assertFalse(client.ping())


class TestListFiles(unittest.TestCase):
    """Test file listing with filtering."""

    @responses.activate
    def test_list_basic(self):
        """Should return only .md files."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/files",
            json=[{"path": "note.md"}, {"path": "image.png"}, {"path": "dir/deep.md"}],
            status=200,
        )
        client = ObsidianClient(api_url=BASE_URL, api_key="key")
        files = client.list_files()
        self.assertEqual(len(files), 2)
        paths = [f["path"] for f in files]
        self.assertIn("note.md", paths)
        self.assertIn("dir/deep.md", paths)

    @responses.activate
    def test_list_folder_filter(self):
        """Should only return files from configured folders."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/files",
            json=[
                {"path": "Knowledge/arch.md"},
                {"path": "Random/junk.md"},
                {"path": "Knowledge/sub/deep.md"},
            ],
            status=200,
        )
        with patch.dict(os.environ, {"OPENMIND_OBSIDIAN_SYNC_FOLDERS": "Knowledge"}):
            client = ObsidianClient(api_url=BASE_URL, api_key="key")
        files = client.list_files()
        self.assertEqual(len(files), 2)

    @responses.activate
    def test_list_string_format(self):
        """Handle API returning plain string array instead of objects."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/files",
            json=["note.md", "folder/deep.md", "image.png"],
            status=200,
        )
        client = ObsidianClient(api_url=BASE_URL, api_key="key")
        files = client.list_files()
        self.assertEqual(len(files), 2)

    @responses.activate
    def test_list_wrapped_format(self):
        """Handle API returning {"files": [...]} wrapper."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/files",
            json={"files": [{"path": "a.md"}, {"path": "b.md"}]},
            status=200,
        )
        client = ObsidianClient(api_url=BASE_URL, api_key="key")
        files = client.list_files()
        self.assertEqual(len(files), 2)


class TestReadFile(unittest.TestCase):
    """Test file reading."""

    @responses.activate
    def test_read_success(self):
        responses.add(
            responses.GET,
            f"{BASE_URL}/vault/Notes/test.md",
            body="# Hello\nWorld",
            status=200,
        )
        client = ObsidianClient(api_url=BASE_URL, api_key="key")
        content = client.read_file("Notes/test.md")
        self.assertEqual(content, "# Hello\nWorld")

    @responses.activate
    def test_read_not_found(self):
        responses.add(
            responses.GET,
            f"{BASE_URL}/vault/missing.md",
            status=404,
        )
        client = ObsidianClient(api_url=BASE_URL, api_key="key")
        content = client.read_file("missing.md")
        self.assertEqual(content, "")


class TestWriteFile(unittest.TestCase):
    """Test file writing."""

    @responses.activate
    def test_write_create(self):
        responses.add(
            responses.PUT,
            f"{BASE_URL}/vault/Inbox/report.md",
            status=204,
        )
        client = ObsidianClient(api_url=BASE_URL, api_key="key")
        result = client.write_file("Inbox/report.md", "# Report")
        self.assertTrue(result)

    @responses.activate
    def test_write_append(self):
        responses.add(
            responses.POST,
            f"{BASE_URL}/vault/Inbox/log.md",
            status=200,
        )
        client = ObsidianClient(api_url=BASE_URL, api_key="key")
        result = client.write_file("Inbox/log.md", "\n- new entry", append=True)
        self.assertTrue(result)

    @responses.activate
    def test_write_failure(self):
        responses.add(
            responses.PUT,
            f"{BASE_URL}/vault/readonly.md",
            status=400,  # client error (500 triggers retries)
        )
        client = ObsidianClient(api_url=BASE_URL, api_key="key")
        result = client.write_file("readonly.md", "test")
        self.assertFalse(result)


class TestSearch(unittest.TestCase):
    """Test vault search."""

    @responses.activate
    def test_search_results(self):
        responses.add(
            responses.POST,
            f"{BASE_URL}/search/simple/",
            json=[
                {"filename": "arch.md", "matches": [{"match": {"content": "RAG pipeline"}}]},
            ],
            status=200,
        )
        client = ObsidianClient(api_url=BASE_URL, api_key="key")
        results = client.search("RAG")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["filename"], "arch.md")


class TestContentHash(unittest.TestCase):
    """Test content hashing for dedup."""

    def test_deterministic(self):
        h1 = ObsidianClient.content_hash("hello world")
        h2 = ObsidianClient.content_hash("hello world")
        self.assertEqual(h1, h2)

    def test_different_content(self):
        h1 = ObsidianClient.content_hash("hello")
        h2 = ObsidianClient.content_hash("world")
        self.assertNotEqual(h1, h2)


class TestTagFilter(unittest.TestCase):
    """Test tag-based filtering."""

    def test_has_inline_tag(self):
        client = ObsidianClient(api_url=BASE_URL, api_key="key")
        content = "Some note with #openmind tag"
        self.assertTrue(client.has_tag(content, ["openmind"]))

    def test_no_matching_tag(self):
        client = ObsidianClient(api_url=BASE_URL, api_key="key")
        content = "Some random note"
        self.assertFalse(client.has_tag(content, ["openmind"]))

    def test_frontmatter_tag(self):
        client = ObsidianClient(api_url=BASE_URL, api_key="key")
        content = "---\ntags: [openmind, research]\n---\nContent here"
        self.assertTrue(client.has_tag(content, ["openmind"]))

    def test_empty_filter_matches_all(self):
        client = ObsidianClient(api_url=BASE_URL, api_key="key")
        self.assertTrue(client.has_tag("anything", []))


if __name__ == "__main__":
    unittest.main()
