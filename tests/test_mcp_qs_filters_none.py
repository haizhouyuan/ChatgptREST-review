from __future__ import annotations

import urllib.parse

from chatgptrest.mcp import server


def test_qs_filters_none_values() -> None:
    qs = server._qs(
        {
            "status": None,
            "kind_prefix": None,
            "phase": "send",
            "before_ts": None,
            "before_job_id": None,
            "limit": 20,
        }
    )
    assert "None" not in qs
    parsed = urllib.parse.parse_qs(qs, keep_blank_values=True)
    assert "status" not in parsed
    assert "kind_prefix" not in parsed
    assert "before_ts" not in parsed
    assert "before_job_id" not in parsed
    assert parsed["phase"] == ["send"]
    assert parsed["limit"] == ["20"]

