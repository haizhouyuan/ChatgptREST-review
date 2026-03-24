#!/usr/bin/env python3
"""Install local OpenClaw cognitive-substrate plugins into an OpenClaw extensions dir.

For day-to-day OpenClaw usage, prefer the official CLI:
  openclaw plugins install --link /abs/path/to/plugin
This helper remains useful for offline staging or bulk-copying plugin trees.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "openclaw_extensions"
DEFAULT_TARGET_ROOT = Path.home() / ".openclaw" / "extensions"


def discover_plugins() -> list[str]:
    return sorted(
        path.name
        for path in PLUGIN_ROOT.iterdir()
        if path.is_dir() and (path / "openclaw.plugin.json").is_file()
    )


def load_manifest(plugin_id: str) -> dict:
    return json.loads((PLUGIN_ROOT / plugin_id / "openclaw.plugin.json").read_text(encoding="utf-8"))


def install_plugin(*, plugin_id: str, target_root: Path, copy_mode: bool, force: bool) -> str:
    source = PLUGIN_ROOT / plugin_id
    target = target_root / plugin_id

    if not source.is_dir():
        raise FileNotFoundError(f"plugin source missing: {source}")

    if target.exists() or target.is_symlink():
        if not force:
            raise FileExistsError(f"target already exists: {target} (use --force to replace)")
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)

    target_root.mkdir(parents=True, exist_ok=True)
    if copy_mode:
        shutil.copytree(source, target)
        return "copied"

    os.symlink(source, target, target_is_directory=True)
    return "symlinked"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-root", default=str(DEFAULT_TARGET_ROOT), help="OpenClaw extensions directory.")
    parser.add_argument("--plugin", action="append", dest="plugins", help="Plugin id to install (repeatable). Defaults to all.")
    parser.add_argument("--copy", action="store_true", help="Copy plugin directories instead of symlinking them.")
    parser.add_argument("--force", action="store_true", help="Replace existing plugin directories.")
    parser.add_argument("--print-config", action="store_true", help="Print example OpenClaw config after install.")
    args = parser.parse_args()

    available = discover_plugins()
    selected = args.plugins or available
    unknown = [plugin_id for plugin_id in selected if plugin_id not in available]
    if unknown:
        parser.error(f"unknown plugin ids: {', '.join(unknown)}")

    target_root = Path(args.target_root).expanduser()
    results = []
    for plugin_id in selected:
        manifest = load_manifest(plugin_id)
        mode = install_plugin(
            plugin_id=plugin_id,
            target_root=target_root,
            copy_mode=args.copy,
            force=args.force,
        )
        results.append(
            {
                "id": plugin_id,
                "name": manifest.get("name") or plugin_id,
                "mode": mode,
                "target": str((target_root / plugin_id).resolve()),
            }
        )

    print(json.dumps({"installed": results}, indent=2, ensure_ascii=False))

    if args.print_config:
        print(
            """
Suggested OpenClaw config snippet:

plugins:
  enabled: true
  entries:
    openmind-advisor:
      enabled: true
      config:
        endpoint:
          baseUrl: "http://127.0.0.1:18711"
          apiKey: ""
    openmind-graph:
      enabled: true
      config:
        endpoint:
          baseUrl: "http://127.0.0.1:18711"
          apiKey: ""
        defaultRepo: "ChatgptREST"
    openmind-telemetry:
      enabled: true
      config:
        endpoint:
          baseUrl: "http://127.0.0.1:18711"
          apiKey: ""
    openmind-memory:
      enabled: true
      config:
        endpoint:
          baseUrl: "http://127.0.0.1:18711"
          apiKey: ""
        graphScopes: ["personal", "repo"]
        repo: "ChatgptREST"
  slots:
    memory: "openmind-memory"
""".strip()
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
