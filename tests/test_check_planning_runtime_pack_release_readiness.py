from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ops.check_planning_runtime_pack_release_readiness import check_release_readiness


def _write_pack(pack: Path, *, generated_at: str | None = None) -> None:
    pack.mkdir(parents=True, exist_ok=True)
    for name in ["docs.tsv", "atoms.tsv", "retrieval_pack.json", "smoke_manifest.json", "README.md"]:
        (pack / name).write_text("{}\n", encoding="utf-8")
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()
    (pack / "manifest.json").write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "scope": {"opt_in_only": True, "default_runtime_cutover": False},
                "ok": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_check_release_readiness_passes_for_fresh_pack(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    _write_pack(pack)
    result = check_release_readiness(pack_dir=pack, max_age_hours=72)
    assert result["ready"] is True
    assert all(result["checks"].values())


def test_check_release_readiness_flags_stale_pack(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
    _write_pack(pack, generated_at=old_ts)
    result = check_release_readiness(pack_dir=pack, max_age_hours=72)
    assert result["ready"] is False
    assert result["checks"]["freshness_ok"] is False
