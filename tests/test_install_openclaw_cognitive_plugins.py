from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "install_openclaw_cognitive_plugins.py"


def test_install_openclaw_cognitive_plugins_symlink_mode(tmp_path) -> None:
    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--target-root",
            str(tmp_path),
            "--plugin",
            "openmind-advisor",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["installed"][0]["id"] == "openmind-advisor"
    target = tmp_path / "openmind-advisor"
    assert target.is_symlink()


def test_install_openclaw_cognitive_plugins_copy_mode_requires_force_for_replace(tmp_path) -> None:
    first = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--target-root",
            str(tmp_path),
            "--plugin",
            "openmind-memory",
            "--copy",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stderr
    assert (tmp_path / "openmind-memory").is_dir()

    second = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--target-root",
            str(tmp_path),
            "--plugin",
            "openmind-memory",
            "--copy",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert second.returncode != 0
    assert "use --force" in second.stderr
