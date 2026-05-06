from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from ops import watch_github_issue_replies as watcher


def _payload(count: int) -> dict:
    comments = []
    for idx in range(count):
        comments.append(
            {
                "author": {"login": f"user{idx}"},
                "createdAt": f"2026-03-09T10:0{idx}:00Z",
                "url": f"https://github.com/example/issues/110#issuecomment-{idx}",
                "body": f"comment body {idx}",
            }
        )
    return {"number": 110, "title": "Review issue", "url": "https://github.com/example/issues/110", "comments": comments}


def test_default_state_file_uses_repo_slug(tmp_path: Path) -> None:
    path = watcher._default_state_file("haizhouyuan/ChatgptREST", 110, tmp_path)
    assert path == tmp_path / "haizhouyuan__ChatgptREST" / "issue_110.json"


def test_write_and_load_baseline(tmp_path: Path) -> None:
    state_file = tmp_path / "issue.json"
    state = watcher._write_baseline(state_file, "haizhouyuan/ChatgptREST", 110, _payload(3))
    assert state["baseline_comment_count"] == 3
    loaded = watcher._load_state(state_file)
    assert loaded["baseline_comment_count"] == 3
    assert loaded["latest_comment_url"].endswith("#issuecomment-2")


def test_summarize_comment_includes_author_and_url() -> None:
    summary = watcher._summarize_comment(_payload(1)["comments"][0])
    assert "author=user0" in summary
    assert "created_at=2026-03-09T10:00:00Z" in summary
    assert "https://github.com/example/issues/110#issuecomment-0" in summary


def test_build_alert_text_mentions_transition() -> None:
    text = watcher._build_alert_text(_payload(4), 3, 4)
    assert "comments: 3 -> 4" in text
    assert "issue=#110" in text
    assert "latest=author=user3" in text


def test_default_wake_target_prefers_controller_pane(monkeypatch) -> None:
    monkeypatch.setenv("CODEX_CONTROLLER_PANE", "%31")
    monkeypatch.setenv("TMUX_PANE", "%10")
    assert watcher._default_wake_target() == "%31"


def test_default_wake_target_does_not_fallback_to_current_tmux_pane(monkeypatch) -> None:
    monkeypatch.delenv("CODEX_CONTROLLER_PANE", raising=False)
    monkeypatch.setenv("TMUX_PANE", "%10")
    assert watcher._default_wake_target() == ""


def test_build_wake_text_mentions_issue_and_latest_comment() -> None:
    text = watcher._build_wake_text(_payload(4), 3, 4, prefix="Wake now.")
    assert "Wake now." in text
    assert "GitHub issue #110" in text
    assert "comments 3->4" in text
    assert "author=user3" in text
    assert "\n" not in text


def test_wake_tmux_pane_sends_text_waits_and_submits(monkeypatch) -> None:
    calls: list[list[str]] = []
    sleeps: list[float] = []

    def _fake_run(cmd, capture_output, text, check=False):
        calls.append(cmd)
        return Mock(returncode=0, stderr="")

    monkeypatch.setattr(watcher.shutil, "which", lambda name: "/usr/bin/tmux")
    monkeypatch.setattr(watcher.subprocess, "run", _fake_run)
    monkeypatch.setattr(watcher.time, "sleep", lambda seconds: sleeps.append(seconds))
    result = watcher._wake_tmux_pane("%31", "hello", submit_delay_seconds=1.5)
    assert result["ok"] is True
    assert calls[0] == ["tmux", "send-keys", "-t", "%31", "-l", "hello"]
    assert calls[1] == ["tmux", "send-keys", "-t", "%31", "C-m"]
    assert sleeps == [1.5]


def test_initial_wake_on_first_run(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(watcher, "_run_gh_issue_view", lambda repo, issue_number: _payload(2))
    monkeypatch.setattr(
        watcher,
        "_wake_tmux_pane",
        lambda target, text, submit_delay_seconds=2.0: {
            "ok": True,
            "target": target,
            "text": text,
            "submit_delay_seconds": submit_delay_seconds,
        },
    )
    monkeypatch.setattr(watcher, "_default_wake_target", lambda: "%31")
    rc = watcher.main(
        [
            "110",
            "--repo",
            "haizhouyuan/ChatgptREST",
            "--state-dir",
            str(tmp_path),
            "--wake-codex-pane",
            "--wake-current-if-unseen",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert '"initial_wake": true' in out.lower()
    state_file = watcher._default_state_file("haizhouyuan/ChatgptREST", 110, tmp_path)
    state = watcher._load_state(state_file)
    assert state["baseline_comment_count"] == 2
