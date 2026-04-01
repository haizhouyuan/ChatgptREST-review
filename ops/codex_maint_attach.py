#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from chatgptrest.core.codex_runner import _codex_bin


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _coerce_path(value: str | Path) -> Path:
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = (_repo_root() / path).resolve(strict=False)
    return path


def _default_lane_root() -> Path:
    raw = str(os.environ.get("CHATGPTREST_SRE_LANES_ROOT") or "").strip()
    if raw:
        return _coerce_path(raw)
    return (_repo_root() / "state" / "sre_lanes").resolve(strict=False)


def _resolve_lane_dir(*, lane_id: str | None, lane_dir: str | None, incident_dir: str | None) -> tuple[str, Path]:
    if lane_dir:
        resolved = _coerce_path(lane_dir)
        return (str(lane_id or resolved.name).strip() or resolved.name, resolved)
    if lane_id:
        resolved = (_default_lane_root() / str(lane_id).strip()).resolve(strict=False)
        return (str(lane_id).strip(), resolved)
    if incident_dir:
        inc_dir = _coerce_path(incident_dir)
        pointer_path = inc_dir / "codex" / "source_lane.json"
        try:
            payload = json.loads(pointer_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - exercised through CLI failure path
            raise SystemExit(f"source lane pointer missing or invalid: {pointer_path} ({type(exc).__name__}: {exc})")
        source_lane_id = str(payload.get("source_lane_id") or "").strip()
        if not source_lane_id:
            raise SystemExit(f"source lane pointer missing source_lane_id: {pointer_path}")
        return _resolve_lane_dir(lane_id=source_lane_id, lane_dir=None, incident_dir=None)
    raise SystemExit("Provide one of --lane-id, --lane-dir, or --incident-dir")


def build_attach_payload(*, lane_id: str, lane_dir: Path, all_sessions: bool) -> dict[str, object]:
    cmd = [_codex_bin(), "exec", "resume", "--last"]
    if all_sessions:
        cmd.append("--all")
    cmd.extend(["--cd", str(lane_dir)])
    return {
        "lane_id": lane_id,
        "lane_dir": str(lane_dir),
        "cmd": cmd,
        "manifest_path": str((lane_dir / "lane_manifest.json").resolve(strict=False)),
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Attach an operator Codex session to the canonical maintenance lane.")
    ap.add_argument("--lane-id", default="", help="SRE lane id (preferred when known)")
    ap.add_argument("--lane-dir", default="", help="Explicit lane directory")
    ap.add_argument("--incident-dir", default="", help="Incident dir containing codex/source_lane.json")
    ap.add_argument("--all", action="store_true", help="Pass --all to codex exec resume --last")
    ap.add_argument("--json", action="store_true", help="Print the resolved attach payload as JSON and exit")
    args = ap.parse_args(argv)

    lane_id, lane_dir = _resolve_lane_dir(
        lane_id=str(args.lane_id or "").strip() or None,
        lane_dir=str(args.lane_dir or "").strip() or None,
        incident_dir=str(args.incident_dir or "").strip() or None,
    )
    payload = build_attach_payload(lane_id=lane_id, lane_dir=lane_dir, all_sessions=bool(args.all))
    if bool(args.json):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    proc = subprocess.run(payload["cmd"], cwd=str(lane_dir), check=False)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main(list(sys.argv[1:])))
