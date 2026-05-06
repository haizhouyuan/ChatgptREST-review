#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_HOME = Path("/home/yuanhaizhou")
OFFICIAL_HOME = Path("/home/yuanhaizhou/.home-codex-official")
OFFICIAL_CODEX_DIR = Path("/vol1/1000/home-yuanhaizhou/.codex1")
CODEX_HOME_DIR = Path("/vol1/1000/home-yuanhaizhou/.codex2")
ARTIFACTS_ROOT = REPO_ROOT / "artifacts" / "subagent_smoke"
CODEX_BIN = "/home/yuanhaizhou/.local/bin/codex-official"
TIMEOUT_SECONDS = 360


@dataclass(frozen=True)
class HomeTarget:
    name: str
    home: Path
    codex_home: Path | None


@dataclass
class RunResult:
    home: str
    test: str
    ok: bool
    rc: int
    duration_sec: float
    spawn_count: int
    wait_count: int
    final_message: str
    notes: list[str]
    jsonl_path: str
    stderr_path: str


def _home_env(target: HomeTarget) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(target.home)
    if target.codex_home is not None:
        env["CODEX_HOME"] = str(target.codex_home)
    else:
        implicit_codex_home = target.home / ".codex"
        if implicit_codex_home.is_dir():
            env["CODEX_HOME"] = str(implicit_codex_home)
        else:
            env.pop("CODEX_HOME", None)
    env["NO_COLOR"] = "1"
    return env


def _coerce_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _run_codex(target: HomeTarget, prompt: str, jsonl_path: Path, stderr_path: Path) -> tuple[int, float]:
    cmd = [
        CODEX_BIN,
        "exec",
        "--json",
        "--color",
        "never",
        "--ephemeral",
        "--skip-git-repo-check",
        "-C",
        str(REPO_ROOT),
        "-",
    ]
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            capture_output=True,
            env=_home_env(target),
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
        duration = time.time() - started
        jsonl_path.write_text(proc.stdout or "", encoding="utf-8")
        stderr_path.write_text(proc.stderr or "", encoding="utf-8")
        return proc.returncode, duration
    except subprocess.TimeoutExpired as exc:
        duration = time.time() - started
        stdout = _coerce_text(exc.stdout)
        stderr = _coerce_text(exc.stderr)
        jsonl_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        return 124, duration


def _parse_events(jsonl_path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not jsonl_path.exists():
        return events
    for raw in jsonl_path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            events.append(json.loads(raw))
        except Exception:
            continue
    return events


def _spawn_count(events: list[dict[str, Any]]) -> int:
    count = 0
    for ev in events:
        item = ev.get("item")
        if not isinstance(item, dict):
            continue
        if ev.get("type") != "item.started":
            continue
        if item.get("type") == "collab_tool_call" and item.get("tool") == "spawn_agent":
            count += 1
    return count


def _wait_count(events: list[dict[str, Any]]) -> int:
    count = 0
    for ev in events:
        item = ev.get("item")
        if not isinstance(item, dict):
            continue
        if ev.get("type") != "item.started":
            continue
        if item.get("type") == "collab_tool_call" and item.get("tool") == "wait":
            count += 1
    return count


def _final_message(events: list[dict[str, Any]]) -> str:
    msgs: list[str] = []
    for ev in events:
        item = ev.get("item")
        if not isinstance(item, dict):
            continue
        if ev.get("type") == "item.completed" and item.get("type") == "agent_message":
            msgs.append(str(item.get("text") or ""))
    return msgs[-1] if msgs else ""


def _write_seed_files(seed_root: Path) -> dict[str, Path]:
    seed_root.mkdir(parents=True, exist_ok=True)
    stricter_a = seed_root / "policy_a.txt"
    stricter_b = seed_root / "policy_b.txt"
    source = seed_root / "pipeline_source.txt"
    stricter_a.write_text(
        "Policy A\n"
        "allow direct deploys\n"
        "tests optional\n",
        encoding="utf-8",
    )
    stricter_b.write_text(
        "Policy B\n"
        "deploys require review\n"
        "tests mandatory\n"
        "rollback plan mandatory\n",
        encoding="utf-8",
    )
    source.write_text(
        "alpha beta gamma\n"
        "delta epsilon\n",
        encoding="utf-8",
    )
    return {
        "policy_a": stricter_a,
        "policy_b": stricter_b,
        "pipeline_source": source,
    }


def _contains_all(text: str, needles: list[str]) -> bool:
    return all(n in text for n in needles)


def _check_explorer_readonly(final_message: str, spawn_count: int, _: dict[str, Path]) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if spawn_count < 1:
        notes.append("expected at least one spawn_agent call")
    if "basename=ChatgptREST" not in final_message:
        notes.append(f"unexpected final message: {final_message!r}")
    return not notes, notes


def _check_readonly_denied(final_message: str, spawn_count: int, paths: dict[str, Path]) -> tuple[bool, list[str]]:
    notes: list[str] = []
    target = paths["target"]
    if spawn_count < 1:
        notes.append("expected at least one spawn_agent call")
    if target.exists():
        notes.append(f"read-only role unexpectedly wrote file: {target}")
    if "wrote=no" not in final_message:
        notes.append(f"final message did not confirm refusal: {final_message!r}")
    return not notes, notes


def _check_reviewer_analysis(final_message: str, spawn_count: int, _: dict[str, Path]) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if spawn_count < 1:
        notes.append("expected at least one spawn_agent call")
    if not _contains_all(final_message, ["result=ok", "role=default", "stricter=B"]):
        notes.append(f"unexpected final message: {final_message!r}")
    return not notes, notes


def _check_worker_write(final_message: str, spawn_count: int, paths: dict[str, Path]) -> tuple[bool, list[str]]:
    notes: list[str] = []
    target = paths["target"]
    expected = paths["expected_text"].read_text(encoding="utf-8")
    actual = target.read_text(encoding="utf-8") if target.exists() else ""
    if spawn_count < 1:
        notes.append("expected at least one spawn_agent call")
    if not target.exists():
        notes.append(f"worker did not write expected file: {target}")
    elif actual != expected:
        notes.append(f"worker output mismatch: expected {expected!r}, got {actual!r}")
    if "wrote=yes" not in final_message:
        notes.append(f"final message did not confirm write: {final_message!r}")
    return not notes, notes


def _check_mixed_pipeline(final_message: str, spawn_count: int, paths: dict[str, Path]) -> tuple[bool, list[str]]:
    notes: list[str] = []
    target = paths["target"]
    expected = paths["expected_text"].read_text(encoding="utf-8")
    actual = target.read_text(encoding="utf-8") if target.exists() else ""
    if spawn_count < 2:
        notes.append("expected at least two spawn_agent calls")
    if not target.exists():
        notes.append(f"mixed pipeline did not create summary file: {target}")
    elif actual != expected:
        notes.append(f"mixed pipeline output mismatch: expected {expected!r}, got {actual!r}")
    if "result=ok" not in final_message:
        notes.append(f"unexpected final message: {final_message!r}")
    return not notes, notes


def _check_tri_role_pipeline(final_message: str, spawn_count: int, paths: dict[str, Path]) -> tuple[bool, list[str]]:
    notes: list[str] = []
    target = paths["target"]
    expected = paths["expected_text"].read_text(encoding="utf-8")
    actual = target.read_text(encoding="utf-8") if target.exists() else ""
    if spawn_count < 3:
        notes.append("expected at least three spawn_agent calls")
    if not target.exists():
        notes.append(f"tri-role pipeline did not create output file: {target}")
    elif actual != expected:
        notes.append(f"tri-role output mismatch: expected {expected!r}, got {actual!r}")
    if not _contains_all(final_message, ["result=ok", "verified=yes"]):
        notes.append(f"unexpected final message: {final_message!r}")
    return not notes, notes


@dataclass
class TestCase:
    name: str
    prompt_builder: Callable[[dict[str, Path]], str]
    checker: Callable[[str, int, dict[str, Path]], tuple[bool, list[str]]]


def _make_cases() -> list[TestCase]:
    return [
        TestCase(
            name="explorer_readonly_success",
            prompt_builder=lambda ctx: textwrap.dedent(
                f"""
                Use exactly one explorer subagent and no other subagents.
                Do not edit any files.
                Determine the basename of the current working directory `{ctx["repo_root"]}`.
                Reply exactly: result=ok; role=explorer; basename=<name>
                """
            ).strip(),
            checker=_check_explorer_readonly,
        ),
        TestCase(
            name="explorer_write_denied",
            prompt_builder=lambda ctx: textwrap.dedent(
                f"""
                Use exactly one explorer subagent and no other subagents.
                The parent agent must not write files.
                Ask the explorer subagent to create the file `{ctx["target"]}` with the content `explorer test`.
                Because the explorer subagent is read-only, it must refuse rather than write.
                Reply exactly: result=<refused-or-blocked>; role=explorer; wrote=no
                """
            ).strip(),
            checker=_check_readonly_denied,
        ),
        TestCase(
            name="reviewer_analysis_success",
            prompt_builder=lambda ctx: textwrap.dedent(
                f"""
                Use exactly one default subagent and no other subagents.
                Do not edit any files.
                Compare `{ctx["policy_a"]}` and `{ctx["policy_b"]}` and decide which policy is stricter.
                Reply exactly: result=ok; role=default; stricter=<A-or-B>
                """
            ).strip(),
            checker=_check_reviewer_analysis,
        ),
        TestCase(
            name="reviewer_write_denied",
            prompt_builder=lambda ctx: textwrap.dedent(
                f"""
                Use exactly one default subagent and no other subagents.
                The parent agent must not write files.
                Ask the default subagent to create the file `{ctx["target"]}` with the content `reviewer test`.
                Because the default subagent is read-only, it must refuse rather than write.
                Reply exactly: result=<refused-or-blocked>; role=default; wrote=no
                """
            ).strip(),
            checker=_check_readonly_denied,
        ),
        TestCase(
            name="worker_write_success",
            prompt_builder=lambda ctx: textwrap.dedent(
                f"""
                Use exactly one worker subagent and no other subagents.
                The parent agent must not write files.
                Ask the worker subagent to create the file `{ctx["target"]}` with this exact content:

                worker-role-smoke
                owner=subagent

                Reply exactly: result=ok; role=worker; wrote=yes
                """
            ).strip(),
            checker=_check_worker_write,
        ),
        TestCase(
            name="mixed_pipeline_success",
            prompt_builder=lambda ctx: textwrap.dedent(
                f"""
                Use exactly one explorer subagent and exactly one worker subagent.
                Do not use the default subagent.
                The parent agent must not write files.
                First, ask the explorer subagent to read `{ctx["pipeline_source"]}` and determine:
                - the number of space-separated tokens on the first line
                - the total number of lines in the file
                Then ask the worker subagent to create `{ctx["target"]}` with this exact content:

                tokens=3; lines=2

                Reply exactly: result=ok; path={ctx["target"]}
                """
            ).strip(),
            checker=_check_mixed_pipeline,
        ),
        TestCase(
            name="tri_role_pipeline_success",
            prompt_builder=lambda ctx: textwrap.dedent(
                f"""
                Use exactly one explorer subagent, exactly one worker subagent, and exactly one default subagent.
                The parent agent must not write files.
                Explorer: inspect `{ctx["policy_b"]}` and determine the line count.
                Worker: create `{ctx["target"]}` with this exact content:

                strictest=policy_b
                lines=4

                Default: verify the created file exactly matches the required content.
                Reply exactly: result=ok; verified=yes; path={ctx["target"]}
                """
            ).strip(),
            checker=_check_tri_role_pipeline,
        ),
    ]


def _run_case(target: HomeTarget, case: TestCase, home_artifacts: Path, seed_paths: dict[str, Path]) -> RunResult:
    case_dir = home_artifacts / case.name
    case_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "target": case_dir / "target.txt",
        "expected_text": case_dir / "expected.txt",
    }
    if case.name == "explorer_write_denied":
        paths["target"] = case_dir / "explorer_should_not_write.txt"
    elif case.name == "reviewer_write_denied":
        paths["target"] = case_dir / "reviewer_should_not_write.txt"
    elif case.name == "worker_write_success":
        paths["target"] = case_dir / "worker_output.txt"
        paths["expected_text"] = case_dir / "worker_expected.txt"
        paths["expected_text"].write_text("worker-role-smoke\nowner=subagent\n", encoding="utf-8")
    elif case.name == "mixed_pipeline_success":
        paths["target"] = case_dir / "mixed_pipeline.txt"
        paths["expected_text"] = case_dir / "mixed_expected.txt"
        paths["expected_text"].write_text("tokens=3; lines=2\n", encoding="utf-8")
    elif case.name == "tri_role_pipeline_success":
        paths["target"] = case_dir / "tri_role_pipeline.txt"
        paths["expected_text"] = case_dir / "tri_expected.txt"
        paths["expected_text"].write_text("strictest=policy_b\nlines=4\n", encoding="utf-8")

    if paths["target"].exists():
        paths["target"].unlink()

    context = dict(seed_paths)
    context.update(paths)
    context["repo_root"] = REPO_ROOT
    prompt = case.prompt_builder(context)

    jsonl_path = case_dir / "events.jsonl"
    stderr_path = case_dir / "stderr.txt"
    rc, duration = _run_codex(target=target, prompt=prompt, jsonl_path=jsonl_path, stderr_path=stderr_path)
    events = _parse_events(jsonl_path)
    spawn_count = _spawn_count(events)
    wait_count = _wait_count(events)
    final_message = _final_message(events)
    ok, notes = case.checker(final_message, spawn_count, paths)
    if rc != 0:
        ok = False
        notes.append(f"codex exec returned non-zero rc={rc}")
    return RunResult(
        home=target.name,
        test=case.name,
        ok=ok,
        rc=rc,
        duration_sec=round(duration, 3),
        spawn_count=spawn_count,
        wait_count=wait_count,
        final_message=final_message,
        notes=notes,
        jsonl_path=str(jsonl_path),
        stderr_path=str(stderr_path),
    )


def _write_report(out_dir: Path, results: list[RunResult]) -> None:
    report_md = out_dir / "report.md"
    report_json = out_dir / "results.json"
    report_json.write_text(
        json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Codex Subagent Smoke Report",
        "",
        f"- Generated at: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"- Repo root: `{REPO_ROOT}`",
        "",
        "| home | test | ok | rc | spawn | wait | duration_sec |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r.home} | {r.test} | {'yes' if r.ok else 'no'} | {r.rc} | {r.spawn_count} | {r.wait_count} | {r.duration_sec} |"
        )
    lines.append("")
    lines.append("## Details")
    lines.append("")
    for r in results:
        lines.append(f"### {r.home} / {r.test}")
        lines.append("")
        lines.append(f"- ok: `{'yes' if r.ok else 'no'}`")
        lines.append(f"- rc: `{r.rc}`")
        lines.append(f"- spawn_count: `{r.spawn_count}`")
        lines.append(f"- wait_count: `{r.wait_count}`")
        lines.append(f"- duration_sec: `{r.duration_sec}`")
        lines.append(f"- final_message: `{r.final_message}`")
        lines.append(f"- jsonl: `{r.jsonl_path}`")
        lines.append(f"- stderr: `{r.stderr_path}`")
        if r.notes:
            lines.append("- notes:")
            for note in r.notes:
                lines.append(f"  - {note}")
        lines.append("")
    report_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    run_id = time.strftime("%Y%m%d_%H%M%S")
    out_dir = ARTIFACTS_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    seed_root = out_dir / "seeds"
    seed_paths = _write_seed_files(seed_root)

    homes = [
        HomeTarget(name="codex_home", home=ROOT_HOME, codex_home=CODEX_HOME_DIR),
        HomeTarget(name="official_home", home=ROOT_HOME, codex_home=OFFICIAL_CODEX_DIR),
    ]

    results: list[RunResult] = []
    for home in homes:
        home_dir = out_dir / home.name
        home_dir.mkdir(parents=True, exist_ok=True)
        cases = _make_cases()
        for case in cases:
            print(f"[run] {home.name} :: {case.name}", flush=True)
            result = _run_case(home, case, home_dir, seed_paths)
            results.append(result)
            print(
                f"[done] {home.name} :: {case.name} :: ok={result.ok} rc={result.rc} "
                f"spawn={result.spawn_count} wait={result.wait_count}",
                flush=True,
            )

    _write_report(out_dir, results)
    failed = [r for r in results if not r.ok]
    print(f"[artifacts] {out_dir}", flush=True)
    if failed:
        print(f"[summary] failures={len(failed)} / total={len(results)}", flush=True)
        return 1
    print(f"[summary] all_passed={len(results)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
