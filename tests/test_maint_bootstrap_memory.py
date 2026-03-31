from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from chatgptrest.ops_shared.maint_memory import (
    load_maintagent_action_preferences,
    load_maintagent_bootstrap_memory,
    load_maintagent_repo_memory,
    merge_maintagent_bootstrap_into_markdown,
)


def _write_packet(path: Path) -> Path:
    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "purpose": "Memory-oriented packet for openmind x openclaw maintagent",
        "entrypoint_markdown": "/vol1/maint/docs/2026-03-15_maintagent_memory_index.md",
        "machine_snapshot_markdown": "/vol1/maint/docs/2026-03-15_maintagent_machine_snapshot.md",
        "repo_snapshot_markdown": "/vol1/maint/docs/2026-03-15_maintagent_repo_workspace_snapshot.md",
        "highlights": {
            "machine": {
                "hostname": "YogaS2",
                "memory_live": "30Gi visible (~32GB installed)",
                "root_fs": "/dev/nvme0n1p2 ext4 63G used 85%",
            },
            "workspace": {
                "repo_or_worktree_count": 73,
                "dominant_families": {"ChatgptREST": 26, "homeagent": 20, "codexread": 13},
            },
        },
        "known_drifts": [
            "AGENTS.md still describes memory as 24GB, but live observation shows about 32GB installed.",
            "AGENTS.md says /etc/resolv.conf is managed by Tailscale, but live observation shows custom DNS servers.",
        ],
        "evidence": {
            "canonical_docs": ["/vol1/maint/AGENTS.md", "/vol1/maint/docs/ops_manual.md"],
            "snapshots": ["/vol1/maint/state/agenting_snapshots/20260315_142324/summary.md"],
        },
        "refresh_triggers": ["systemd or Docker service layout changes"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _load_ops_codex_memory_module(repo_root: Path):
    ops_dir = repo_root / "ops"
    sys.path.insert(0, str(ops_dir))
    spec = importlib.util.spec_from_file_location("test_ops_maint_codex_memory", ops_dir / "_maint_codex_memory.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_maintagent_bootstrap_memory_reads_packet(tmp_path: Path, monkeypatch) -> None:
    packet_path = _write_packet(tmp_path / "maintagent_memory_packet_2026-03-15.json")
    monkeypatch.setenv("CHATGPTREST_MAINT_BOOTSTRAP_MEMORY_PACKET", str(packet_path))

    payload = load_maintagent_bootstrap_memory(max_chars=4000)

    assert payload["status"] == "loaded"
    assert payload["source_path"] == str(packet_path)
    assert "YogaS2" in payload["text"]
    assert "repo_or_worktree_count=73" in payload["text"]
    assert "custom DNS servers" in payload["text"]


def test_merge_maintagent_bootstrap_into_markdown_inserts_once(tmp_path: Path, monkeypatch) -> None:
    packet_path = _write_packet(tmp_path / "maintagent_memory_packet_2026-03-15.json")
    monkeypatch.setenv("CHATGPTREST_MAINT_BOOTSTRAP_MEMORY_PACKET", str(packet_path))

    original = (
        "# Codex Global Memory (ChatgptREST)\n\n"
        "Updated: 2026-03-15T12:00:00Z\n\n"
        "## Known patterns (newest first)\n"
        "- `abc123` provider=`chatgpt`\n"
    )
    merged = merge_maintagent_bootstrap_into_markdown(original, max_chars=4000)
    merged_twice = merge_maintagent_bootstrap_into_markdown(merged, max_chars=4000)

    assert "## Maintagent Repo Memory" in merged
    assert "## Maintagent Bootstrap Memory" in merged
    assert merged.index("## Maintagent Bootstrap Memory") < merged.index("## Known patterns (newest first)")
    assert merged == merged_twice


def test_load_maintagent_repo_memory_renders_repo_facts() -> None:
    payload = load_maintagent_repo_memory(max_chars=4000)

    assert payload["status"] == "loaded"
    assert "contract_v1.md" in payload["text"]
    assert "state/jobdb.sqlite3" in payload["text"]
    assert "61 seconds" in payload["text"]
    assert payload["checkout_root"]
    assert payload["shared_state_root"]
    assert payload["shared_state_root"] in payload["text"]
    assert any(path.startswith(payload["shared_state_root"]) for path in payload["key_state_paths"])


def test_ops_snapshot_uses_bootstrap_memory_when_global_digest_missing(tmp_path: Path, monkeypatch) -> None:
    packet_path = _write_packet(tmp_path / "maintagent_memory_packet_2026-03-15.json")
    monkeypatch.setenv("CHATGPTREST_MAINT_BOOTSTRAP_MEMORY_PACKET", str(packet_path))

    repo_root = Path(__file__).resolve().parents[1]
    module = _load_ops_codex_memory_module(repo_root)
    inc_dir = tmp_path / "incident-pack"

    snapshot_path = module._snapshot_codex_global_memory_md(
        global_md=tmp_path / "missing_codex_global_memory.md",
        inc_dir=inc_dir,
        max_chars=4000,
    )

    assert snapshot_path is not None
    text = snapshot_path.read_text(encoding="utf-8")
    assert "## Maintagent Repo Memory" in text
    assert "## Maintagent Bootstrap Memory" in text
    assert "root_fs=/dev/nvme0n1p2 ext4 63G used 85%" in text


def test_load_maintagent_action_preferences_prefers_recent_matching_actions(tmp_path: Path) -> None:
    jsonl_path = tmp_path / "codex_global_memory.jsonl"
    rows = [
        {
            "sig_hash": "sig-1",
            "top_actions": [
                {"name": "restart_driver", "reason": "Driver got stale."},
                {"name": "capture_ui", "reason": "Collect fresh UI evidence."},
            ],
        },
        {
            "sig_hash": "sig-2",
            "top_actions": [{"name": "restart_chrome", "reason": "Other incident."}],
        },
        {
            "sig_hash": "sig-1",
            "top_actions": [{"name": "restart_driver", "reason": "Still the best first action."}],
        },
    ]
    jsonl_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    payload = load_maintagent_action_preferences(jsonl_path=jsonl_path, sig_hash="sig-1")

    assert payload["matched_records"] == 2
    assert payload["preferred_actions"][0]["name"] == "restart_driver"
    assert payload["preferred_actions"][0]["count"] == 2
    assert payload["preferred_actions"][1]["name"] == "capture_ui"
