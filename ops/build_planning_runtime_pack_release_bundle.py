#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops.check_planning_runtime_pack_release_readiness import DEFAULT_PACK_ROOT, check_release_readiness

DEFAULT_VALIDATION_ROOT = REPO_ROOT / "artifacts" / "monitor" / "planning_runtime_pack_validation"
DEFAULT_SENSITIVITY_ROOT = REPO_ROOT / "artifacts" / "monitor" / "planning_runtime_pack_sensitivity_audit"
DEFAULT_OBSERVABILITY_ROOT = REPO_ROOT / "artifacts" / "monitor" / "planning_runtime_pack_observability_samples"


def _latest_dir(root: str | Path) -> Path | None:
    base = Path(root)
    if not base.exists():
        return None
    candidates = sorted(path for path in base.iterdir() if path.is_dir())
    return candidates[-1] if candidates else None


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_release_bundle(
    *,
    pack_dir: str | Path,
    validation_dir: str | Path,
    sensitivity_dir: str | Path,
    observability_dir: str | Path,
    output_dir: str | Path,
    max_age_hours: int = 72,
) -> dict[str, Any]:
    pack = Path(pack_dir)
    validation = Path(validation_dir)
    sensitivity = Path(sensitivity_dir)
    observability = Path(observability_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    readiness = check_release_readiness(pack_dir=pack, max_age_hours=max_age_hours)
    validation_summary = _read_json(validation / "summary.json")
    sensitivity_summary = _read_json(sensitivity / "summary.json")
    observability_schema_path = observability / "event_schema.json"
    observability_schema = _read_json(observability_schema_path)

    checks = {
        "release_readiness_ready": bool(readiness["ready"]),
        "offline_validation_ok": bool(validation_summary.get("ok", False)),
        "observability_schema_present": observability_schema_path.exists(),
        "sensitivity_clear": bool(sensitivity_summary.get("ok", False)),
    }
    blocking_findings: list[str] = []
    if not checks["release_readiness_ready"]:
        blocking_findings.append("release_readiness_failed")
    if not checks["offline_validation_ok"]:
        blocking_findings.append("offline_validation_failed")
    if not checks["observability_schema_present"]:
        blocking_findings.append("observability_schema_missing")
    if not checks["sensitivity_clear"]:
        blocking_findings.append("sensitivity_manual_review_required")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pack_dir": str(pack),
        "validation_dir": str(validation),
        "sensitivity_dir": str(sensitivity),
        "observability_dir": str(observability),
        "checks": checks,
        "blocking_findings": blocking_findings,
        "manual_review_required": not checks["sensitivity_clear"],
        "ready_for_explicit_consumption": len(blocking_findings) == 0,
        "validation_summary": validation_summary,
        "sensitivity_summary": sensitivity_summary,
        "observability_summary": {
            "event_types": observability_schema.get("event_types", []),
            "source_label": observability_schema.get("source_label", ""),
        },
        "scope": {
            "opt_in_only": True,
            "default_runtime_cutover": False,
        },
    }

    (out / "release_bundle_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "component_paths.json").write_text(
        json.dumps(
            {
                "pack_dir": str(pack),
                "validation_dir": str(validation),
                "sensitivity_dir": str(sensitivity),
                "observability_dir": str(observability),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out / "rollback_runbook.md").write_text(
        "\n".join(
            [
                "# Planning Runtime Pack Rollback Runbook",
                "",
                "1. Disable the explicit planning runtime pack consumer or clear its pack pointer.",
                "2. Re-point the consumer to the previous approved pack version.",
                "3. Re-run release-readiness validation for the previous pack before re-enabling.",
                "4. Review `blocking_findings` and `sensitivity_summary` before attempting a new promotion.",
                "5. Record the rollback reason and impacted query/doc/atom ids in the incident log.",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (out / "README.md").write_text(
        "\n".join(
            [
                "# Planning Runtime Pack Release Bundle",
                "",
                f"- `pack_dir`: `{pack}`",
                f"- `validation_dir`: `{validation}`",
                f"- `sensitivity_dir`: `{sensitivity}`",
                f"- `observability_dir`: `{observability}`",
                f"- `ready_for_explicit_consumption`: `{manifest['ready_for_explicit_consumption']}`",
                f"- `manual_review_required`: `{manifest['manual_review_required']}`",
                f"- `blocking_findings`: `{', '.join(blocking_findings) if blocking_findings else 'none'}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "output_dir": str(out),
        "manifest_path": str(out / "release_bundle_manifest.json"),
        "ready_for_explicit_consumption": manifest["ready_for_explicit_consumption"],
        "blocking_findings": blocking_findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble a sidecar release bundle for the planning reviewed runtime pack.")
    parser.add_argument("--pack-dir", default="")
    parser.add_argument("--pack-root", default=str(DEFAULT_PACK_ROOT))
    parser.add_argument("--validation-dir", default="")
    parser.add_argument("--validation-root", default=str(DEFAULT_VALIDATION_ROOT))
    parser.add_argument("--sensitivity-dir", default="")
    parser.add_argument("--sensitivity-root", default=str(DEFAULT_SENSITIVITY_ROOT))
    parser.add_argument("--observability-dir", default="")
    parser.add_argument("--observability-root", default=str(DEFAULT_OBSERVABILITY_ROOT))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--max-age-hours", type=int, default=72)
    args = parser.parse_args()

    pack_dir = Path(args.pack_dir) if args.pack_dir else _latest_dir(args.pack_root)
    validation_dir = Path(args.validation_dir) if args.validation_dir else _latest_dir(args.validation_root)
    sensitivity_dir = Path(args.sensitivity_dir) if args.sensitivity_dir else _latest_dir(args.sensitivity_root)
    observability_dir = Path(args.observability_dir) if args.observability_dir else _latest_dir(args.observability_root)
    if pack_dir is None or not pack_dir.exists():
        raise SystemExit("No planning reviewed runtime pack found. Pass --pack-dir explicitly.")
    if validation_dir is None or not validation_dir.exists():
        raise SystemExit("No planning runtime pack validation run found. Pass --validation-dir explicitly.")
    if sensitivity_dir is None or not sensitivity_dir.exists():
        raise SystemExit("No planning runtime pack sensitivity audit found. Pass --sensitivity-dir explicitly.")
    if observability_dir is None or not observability_dir.exists():
        raise SystemExit("No planning runtime pack observability sample run found. Pass --observability-dir explicitly.")

    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else REPO_ROOT / "artifacts" / "monitor" / "planning_runtime_pack_release_bundle" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    print(
        json.dumps(
            build_release_bundle(
                pack_dir=pack_dir,
                validation_dir=validation_dir,
                sensitivity_dir=sensitivity_dir,
                observability_dir=observability_dir,
                output_dir=output_dir,
                max_age_hours=args.max_age_hours,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
