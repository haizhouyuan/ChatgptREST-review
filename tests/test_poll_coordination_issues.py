from __future__ import annotations

import json
from pathlib import Path

from ops.poll_coordination_issues import (
    CONTROLLER_MARKER,
    IssueSnapshot,
    _is_mainline_comment,
    load_state,
    parse_wake_pane_map,
    poll_once,
    save_state,
)


def test_state_roundtrip(tmp_path: Path):
    state_file = tmp_path / "state.json"
    payload = {"114": {"comments_count": 3, "url": "https://example.test/114"}}
    save_state(state_file, payload)
    assert load_state(state_file) == payload


def test_poll_once_logs_comment_count_change(tmp_path: Path, monkeypatch):
    log_path = tmp_path / "poll.log"
    state = {"114": {"comments_count": 1}}

    def fake_fetch_snapshot(repo: str, issue_number: int) -> IssueSnapshot:
        assert repo == "haizhouyuan/ChatgptREST"
        assert issue_number == 114
        return IssueSnapshot(
            number=114,
            title="coordination",
            url="https://example.test/114",
            comments_count=2,
            latest_comment_url="https://example.test/comment/2",
            latest_comment_author="codex",
            latest_comment_created_at="2026-03-11T12:00:00Z",
            latest_comment_body="new delta from side lane",
        )

    monkeypatch.setattr("ops.poll_coordination_issues.fetch_snapshot", fake_fetch_snapshot)
    next_state = poll_once(
        repo="haizhouyuan/ChatgptREST",
        issues=[114],
        state=state,
        log_path=log_path,
        notify=False,
    )

    assert next_state["114"]["comments_count"] == 2
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert any("Issue #114 comments changed: 1 -> 2" in line for line in lines)
    assert any("new delta from side lane" in line for line in lines)


def test_poll_once_can_wake_codex_pane(tmp_path: Path, monkeypatch):
    log_path = tmp_path / "poll.log"
    state = {"115": {"comments_count": 2}}
    wake_calls: list[tuple[str, str, float]] = []

    def fake_fetch_snapshot(repo: str, issue_number: int) -> IssueSnapshot:
        assert issue_number == 115
        return IssueSnapshot(
            number=115,
            title="execution lane",
            url="https://example.test/115",
            comments_count=3,
            latest_comment_url="https://example.test/comment/3",
            latest_comment_author="mainline-codex",
            latest_comment_created_at="2026-03-11T13:00:00Z",
            latest_comment_body="主线 Codex 下发下一步任务（#115）。\n\nnew instructions for execution lane",
        )

    def fake_wake(target: str, text: str, submit_delay_seconds: float = 2.0) -> dict:
        wake_calls.append((target, text, submit_delay_seconds))
        return {"ok": True, "target": target}

    monkeypatch.setattr("ops.poll_coordination_issues.fetch_snapshot", fake_fetch_snapshot)
    monkeypatch.setattr("ops.poll_coordination_issues._wake_tmux_pane", fake_wake)
    next_state = poll_once(
        repo="haizhouyuan/ChatgptREST",
        issues=[115],
        state=state,
        log_path=log_path,
        notify=False,
        wake_codex_pane=True,
        wake_pane_target="%44",
        controller_pane_target="%12",
        wake_prefix="Wake now.",
        wake_submit_delay_seconds=1.25,
    )

    assert next_state["115"]["comments_count"] == 3
    assert wake_calls == [
        (
            "%44",
            "Wake now. | GitHub issue #115 has a new reply in haizhouyuan/ChatgptREST | comments 2->3 | url=https://example.test/115 | latest=author=mainline-codex | created_at=2026-03-11T13:00:00Z | url=https://example.test/comment/3 | body=主线 Codex 下发下一步任务（#115）。 new instructions for execution lane | Read the latest comment, summarize the delta, and continue the workstream immediately.",
            1.25,
        )
    ]
    assert "wake=" in log_path.read_text(encoding="utf-8")


def test_poll_once_prefers_issue_specific_wake_target(tmp_path: Path, monkeypatch):
    log_path = tmp_path / "poll.log"
    state = {"114": {"comments_count": 4}}
    wake_calls: list[str] = []

    def fake_fetch_snapshot(repo: str, issue_number: int) -> IssueSnapshot:
        return IssueSnapshot(
            number=114,
            title="planning lane",
            url="https://example.test/114",
            comments_count=5,
            latest_comment_url="https://example.test/comment/5",
            latest_comment_author="mainline-codex",
            latest_comment_created_at="2026-03-11T13:30:00Z",
            latest_comment_body="主线 Codex 下发下一步任务（#114）。\n\nupdated planning boundary",
        )

    def fake_wake(target: str, text: str, submit_delay_seconds: float = 2.0) -> dict:
        wake_calls.append(target)
        return {"ok": True, "target": target}

    monkeypatch.setattr("ops.poll_coordination_issues.fetch_snapshot", fake_fetch_snapshot)
    monkeypatch.setattr("ops.poll_coordination_issues._wake_tmux_pane", fake_wake)
    poll_once(
        repo="haizhouyuan/ChatgptREST",
        issues=[114],
        state=state,
        log_path=log_path,
        notify=False,
        wake_codex_pane=True,
        wake_pane_target="%44",
        wake_pane_map={114: "%31"},
    )

    assert wake_calls == ["%31"]


def test_poll_once_routes_mainline_status_update_to_issue_pane(tmp_path: Path, monkeypatch):
    log_path = tmp_path / "poll.log"
    state = {"115": {"comments_count": 59}}
    wake_calls: list[str] = []

    def fake_fetch_snapshot(repo: str, issue_number: int) -> IssueSnapshot:
        return IssueSnapshot(
            number=115,
            title="execution lane",
            url="https://example.test/115",
            comments_count=60,
            latest_comment_url="https://example.test/comment/60",
            latest_comment_author="haizhouyuan",
            latest_comment_created_at="2026-03-11T09:14:59Z",
            latest_comment_body="主线已补上 `72ee929` `feat: add execution experience controller packet`。\n\n下一条批准的窄 slice 只做 controller-packet fixture bundle。",
        )

    def fake_wake(target: str, text: str, submit_delay_seconds: float = 2.0) -> dict:
        wake_calls.append(target)
        return {"ok": True, "target": target}

    monkeypatch.setattr("ops.poll_coordination_issues.fetch_snapshot", fake_fetch_snapshot)
    monkeypatch.setattr("ops.poll_coordination_issues._wake_tmux_pane", fake_wake)
    poll_once(
        repo="haizhouyuan/ChatgptREST",
        issues=[115],
        state=state,
        log_path=log_path,
        notify=False,
        wake_codex_pane=True,
        controller_pane_target="%48",
        wake_pane_map={115: "%32"},
    )

    assert wake_calls == ["%32"]


def test_poll_once_routes_controller_absorb_reply_to_issue_pane(tmp_path: Path, monkeypatch):
    log_path = tmp_path / "poll.log"
    state = {"114": {"comments_count": 41}}
    wake_calls: list[str] = []

    def fake_fetch_snapshot(repo: str, issue_number: int) -> IssueSnapshot:
        return IssueSnapshot(
            number=114,
            title="planning lane",
            url="https://example.test/114",
            comments_count=42,
            latest_comment_url="https://example.test/comment/42",
            latest_comment_author="haizhouyuan",
            latest_comment_created_at="2026-03-11T09:19:33Z",
            latest_comment_body="收到。你这条更像是上线前可能需要的准备项盘点，不是 `#114` 当前边界内的继续执行任务。",
        )

    def fake_wake(target: str, text: str, submit_delay_seconds: float = 2.0) -> dict:
        wake_calls.append(target)
        return {"ok": True, "target": target}

    monkeypatch.setattr("ops.poll_coordination_issues.fetch_snapshot", fake_fetch_snapshot)
    monkeypatch.setattr("ops.poll_coordination_issues._wake_tmux_pane", fake_wake)
    poll_once(
        repo="haizhouyuan/ChatgptREST",
        issues=[114],
        state=state,
        log_path=log_path,
        notify=False,
        wake_codex_pane=True,
        controller_pane_target="%48",
        wake_pane_map={114: "%31"},
    )

    assert wake_calls == ["%31"]


def test_poll_once_routes_side_lane_received_reply_back_to_controller(tmp_path: Path, monkeypatch):
    log_path = tmp_path / "poll.log"
    state = {"115": {"comments_count": 40}}
    wake_calls: list[str] = []

    def fake_fetch_snapshot(repo: str, issue_number: int) -> IssueSnapshot:
        return IssueSnapshot(
            number=115,
            title="execution lane",
            url="https://example.test/115",
            comments_count=41,
            latest_comment_url="https://example.test/comment/41",
            latest_comment_author="haizhouyuan",
            latest_comment_created_at="2026-03-11T08:22:56Z",
            latest_comment_body="收到这条校正。 我这边不再把 validator alias 当成主线待办源问题；上一轮提到的 shim 只视为局部兼容处理。",
        )

    def fake_wake(target: str, text: str, submit_delay_seconds: float = 2.0) -> dict:
        wake_calls.append(target)
        return {"ok": True, "target": target}

    monkeypatch.setattr("ops.poll_coordination_issues.fetch_snapshot", fake_fetch_snapshot)
    monkeypatch.setattr("ops.poll_coordination_issues._wake_tmux_pane", fake_wake)
    poll_once(
        repo="haizhouyuan/ChatgptREST",
        issues=[115],
        state=state,
        log_path=log_path,
        notify=False,
        wake_codex_pane=True,
        controller_pane_target="%48",
        wake_pane_map={115: "%32"},
    )

    assert wake_calls == ["%48"]


def test_poll_once_routes_side_lane_reply_back_to_controller(tmp_path: Path, monkeypatch):
    log_path = tmp_path / "poll.log"
    state = {"115": {"comments_count": 5}}
    wake_calls: list[str] = []

    def fake_fetch_snapshot(repo: str, issue_number: int) -> IssueSnapshot:
        return IssueSnapshot(
            number=115,
            title="execution lane",
            url="https://example.test/115",
            comments_count=6,
            latest_comment_url="https://example.test/comment/6",
            latest_comment_author="haizhouyuan",
            latest_comment_created_at="2026-03-11T14:00:00Z",
            latest_comment_body="这轮已经完成并提交 1553436，产出 capability matrix。",
        )

    def fake_wake(target: str, text: str, submit_delay_seconds: float = 2.0) -> dict:
        wake_calls.append(target)
        return {"ok": True, "target": target}

    monkeypatch.setattr("ops.poll_coordination_issues.fetch_snapshot", fake_fetch_snapshot)
    monkeypatch.setattr("ops.poll_coordination_issues._wake_tmux_pane", fake_wake)
    poll_once(
        repo="haizhouyuan/ChatgptREST",
        issues=[115],
        state=state,
        log_path=log_path,
        notify=False,
        wake_codex_pane=True,
        controller_pane_target="%12",
        wake_pane_map={115: "%32"},
    )

    assert wake_calls == ["%12"]


def test_parse_wake_pane_map() -> None:
    assert parse_wake_pane_map(["114=%31", "115=%32"]) == {114: "%31", 115: "%32"}


def test_is_mainline_comment_matches_leading_mainline_line() -> None:
    assert _is_mainline_comment("主线 Codex 下发下一步任务")
    assert _is_mainline_comment("主线已补上 `72ee929` `feat: add execution experience controller packet`")
    assert _is_mainline_comment("\n\n主线这边继续推进 review-plane")
    assert _is_mainline_comment("收到。你这条更像是上线前可能需要的准备项盘点。")
    assert _is_mainline_comment("收到，这轮 `8c5820c` 我已经吸收：validation-failure fixture bundle 已完成并 parked。")
    assert _is_mainline_comment("收到，这个澄清是有必要的。我的理解与你这条一致：\n- `#114` 继续 parked")
    assert _is_mainline_comment(f"协调吸收说明。\n\n{CONTROLLER_MARKER}")
    assert not _is_mainline_comment("这轮对主线 Codex 的 delta 我已经吸收")
    assert not _is_mainline_comment("收到这条校正。 我这边不再把 validator alias 当成主线待办源问题。")
    assert not _is_mainline_comment("education codex\n\n按主线刚批准的新 slice，我只做 fixture bundle")


def test_load_state_ignores_invalid_json(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{bad", encoding="utf-8")
    assert load_state(state_file) == {}
