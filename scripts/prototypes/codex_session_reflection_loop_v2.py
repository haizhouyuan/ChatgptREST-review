#!/usr/bin/env python3
"""Build a review-gated wiki/memory/skill queue from Codex sessions.

V2 intentionally keeps the loop offline and reversible:

1. read Codex JSONL sessions
2. extract compact reflection candidates
3. route candidates into wiki, memory, and skill-update queues
4. emit a candidate skill folder, but do not install or overwrite live skills
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from codex_session_reflection_extract import compact, extract_session


DEFAULT_EUPHONY_ROOT = Path("/vol1/1000/tools/euphony")
DEFAULT_EUPHONY_VIEWER = "http://127.0.0.1:8766/"
DEFAULT_MAX_SESSIONS = 8

PROMOTION_THRESHOLDS = {
    "wiki": 0.65,
    "memory": 0.7,
    "skill": 0.75,
}

SKILL_PROMOTION_CATEGORIES = {"debugging", "convention", "environment"}
MEMORY_PROMOTION_SOURCES = {"user_prompt"}
WIKI_PROMOTION_CATEGORIES = {"debugging", "convention", "environment", "decision", "session-log"}


def slugify(value: str, limit: int = 72) -> str:
    lowered = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.lower()).strip("-")
    if not lowered:
        lowered = "candidate"
    return lowered[:limit].strip("-") or "candidate"


def stable_hash(value: str, limit: int = 12) -> str:
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:limit]


def normalize_fingerprint_text(text: str) -> str:
    normalized = re.sub(r"\b[0-9a-f]{12,}\b", "<hex>", text.lower())
    normalized = re.sub(r"\b\d+\b", "<num>", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[:500]


def default_session_roots() -> list[Path]:
    roots: list[Path] = []
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        roots.append(Path(codex_home) / "sessions")
    home = os.environ.get("HOME")
    if home:
        roots.append(Path(home) / ".codex" / "sessions")
    return roots


def read_session_meta(path: Path) -> dict[str, Any]:
    try:
        first_line = path.open("r", encoding="utf-8", errors="replace").readline()
        first = json.loads(first_line)
    except Exception:
        return {}
    payload = first.get("payload") if isinstance(first, dict) else None
    return dict(payload or {}) if isinstance(payload, dict) else {}


def discover_sessions(
    roots: Iterable[Path],
    *,
    cwd_contains: str,
    since_days: int,
    max_sessions: int,
) -> list[Path]:
    cutoff = dt.datetime.now(dt.timezone.utc).timestamp() - since_days * 86400
    matches: list[tuple[float, Path]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("rollout-*.jsonl"):
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_mtime < cutoff:
                continue
            meta = read_session_meta(path)
            cwd = str(meta.get("cwd") or "")
            if cwd_contains and cwd_contains not in cwd:
                continue
            matches.append((stat.st_mtime, path))
    return [path for _, path in sorted(matches, reverse=True)[:max_sessions]]


def evidence_review_ref(session: dict[str, Any], euphony_viewer: str) -> dict[str, Any]:
    return {
        "viewer": euphony_viewer,
        "session_path": session["path"],
        "note": "Open the viewer and choose this JSONL file when a candidate needs transcript-level review.",
    }


def enrich_candidate(session: dict[str, Any], candidate: dict[str, Any], euphony_viewer: str) -> dict[str, Any]:
    text = str(candidate.get("text") or "")
    category = str(candidate.get("category") or "reference")
    source = str(candidate.get("source") or "unknown")
    fingerprint_input = f"{category}\n{source}\n{normalize_fingerprint_text(text)}"
    fingerprint = stable_hash(fingerprint_input)
    enriched = dict(candidate)
    enriched.update(
        {
            "fingerprint": fingerprint,
            "session_id": session["session_id"],
            "session_path": session["path"],
            "session_timestamp": session.get("timestamp"),
            "cwd": session.get("cwd"),
            "euphony_review": evidence_review_ref(session, euphony_viewer),
            "promotion_targets": promotion_targets(candidate),
        }
    )
    return enriched


def promotion_targets(candidate: dict[str, Any]) -> list[str]:
    category = str(candidate.get("category") or "")
    source = str(candidate.get("source") or "")
    confidence = float(candidate.get("confidence") or 0.0)
    targets: list[str] = []
    if category in WIKI_PROMOTION_CATEGORIES and confidence >= PROMOTION_THRESHOLDS["wiki"]:
        targets.append("wiki")
    if source in MEMORY_PROMOTION_SOURCES and confidence >= PROMOTION_THRESHOLDS["memory"]:
        targets.append("memory")
    if category in SKILL_PROMOTION_CATEGORIES and confidence >= PROMOTION_THRESHOLDS["skill"]:
        targets.append("skill_candidate")
    return targets


def dedupe_candidates(candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_fingerprint: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        fingerprint = str(candidate["fingerprint"])
        existing = by_fingerprint.get(fingerprint)
        if existing is None:
            by_fingerprint[fingerprint] = candidate
            continue
        existing["occurrences"] = int(existing.get("occurrences") or 1) + 1
        existing_sessions = list(existing.get("related_sessions") or [existing["session_id"]])
        if candidate["session_id"] not in existing_sessions:
            existing_sessions.append(candidate["session_id"])
        existing["related_sessions"] = existing_sessions
        if float(candidate.get("confidence") or 0) > float(existing.get("confidence") or 0):
            existing["text"] = candidate.get("text")
            existing["confidence"] = candidate.get("confidence")
    for candidate in by_fingerprint.values():
        candidate.setdefault("occurrences", 1)
        candidate.setdefault("related_sessions", [candidate["session_id"]])
    return sorted(
        by_fingerprint.values(),
        key=lambda item: (
            len(item.get("promotion_targets") or []),
            int(item.get("occurrences") or 1),
            float(item.get("confidence") or 0),
        ),
        reverse=True,
    )


def candidate_title(candidate: dict[str, Any]) -> str:
    category = str(candidate.get("category") or "reference")
    source = str(candidate.get("source") or "candidate")
    text = compact(str(candidate.get("text") or ""), 80)
    return f"{category} {source} {text}"


def build_wiki_draft(candidate: dict[str, Any]) -> str:
    title = candidate_title(candidate)
    tags = [
        "codex-session-reflection",
        str(candidate.get("category") or "reference"),
        str(candidate.get("source") or "unknown"),
    ]
    lines = [
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"category: {candidate.get('category')}",
        f"confidence: {candidate.get('confidence')}",
        f"tags: {json.dumps(tags, ensure_ascii=False)}",
        f"source_session: {candidate.get('session_id')}",
        f"source_path: {candidate.get('session_path')}",
        f"promotion_state: candidate",
        "---",
        "",
        f"# {title}",
        "",
        "## Candidate Lesson",
        "",
        str(candidate.get("text") or ""),
        "",
        "## Evidence",
        "",
        f"- session: `{candidate.get('session_id')}`",
        f"- path: `{candidate.get('session_path')}`",
        f"- euphony viewer: `{candidate.get('euphony_review', {}).get('viewer')}`",
        "",
        "## Promotion Gate",
        "",
        "- Confirm the lesson is not one-off session noise.",
        "- Confirm it has no secrets or private raw transcript content.",
        "- Promote only after repeated evidence or explicit maintainer approval.",
        "",
    ]
    return "\n".join(lines)


def memory_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    category = str(candidate.get("category") or "reference")
    source = str(candidate.get("source") or "unknown")
    return {
        "schema": "memory-candidate-v1",
        "category": f"session_reflection:{category}",
        "key": f"codex_session_reflection:{candidate['fingerprint']}",
        "value": {
            "lesson": candidate.get("text"),
            "category": category,
            "source": source,
            "occurrences": candidate.get("occurrences", 1),
            "related_sessions": candidate.get("related_sessions", [candidate.get("session_id")]),
        },
        "confidence": candidate.get("confidence"),
        "source": {
            "type": "codex_session_jsonl",
            "session_id": candidate.get("session_id"),
            "path": candidate.get("session_path"),
            "cwd": candidate.get("cwd"),
        },
        "promotion_state": "candidate",
    }


def build_skill_candidate(candidates: list[dict[str, Any]]) -> str:
    skill_candidates = [c for c in candidates if "skill_candidate" in (c.get("promotion_targets") or [])]
    lessons = dedupe_skill_lessons(skill_candidates)
    lines = [
        "---",
        "name: codex-session-reflection",
        "description: Use when reviewing Codex session JSONL logs to extract durable lessons, route them into wiki or memory candidates, and propose skill updates through a review gate without importing raw transcripts as long-term instructions.",
        "---",
        "",
        "# Codex Session Reflection",
        "",
        "Use this skill when asked to mine Codex session history for agent improvement, self-learning, llmwiki updates, or skill evolution.",
        "",
        "## Workflow",
        "",
        "1. Read Codex session JSONL from `$CODEX_HOME/sessions` or an explicit path.",
        "2. Extract compact evidence spans: user corrections, command failures, root-cause statements, environment/tooling lessons, final fixes, and closeout results.",
        "3. Route candidates by target:",
        "   - `wiki`: durable debugging, environment, convention, decision, or high-value session-log lessons.",
        "   - `memory`: repeated or explicit user preference/correction signals.",
        "   - `skill_candidate`: stable procedural rules that change how future agents should work.",
        "4. Use Euphony as a transcript review surface when evidence is ambiguous; do not rely on manual browsing as the pipeline.",
        "5. Promote only after repeated evidence or explicit maintainer approval.",
        "",
        "## Guardrails",
        "",
        "- Do not promote raw transcripts into skills.",
        "- Do not convert a single one-off failure into global agent policy.",
        "- Redact secrets, tokens, emails, and raw private payloads before writing candidates.",
        "- Keep installed skill edits as explicit patches with rollback notes.",
        "- Prefer wiki or memory candidates over skill edits unless the lesson is procedural and reusable.",
        "",
        "## Candidate Procedural Lessons From Latest Run",
        "",
    ]
    if not lessons:
        lines.append("- No skill-level candidate met the current promotion threshold.")
    for lesson in lessons[:10]:
        lines.append(f"- {lesson}")
    lines.append("")
    return "\n".join(lines)


def summarize_skill_lesson(candidate: dict[str, Any]) -> str | None:
    text = str(candidate.get("text") or "")
    lowered = text.lower()
    if "429" in lowered and ("dom fallback" in lowered or "export" in lowered):
        return "When export metadata shows backend `429`, do not treat DOM fallback text as a complete successful answer until finality metadata is reconciled."
    if "public mcp" in lowered and ("不前台等待" in text or "background" in lowered or "异步" in text):
        return "For long Pro or external-review jobs, submit through the public MCP async lane and continue local work instead of blocking the foreground session."
    if "jsondecodeerror" in lowered or "cooldown" in lowered:
        return "When MCP or wrapper responses contain cooldown/rate-limit text, preserve structured error details instead of collapsing them into generic parse failures."
    if "没有产出可引用的最终答复" in text or "final answer" in lowered:
        return "Treat missing final answer artifacts as an evidence-chain failure even when the provider request itself was submitted successfully."
    if "pro thinking" in lowered or "thinking" in lowered:
        return "For ChatGPT Pro investigations, distinguish visible UI thinking indicators from backend model/preset evidence before deciding that the wrong model ran."
    if "不要影响客户端" in text or "client" in lowered:
        return "For ChatgptREST maintenance, keep client-facing public MCP behavior stable while changing worker/runtime internals."
    if "handoff" in lowered or "接手" in text:
        return "On resumed maintenance sessions, read the handoff and current git state first, then avoid repeating already completed work."
    if "根因" in text or "根本原因" in text or "彻底解决" in text or "root cause" in lowered:
        return "For recurring ChatgptREST incidents, investigate root cause across job events, worker logs, exports, and client wrapper behavior before patching symptoms."
    if "proxy" in lowered or "no_proxy" in lowered or "github" in lowered:
        return "When installing external tooling, verify proxy and `NO_PROXY` behavior before diagnosing GitHub or registry failures as package problems."
    return None


def dedupe_skill_lessons(candidates: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    lessons: list[str] = []
    for candidate in candidates:
        lesson = summarize_skill_lesson(candidate)
        if not lesson:
            continue
        if lesson in seen:
            continue
        seen.add(lesson)
        lessons.append(lesson)
    return lessons


def build_skill_update_plan(candidates: list[dict[str, Any]], skill_path: Path) -> str:
    skill_candidates = [c for c in candidates if "skill_candidate" in (c.get("promotion_targets") or [])]
    lines = [
        "# Skill Update Candidate Plan v2",
        "",
        f"Candidate skill folder: `{skill_path}`",
        "",
        "## Default Decision",
        "",
        "Do not auto-install this candidate. Review it as a patch first.",
        "",
        "## Promotion Criteria",
        "",
        "- Candidate lesson is procedural, not merely informational.",
        "- At least two sessions show the same pattern, or the maintainer explicitly approves one high-impact incident.",
        "- The skill text is shorter than the raw evidence it replaces.",
        "- A rollback is possible by removing the generated skill folder or reverting the skill patch commit.",
        "",
        "## Candidate Count",
        "",
        f"- skill candidates: `{len(skill_candidates)}`",
        "",
        "## Candidates",
        "",
    ]
    for candidate in skill_candidates[:20]:
        lines.append(
            f"- `{candidate['fingerprint']}` `{candidate.get('category')}` "
            f"confidence={candidate.get('confidence')} sessions={candidate.get('related_sessions')}: "
            f"{candidate.get('text')}"
        )
    if not skill_candidates:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def build_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Codex Session Reflection Loop v2",
        "",
        f"Generated at: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- sessions scanned: `{len(report['sessions'])}`",
        f"- unique candidates: `{len(report['candidates'])}`",
        f"- wiki candidates: `{len(report['wiki_candidates'])}`",
        f"- memory candidates: `{len(report['memory_candidates'])}`",
        f"- skill candidates: `{len(report['skill_candidates'])}`",
        f"- euphony viewer: `{report['euphony']['viewer']}`",
        f"- euphony parser reference: `{report['euphony']['codex_parser_reference']}`",
        "",
        "## Sessions",
        "",
    ]
    for session in report["sessions"]:
        lines.extend(
            [
                f"### {session['file_name']}",
                "",
                f"- session: `{session['session_id']}`",
                f"- cwd: `{session.get('cwd')}`",
                f"- prompts: `{session.get('actual_user_prompt_count')}`",
                f"- command failures: `{session.get('command_failure_count')}`",
                f"- reflection candidates: `{len(session.get('reflection_candidates') or [])}`",
                "",
            ]
        )
    lines.extend(["## Top Candidates", ""])
    for candidate in report["candidates"][:25]:
        lines.append(
            f"- `{candidate['fingerprint']}` targets={candidate.get('promotion_targets')} "
            f"`{candidate.get('category')}` `{candidate.get('source')}` "
            f"confidence={candidate.get('confidence')} occurrences={candidate.get('occurrences')}: "
            f"{candidate.get('text')}"
        )
    lines.append("")
    lines.extend(["## Artifacts", ""])
    for name, path in report["artifacts"].items():
        lines.append(f"- `{name}`: `{path}`")
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    queue_dir = out_dir / "queue"
    wiki_dir = queue_dir / "wiki_candidates"
    skill_dir = queue_dir / "skill_candidates" / "codex-session-reflection"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    skill_dir.mkdir(parents=True, exist_ok=True)

    wiki_paths: list[str] = []
    for candidate in report["wiki_candidates"]:
        category = slugify(str(candidate.get("category") or "reference"), 24)
        source = slugify(str(candidate.get("source") or "candidate"), 24)
        file_name = f"{candidate['fingerprint']}_{category}_{source}.md"
        path = wiki_dir / file_name
        path.write_text(build_wiki_draft(candidate), encoding="utf-8")
        wiki_paths.append(str(path))

    memory_path = queue_dir / "memory_candidates.jsonl"
    with memory_path.open("w", encoding="utf-8") as handle:
        for candidate in report["memory_candidates"]:
            handle.write(json.dumps(memory_candidate(candidate), ensure_ascii=False) + "\n")

    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(build_skill_candidate(report["candidates"]), encoding="utf-8")

    skill_plan_path = queue_dir / "skill_update_plan_v2.md"
    skill_plan_path.write_text(build_skill_update_plan(report["candidates"], skill_dir), encoding="utf-8")

    report["artifacts"].update(
        {
            "wiki_candidate_dir": str(wiki_dir),
            "wiki_candidate_files": wiki_paths,
            "memory_candidates_jsonl": str(memory_path),
            "skill_candidate": str(skill_path),
            "skill_update_plan": str(skill_plan_path),
        }
    )

    json_path = out_dir / "loop_report_v2.json"
    md_path = out_dir / "loop_report_v2.md"
    report["artifacts"].update({"loop_report_json": str(json_path), "loop_report_md": str(md_path)})
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(build_markdown_report(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sessions", nargs="*", type=Path, help="Explicit Codex session JSONL files.")
    parser.add_argument("--session-root", action="append", type=Path, default=[])
    parser.add_argument("--cwd-contains", default="ChatgptREST")
    parser.add_argument("--since-days", type=int, default=4)
    parser.add_argument("--max-sessions", type=int, default=DEFAULT_MAX_SESSIONS)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--euphony-root", type=Path, default=DEFAULT_EUPHONY_ROOT)
    parser.add_argument("--euphony-viewer", default=DEFAULT_EUPHONY_VIEWER)
    args = parser.parse_args()

    if args.sessions:
        session_paths = args.sessions
    else:
        roots = args.session_root or default_session_roots()
        session_paths = discover_sessions(
            roots,
            cwd_contains=args.cwd_contains,
            since_days=args.since_days,
            max_sessions=args.max_sessions,
        )

    sessions = [extract_session(path) for path in session_paths]
    enriched: list[dict[str, Any]] = []
    for session in sessions:
        for candidate in session.get("reflection_candidates") or []:
            enriched.append(enrich_candidate(session, candidate, args.euphony_viewer))
    candidates = dedupe_candidates(enriched)
    wiki_candidates = [c for c in candidates if "wiki" in (c.get("promotion_targets") or [])]
    memory_candidates = [c for c in candidates if "memory" in (c.get("promotion_targets") or [])]
    skill_candidates = [c for c in candidates if "skill_candidate" in (c.get("promotion_targets") or [])]

    report: dict[str, Any] = {
        "schema": "codex-session-reflection-loop-v2",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "euphony": {
            "root": str(args.euphony_root),
            "viewer": args.euphony_viewer,
            "codex_parser_reference": str(args.euphony_root / "src" / "utils" / "codex-session.ts"),
            "role": "human-readable transcript review surface and parser reference; automated loop reads JSONL directly",
        },
        "thresholds": PROMOTION_THRESHOLDS,
        "sessions": sessions,
        "candidates": candidates,
        "wiki_candidates": wiki_candidates,
        "memory_candidates": memory_candidates,
        "skill_candidates": skill_candidates,
        "artifacts": {},
        "safety": {
            "raw_transcripts_promoted": False,
            "installed_skill_mutated": False,
            "writes_live_memory_db": False,
            "review_gate_required": True,
        },
    }
    write_outputs(report, args.out_dir)
    print(f"wrote {args.out_dir / 'loop_report_v2.md'}")
    print(f"candidates={len(candidates)} wiki={len(wiki_candidates)} memory={len(memory_candidates)} skill={len(skill_candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
