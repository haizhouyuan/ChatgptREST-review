from __future__ import annotations

from ops.run_cc_executor_eventbus_smoke import run_smoke


def test_cc_executor_eventbus_smoke_creates_completed_and_failed_atoms() -> None:
    report = run_smoke()
    assert report["ok"] is True
    assert report["row_count"] == 2

    rows = {row["canonical_question"]: row["applicability"] for row in report["rows"]}
    assert "activity: task.completed" in rows
    assert "activity: task.failed" in rows
    assert rows["activity: task.completed"]["agent"] == "cc_executor"
    assert rows["activity: task.failed"]["agent"] == "cc_executor"
