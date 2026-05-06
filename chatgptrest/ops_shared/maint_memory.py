"""Shared maintagent bootstrap memory helpers.

This module turns the external `/vol1/maint` memory packet into compact,
prompt-safe bootstrap memory that can be injected into maint daemon Codex
prompts and SRE lane prompts without copying whole docs into every request.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import json
import os
from typing import Any

from chatgptrest.ops_shared.infra import now_iso, read_json, truncate_text


_REPO_ROOT = Path(__file__).resolve().parents[2]
_BOOTSTRAP_SECTION_TITLE = "## Maintagent Bootstrap Memory"
_REPO_SECTION_TITLE = "## Maintagent Repo Memory"
_DEFAULT_PACKET_GLOB = "maintagent_memory_packet_*.json"
_DEFAULT_PACKET_DIR = Path("/vol1/maint/exports")
_DEFAULT_REPO_MEMORY_DOCS = (
    "docs/contract_v1.md",
    "docs/runbook.md",
    "docs/repair_agent_playbook.md",
    "docs/handoff_chatgptrest_history.md",
    "docs/ops_rollout_plan_p0p1p2_safe_enable_20251228.md",
)
_DEFAULT_REPO_MEMORY_PATHS = (
    "state/jobdb.sqlite3",
    "state/driver/",
    "artifacts/jobs/<job_id>/",
    "artifacts/monitor/",
    "logs/",
)
_DEFAULT_REPO_MEMORY_INVARIANTS = (
    "Clients should call ChatgptREST rather than the raw driver.",
    "Server-side prompt throttling defaults to 61 seconds between sends.",
    "Conversation single-flight is enabled by default for follow-up asks.",
    "repair.autofix must preserve the original conversation and never send a new prompt.",
    "Blocked/cooldown recovery should try guarded low-risk runtime actions before restart-class actions.",
)
_DEFAULT_CODEX_GLOBAL_MEMORY_JSONL = "artifacts/monitor/maint_daemon/codex_global_memory.jsonl"


def _resolve_shared_state_root() -> Path:
    env_raw = str(os.environ.get("CHATGPTREST_SHARED_STATE_ROOT") or "").strip()
    if env_raw:
        return _coerce_path(env_raw)

    git_pointer = _REPO_ROOT / ".git"
    try:
        if git_pointer.is_dir():
            return _REPO_ROOT
        if git_pointer.is_file():
            first_line = git_pointer.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
            if first_line.startswith("gitdir:"):
                raw_gitdir = first_line.split(":", 1)[1].strip()
                gitdir = Path(raw_gitdir)
                if not gitdir.is_absolute():
                    gitdir = (git_pointer.parent / gitdir).resolve(strict=False)
                for candidate in (gitdir, *gitdir.parents):
                    if candidate.name == ".git":
                        return candidate.parent.resolve(strict=False)
    except Exception:
        return _REPO_ROOT
    return _REPO_ROOT


def _parse_iso_ts(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _default_stale_hours() -> int:
    raw = str(os.environ.get("CHATGPTREST_MAINT_BOOTSTRAP_MEMORY_STALE_HOURS") or "").strip()
    try:
        return max(1, int(raw))
    except Exception:
        return 168


def _coerce_path(value: str | Path) -> Path:
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = (_REPO_ROOT / path).resolve(strict=False)
    return path


def _tail_jsonl_records(path: Path, *, max_bytes: int, max_records: int) -> list[dict[str, Any]]:
    if int(max_bytes) <= 0 or int(max_records) <= 0:
        return []
    try:
        if not path.exists():
            return []
    except Exception:
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            end = handle.tell()
            size = min(int(max_bytes), int(end))
            handle.seek(max(0, int(end) - size))
            raw = handle.read()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        text = str(line or "").strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except Exception:
            continue
        if isinstance(payload, dict):
            out.append(payload)
    if len(out) > int(max_records):
        out = out[-int(max_records) :]
    return out


def resolve_maintagent_memory_packet_path(packet_path: str | Path | None = None) -> Path | None:
    raw = str(packet_path or "").strip()
    if raw:
        return _coerce_path(raw)

    for env_name in ("CHATGPTREST_MAINT_BOOTSTRAP_MEMORY_PACKET", "CHATGPTREST_MAINTAGENT_MEMORY_PACKET"):
        env_raw = str(os.environ.get(env_name) or "").strip()
        if env_raw:
            return _coerce_path(env_raw)

    try:
        candidates = sorted(
            _DEFAULT_PACKET_DIR.glob(_DEFAULT_PACKET_GLOB),
            key=lambda path: (path.stat().st_mtime, path.name),
            reverse=True,
        )
    except Exception:
        return None
    return candidates[0] if candidates else None


def resolve_codex_global_memory_jsonl_path(path: str | Path | None = None) -> Path:
    raw = str(path or "").strip() or str(os.environ.get("CHATGPTREST_CODEX_GLOBAL_MEMORY_JSONL") or "").strip()
    if raw:
        return _coerce_path(raw)
    return _coerce_path(_DEFAULT_CODEX_GLOBAL_MEMORY_JSONL)


def _format_mapping(mapping: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in mapping.items():
        if value is None:
            continue
        if isinstance(value, dict):
            nested = ",".join(f"{sub_key}={sub_value}" for sub_key, sub_value in value.items() if sub_value is not None)
            if nested:
                parts.append(f"{key}=({nested})")
            continue
        if isinstance(value, list):
            rendered = ",".join(str(item) for item in value if str(item or "").strip())
            if rendered:
                parts.append(f"{key}={rendered}")
            continue
        rendered = str(value).strip()
        if rendered:
            parts.append(f"{key}={rendered}")
    return ", ".join(parts)


def _render_bootstrap_body(packet: dict[str, Any], *, source_path: Path, stale_after_hours: int) -> tuple[str, dict[str, Any]]:
    generated_at = str(packet.get("generated_at") or "").strip() or None
    packet_dt = _parse_iso_ts(generated_at)
    age_seconds: int | None = None
    stale = False
    if packet_dt is not None:
        age_seconds = max(0, int((datetime.now(UTC) - packet_dt.astimezone(UTC)).total_seconds()))
        stale = age_seconds > int(stale_after_hours) * 3600

    entrypoint = str(packet.get("entrypoint_markdown") or "").strip() or None
    machine_snapshot = str(packet.get("machine_snapshot_markdown") or "").strip() or None
    repo_snapshot = str(packet.get("repo_snapshot_markdown") or "").strip() or None
    highlights = packet.get("highlights") if isinstance(packet.get("highlights"), dict) else {}
    machine = highlights.get("machine") if isinstance(highlights.get("machine"), dict) else {}
    workspace = highlights.get("workspace") if isinstance(highlights.get("workspace"), dict) else {}
    known_drifts = [str(item).strip() for item in packet.get("known_drifts", []) if str(item or "").strip()][:8]
    refresh_triggers = [str(item).strip() for item in packet.get("refresh_triggers", []) if str(item or "").strip()][:8]
    evidence = packet.get("evidence") if isinstance(packet.get("evidence"), dict) else {}
    canonical_docs = [str(item).strip() for item in evidence.get("canonical_docs", []) if str(item or "").strip()][:6]
    snapshots = [str(item).strip() for item in evidence.get("snapshots", []) if str(item or "").strip()][:4]

    lines: list[str] = []
    lines.append(f"- status=`{'stale' if stale else 'loaded'}` source=`{source_path}`")
    if generated_at:
        lines.append(f"- packet_generated_at=`{generated_at}` age_seconds=`{age_seconds if age_seconds is not None else 'unknown'}`")
    purpose = str(packet.get("purpose") or "").strip()
    if purpose:
        lines.append(f"- purpose={truncate_text(purpose, limit=240)}")
    if entrypoint:
        lines.append(f"- entrypoint=`{entrypoint}`")
    if machine_snapshot:
        lines.append(f"- machine_snapshot=`{machine_snapshot}`")
    if repo_snapshot:
        lines.append(f"- repo_snapshot=`{repo_snapshot}`")
    machine_line = _format_mapping(machine)
    if machine_line:
        lines.append(f"- machine_highlights: {truncate_text(machine_line, limit=600)}")
    workspace_line = _format_mapping(workspace)
    if workspace_line:
        lines.append(f"- workspace_highlights: {truncate_text(workspace_line, limit=600)}")
    if known_drifts:
        lines.append("- known_drifts:")
        lines.extend(f"  - {truncate_text(item, limit=240)}" for item in known_drifts)
    if canonical_docs:
        lines.append("- canonical_docs:")
        lines.extend(f"  - `{item}`" for item in canonical_docs)
    if snapshots:
        lines.append("- runtime_snapshots:")
        lines.extend(f"  - `{item}`" for item in snapshots)
    if refresh_triggers:
        lines.append("- refresh_triggers:")
        lines.extend(f"  - {truncate_text(item, limit=180)}" for item in refresh_triggers)
    return (
        "\n".join(lines).strip() + "\n",
        {
            "status": ("stale" if stale else "loaded"),
            "source_path": str(source_path),
            "generated_at": generated_at,
            "age_seconds": age_seconds,
            "stale": stale,
            "entrypoint_markdown": entrypoint,
            "machine_snapshot_markdown": machine_snapshot,
            "repo_snapshot_markdown": repo_snapshot,
        },
    )


def load_maintagent_bootstrap_memory(
    *,
    packet_path: str | Path | None = None,
    max_chars: int = 12_000,
    stale_after_hours: int | None = None,
) -> dict[str, Any]:
    stale_hours = int(stale_after_hours if stale_after_hours is not None else _default_stale_hours())
    source_path = resolve_maintagent_memory_packet_path(packet_path)
    if source_path is None:
        return {"status": "missing", "text": "", "source_path": None, "stale": False, "age_seconds": None}
    if not source_path.exists():
        return {
            "status": "missing",
            "text": f"- status=`missing` source=`{source_path}`\n",
            "source_path": str(source_path),
            "stale": False,
            "age_seconds": None,
        }

    packet = read_json(source_path)
    if not isinstance(packet, dict):
        return {
            "status": "invalid",
            "text": f"- status=`invalid` source=`{source_path}` error=`packet_not_json_object`\n",
            "source_path": str(source_path),
            "stale": False,
            "age_seconds": None,
        }

    body, meta = _render_bootstrap_body(packet, source_path=source_path, stale_after_hours=stale_hours)
    text = body
    if int(max_chars) > 0 and len(text) > int(max_chars):
        text = text[: int(max_chars)] + f"\n...<truncated {len(body) - int(max_chars)} chars>\n"
    meta["text"] = text
    return meta


def load_maintagent_repo_memory(*, max_chars: int = 6000) -> dict[str, Any]:
    shared_state_root = _resolve_shared_state_root()
    canonical_docs = [str((_REPO_ROOT / rel).resolve(strict=False)) for rel in _DEFAULT_REPO_MEMORY_DOCS]
    key_state_paths = [str((shared_state_root / rel).resolve(strict=False)) for rel in _DEFAULT_REPO_MEMORY_PATHS]
    lines = [
        "- status=`loaded` source=`chatgptrest_repo_profile`",
        "- role=REST job queue + worker runtime + web automation driver integration + Advisor v3",
        "- primary_ports: api_v1=`127.0.0.1:18711`, advisor_v3_surface=`127.0.0.1:18711/v2/advisor/*`, mcp_adapter=`127.0.0.1:18712`",
        "- primary_kinds: `chatgpt_web.ask`, `gemini_web.ask`, `repair.check`, `repair.autofix`, `repair.open_pr`, `sre.fix_request`",
        f"- code_checkout=`{_REPO_ROOT.resolve(strict=False)}`",
        f"- shared_state_root=`{shared_state_root}`",
        "- key_state_paths:",
    ]
    lines.extend(f"  - `{item}`" for item in key_state_paths)
    lines.append("- canonical_docs:")
    lines.extend(f"  - `{item}`" for item in canonical_docs)
    lines.append("- operator_invariants:")
    lines.extend(f"  - {item}" for item in _DEFAULT_REPO_MEMORY_INVARIANTS)

    text = "\n".join(lines).strip() + "\n"
    if int(max_chars) > 0 and len(text) > int(max_chars):
        text = text[: int(max_chars)] + f"\n...<truncated {len(text) - int(max_chars)} chars>\n"
    return {
        "status": "loaded",
        "source_path": "chatgptrest_repo_profile",
        "text": text,
        "checkout_root": str(_REPO_ROOT.resolve(strict=False)),
        "shared_state_root": str(shared_state_root),
        "canonical_docs": canonical_docs,
        "key_state_paths": key_state_paths,
    }


def load_maintagent_action_preferences(
    *,
    jsonl_path: str | Path | None = None,
    sig_hash: str | None = None,
    max_records: int = 200,
    max_bytes: int = 2_000_000,
    max_actions: int = 5,
) -> dict[str, Any]:
    resolved = resolve_codex_global_memory_jsonl_path(jsonl_path)
    records = _tail_jsonl_records(resolved, max_bytes=int(max_bytes), max_records=int(max_records))
    target_sig = str(sig_hash or "").strip()
    filtered = [
        record
        for record in records
        if isinstance(record, dict) and (not target_sig or str(record.get("sig_hash") or "").strip() == target_sig)
    ]
    filtered = list(reversed(filtered))
    action_counts: dict[str, int] = {}
    action_reasons: dict[str, str] = {}
    for record in filtered:
        top_actions = record.get("top_actions")
        if not isinstance(top_actions, list):
            continue
        for item in top_actions:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                reason = str(item.get("reason") or "").strip()
            else:
                name = str(item or "").strip()
                reason = ""
            if not name:
                continue
            action_counts[name] = int(action_counts.get(name, 0)) + 1
            if reason and name not in action_reasons:
                action_reasons[name] = truncate_text(reason.replace("\n", " "), limit=240)
    preferred = [
        {
            "name": name,
            "count": count,
            "reason": action_reasons.get(name) or None,
        }
        for name, count in sorted(action_counts.items(), key=lambda item: (-item[1], item[0]))[: int(max_actions)]
    ]
    return {
        "source_path": str(resolved),
        "sig_hash": target_sig or None,
        "matched_records": len(filtered),
        "preferred_actions": preferred,
    }


def merge_maintagent_bootstrap_into_markdown(
    markdown: str,
    *,
    packet_path: str | Path | None = None,
    max_chars: int = 12_000,
    stale_after_hours: int | None = None,
) -> str:
    existing = str(markdown or "")
    repo_payload = load_maintagent_repo_memory(max_chars=min(6000, int(max_chars)))
    repo_body = str(repo_payload.get("text") or "").strip()
    repo_section = ""
    if repo_body and _REPO_SECTION_TITLE not in existing:
        repo_section = f"{_REPO_SECTION_TITLE}\n\n{repo_body}\n"

    bootstrap_body = ""
    if _BOOTSTRAP_SECTION_TITLE not in existing:
        payload = load_maintagent_bootstrap_memory(
            packet_path=packet_path,
            max_chars=max_chars,
            stale_after_hours=stale_after_hours,
        )
        bootstrap_body = str(payload.get("text") or "").strip()

    if not repo_section and not bootstrap_body:
        return existing

    bootstrap_section = f"{_BOOTSTRAP_SECTION_TITLE}\n\n{bootstrap_body}\n" if bootstrap_body else ""
    combined_sections = f"{repo_section}{bootstrap_section}".strip() + "\n"
    if not existing.strip():
        return (
            "# Codex Global Memory (ChatgptREST)\n\n"
            f"Updated: {now_iso()}\n\n"
            f"{combined_sections}"
        )

    marker = "## Known patterns (newest first)"
    if marker in existing:
        head, tail = existing.split(marker, 1)
        return head.rstrip() + "\n\n" + combined_sections + "\n" + marker + tail

    empty_marker = "_empty_"
    if empty_marker in existing:
        head, tail = existing.split(empty_marker, 1)
        return head.rstrip() + "\n\n" + combined_sections + "\n" + empty_marker + tail

    return existing.rstrip() + "\n\n" + combined_sections
