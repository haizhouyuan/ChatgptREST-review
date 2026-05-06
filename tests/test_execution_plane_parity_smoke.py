from __future__ import annotations

from ops.run_execution_plane_parity_smoke import run_smoke


def test_execution_plane_parity_smoke() -> None:
    report = run_smoke()
    assert report["ok"] is True

    expected = report["expected"]
    archive = report["archive_applicability"]
    live = report["live_applicability"]

    for key, value in expected.items():
        assert archive.get(key) == value
        assert live.get(key) == value

    assert report["plane_local"]["archive_source"] == "workflow/closeout"
    assert report["plane_local"]["live_source"] == "controller_lane_wrapper"
