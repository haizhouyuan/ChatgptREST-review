"""Phase 12 core ask launch gate."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ReportCheckSpec:
    name: str
    path: str
    min_items: int = 1
    min_cases: int = 0


@dataclass(frozen=True)
class HealthCheckSpec:
    name: str
    url: str
    expected_status: int = 200
    expected_field: str = ""
    expected_value: Any = None


@dataclass
class ReportCheckResult:
    name: str
    path: str
    passed: bool
    num_items: int
    num_failed: int
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HealthCheckResult:
    name: str
    url: str
    passed: bool
    status_code: int
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CoreAskLaunchGateReport:
    overall_passed: bool
    report_checks: list[ReportCheckResult]
    health_checks: list[HealthCheckResult]
    exclusions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_passed": self.overall_passed,
            "report_checks": [item.to_dict() for item in self.report_checks],
            "health_checks": [item.to_dict() for item in self.health_checks],
            "exclusions": list(self.exclusions),
        }


PHASE_REPORT_SPECS: tuple[ReportCheckSpec, ...] = (
    ReportCheckSpec(
        name="phase7_front_door_business_sample_semantics",
        path="docs/dev_log/artifacts/phase7_business_work_sample_validation_20260322/report_v1.json",
        min_items=7,
    ),
    ReportCheckSpec(
        name="phase8_multi_ingress_business_sample_semantics",
        path="docs/dev_log/artifacts/phase8_multi_ingress_work_sample_validation_20260322/report_v2.json",
        min_items=7,
        min_cases=28,
    ),
    ReportCheckSpec(
        name="phase9_agent_v3_public_route_validation",
        path="docs/dev_log/artifacts/phase9_agent_v3_route_work_sample_validation_20260322/report_v1.json",
        min_items=7,
    ),
    ReportCheckSpec(
        name="phase10_controller_pack_route_parity",
        path="docs/dev_log/artifacts/phase10_controller_route_parity_validation_20260322/report_v1.json",
        min_items=5,
    ),
    ReportCheckSpec(
        name="phase11_branch_family_validation",
        path="docs/dev_log/artifacts/phase11_branch_coverage_validation_20260322/report_v1.json",
        min_items=4,
    ),
)


HEALTH_CHECK_SPECS: tuple[HealthCheckSpec, ...] = (
    HealthCheckSpec(
        name="chatgptrest_api_healthz",
        url="http://127.0.0.1:18711/healthz",
        expected_status=200,
        expected_field="ok",
        expected_value=True,
    ),
    HealthCheckSpec(
        name="advisor_health",
        url="http://127.0.0.1:18711/v2/advisor/health",
        expected_status=200,
        expected_field="status",
        expected_value="ok",
    ),
)


DEFAULT_EXCLUSIONS: tuple[str, ...] = (
    "public agent MCP usability gate is not included in Phase 12",
    "strict ChatGPT Pro smoke blocking is not included in Phase 12",
    "OpenClaw dynamic replay is not included in Phase 12",
    "full-stack execution delivery is not included in Phase 12",
)


def run_core_ask_launch_gate(
    *,
    report_specs: tuple[ReportCheckSpec, ...] = PHASE_REPORT_SPECS,
    health_specs: tuple[HealthCheckSpec, ...] = HEALTH_CHECK_SPECS,
    exclusions: tuple[str, ...] = DEFAULT_EXCLUSIONS,
    fetch_json: Callable[[str], tuple[int, dict[str, Any]]] | None = None,
) -> CoreAskLaunchGateReport:
    report_checks = [_validate_report(spec) for spec in report_specs]
    fetcher = fetch_json or _fetch_json
    health_checks = [_validate_health(spec, fetcher=fetcher) for spec in health_specs]
    overall_passed = all(item.passed for item in report_checks) and all(item.passed for item in health_checks)
    return CoreAskLaunchGateReport(
        overall_passed=overall_passed,
        report_checks=report_checks,
        health_checks=health_checks,
        exclusions=list(exclusions),
    )


def render_core_ask_launch_gate_markdown(report: CoreAskLaunchGateReport) -> str:
    lines = [
        "# Core Ask Launch Gate Report",
        "",
        f"- overall_passed: {'yes' if report.overall_passed else 'no'}",
        "",
        "## Report Checks",
        "",
        "| Name | Pass | Items | Failed | Note |",
        "|---|---:|---:|---:|---|",
    ]
    for item in report.report_checks:
        lines.append(
            f"| {_escape(item.name)} | {'yes' if item.passed else 'no'} | {item.num_items} | {item.num_failed} | {_escape(item.note or '-')} |"
        )
    lines.extend(
        [
            "",
            "## Health Checks",
            "",
            "| Name | Pass | Status | Note |",
            "|---|---:|---:|---|",
        ]
    )
    for item in report.health_checks:
        lines.append(
            f"| {_escape(item.name)} | {'yes' if item.passed else 'no'} | {item.status_code} | {_escape(item.note or '-')} |"
        )
    lines.extend(["", "## Explicit Exclusions", ""])
    for entry in report.exclusions:
        lines.append(f"- {entry}")
    lines.append("")
    return "\n".join(lines)


def write_core_ask_launch_gate_report(
    report: CoreAskLaunchGateReport,
    *,
    out_dir: str | Path,
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "report_v1.json"
    md_path = out_path / "report_v1.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_core_ask_launch_gate_markdown(report), encoding="utf-8")
    return json_path, md_path


def _validate_report(spec: ReportCheckSpec) -> ReportCheckResult:
    path = Path(spec.path)
    if not path.exists():
        return ReportCheckResult(
            name=spec.name,
            path=spec.path,
            passed=False,
            num_items=0,
            num_failed=0,
            note="missing report file",
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    num_items = int(payload.get("num_items") or 0)
    num_cases = int(payload.get("num_cases") or 0)
    num_failed = int(payload.get("num_failed") or 0)
    passed = num_failed == 0 and num_items >= spec.min_items and num_cases >= spec.min_cases
    note = ""
    if num_items < spec.min_items:
        note = f"expected at least {spec.min_items} items"
    elif spec.min_cases and num_cases < spec.min_cases:
        note = f"expected at least {spec.min_cases} cases"
    return ReportCheckResult(
        name=spec.name,
        path=spec.path,
        passed=passed,
        num_items=num_items,
        num_failed=num_failed,
        note=note,
    )


def _validate_health(
    spec: HealthCheckSpec,
    *,
    fetcher: Callable[[str], tuple[int, dict[str, Any]]],
) -> HealthCheckResult:
    try:
        status_code, payload = fetcher(spec.url)
    except Exception as exc:  # pragma: no cover - exercised via runtime
        return HealthCheckResult(
            name=spec.name,
            url=spec.url,
            passed=False,
            status_code=0,
            note=str(exc),
        )
    passed = status_code == spec.expected_status
    note = ""
    if spec.expected_field:
        actual = payload.get(spec.expected_field)
        if actual != spec.expected_value:
            passed = False
            note = f"{spec.expected_field}={actual!r}"
    return HealthCheckResult(
        name=spec.name,
        url=spec.url,
        passed=passed,
        status_code=status_code,
        note=note,
    )


def _fetch_json(url: str) -> tuple[int, dict[str, Any]]:
    req = Request(url, method="GET")
    with urlopen(req, timeout=5) as resp:  # noqa: S310
        body = resp.read().decode("utf-8")
        return resp.getcode(), json.loads(body)


def _escape(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
