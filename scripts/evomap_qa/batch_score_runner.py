#!/usr/bin/env python3
"""batch_score_runner.py — 通过 ChatgptREST API 自动批量评分.

自动化 submit → wait → parse → save 循环。
支持 ChatGPT Pro 和 Gemini Pro 双通道，断点续跑。

用法:
    # 试跑 1 批 (10条)
    python3 batch_score_runner.py --provider chatgpt --max-batches 1 --domain AIOS架构

    # 全量跑
    python3 batch_score_runner.py --provider chatgpt --max-batches 0

    # Gemini 通道
    python3 batch_score_runner.py --provider gemini --max-batches 50

    # 双通道并行 (两个终端分别跑)
    # Terminal 1: python3 batch_score_runner.py --provider chatgpt --split odd
    # Terminal 2: python3 batch_score_runner.py --provider gemini --split even
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_URL = "http://127.0.0.1:18711"   # REST API port

SCORED_FILE = Path(__file__).parent / "planning_qa_scored.jsonl"
PROGRESS_FILE = Path(__file__).parent / "batch_progress.json"

BATCH_SIZE_DEFAULT = 10
WAIT_TIMEOUT = 300  # seconds per job wait
RETRY_LIMIT = 3

# Rubric dimensions (v2: 7-dim)
DIMS = ("clarity", "correctness", "evidence", "actionability",
        "risk", "alignment", "completeness")

# Import prompt builder from llm_score
sys.path.insert(0, str(Path(__file__).parent))
from llm_score import build_scoring_prompt, get_rubric_for_record  # noqa: E402


# ---------------------------------------------------------------------------
# HTTP helpers (no external deps)
# ---------------------------------------------------------------------------

def _post_json(url: str, data: dict, headers: dict | None = None) -> dict:
    """POST JSON and return parsed response."""
    body = json.dumps(data).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {err_body}") from e


def _get_json(url: str, timeout: int = 30) -> dict:
    """GET JSON and return parsed response."""
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {err_body}") from e


# ---------------------------------------------------------------------------
# Job submission and waiting
# ---------------------------------------------------------------------------

def submit_scoring_job(prompt: str, provider: str, batch_idx: int) -> str:
    """Submit a scoring prompt to ChatgptREST and return job_id."""
    idem_key = f"batch-score-{provider}-b{batch_idx:04d}-{int(time.time())}"

    if provider == "chatgpt":
        kind = "chatgpt_web.ask"
        preset = "thinking_heavy"  # auto triggers extended thinking; heavy waits for full answer
    elif provider == "gemini":
        kind = "gemini_web.ask"
        preset = "pro"
    else:
        raise ValueError(f"Unknown provider: {provider}")

    result = _post_json(f"{API_URL}/v1/jobs", {
        "kind": kind,
        "input": {"question": prompt},
        "params": {
            "preset": preset,
            "purpose": "batch_scoring",
            "send_timeout_seconds": 300,
            "wait_timeout_seconds": WAIT_TIMEOUT,
        },
    }, headers={
        "Idempotency-Key": idem_key,
        "X-Client-Name": "chatgptrestctl",
        "X-Client-Instance": f"batch-scorer-{provider}",
        "X-Request-ID": f"score-{provider}-{batch_idx:04d}",
    })

    job_id = result.get("job_id", "")
    status = result.get("status", "")
    print(f"  📤 Submitted job {job_id[:12]}... (status: {status})")
    return job_id


def wait_for_job(job_id: str) -> dict:
    """Wait for job completion and return the job result."""
    url = f"{API_URL}/v1/jobs/{job_id}/wait?timeout_seconds={WAIT_TIMEOUT}&auto_wait_cooldown=true"
    print(f"  ⏳ Waiting for {job_id[:12]}...", end="", flush=True)

    for attempt in range(RETRY_LIMIT):
        try:
            result = _get_json(url, timeout=WAIT_TIMEOUT + 30)
            status = result.get("status", "")
            print(f" [{status}]")

            if status == "completed":
                return result
            elif status == "error":
                print(f"  ❌ Job error: {result.get('error', 'unknown')}")
                return result
            elif status in ("in_progress", "cooldown"):
                print(f"  ⏳ Still {status}, retrying...", end="", flush=True)
                continue
            else:
                print(f"  ⚠️ Unexpected status: {status}")
                return result
        except Exception as e:
            print(f"\n  ⚠️ Wait error (attempt {attempt+1}/{RETRY_LIMIT}): {e}")
            if attempt < RETRY_LIMIT - 1:
                time.sleep(10)

    print(f"  ❌ Gave up waiting for {job_id[:12]}")
    return {"status": "timeout", "job_id": job_id}


def read_answer(job_id: str) -> str:
    """Read the answer text from a completed job."""
    # Method 1: Read from artifact file (most reliable)
    artifacts_dir = Path("/vol1/1000/projects/ChatgptREST/artifacts")
    answer_path = artifacts_dir / "jobs" / job_id / "answer.md"
    if answer_path.exists():
        text = answer_path.read_text("utf-8", errors="replace")
        if len(text) > 100:  # Not just a preamble
            return text

    # Method 2: Parse conversation.json for all assistant messages
    conv_path = artifacts_dir / "jobs" / job_id / "conversation.json"
    if conv_path.exists():
        try:
            conv = json.loads(conv_path.read_text("utf-8"))
            mapping = conv.get("mapping", {})
            assistant_texts = []
            for node in mapping.values():
                msg = node.get("message", {})
                if msg and msg.get("author", {}).get("role") == "assistant":
                    parts = msg.get("content", {}).get("parts", [])
                    for p in parts:
                        if isinstance(p, str) and len(p) > 30:
                            assistant_texts.append(p)
            if assistant_texts:
                # Return the longest assistant message (likely the actual scores)
                return max(assistant_texts, key=len)
        except (json.JSONDecodeError, KeyError):
            pass

    # Method 3: Try the API answer endpoint
    try:
        url = f"{API_URL}/v1/jobs/{job_id}/answer?offset=0&max_chars=32000"
        result = _get_json(url)
        text = result.get("text", "")
        if text:
            return text
    except Exception:
        pass

    # Method 4: Fallback to job preview
    try:
        job = _get_json(f"{API_URL}/v1/jobs/{job_id}")
        return job.get("preview", "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def parse_scoring_response(text: str) -> list[dict]:
    """Parse LLM response to extract scored items."""
    # Strip common prefixes like "JSON\n" or "json\n"
    text_stripped = re.sub(r'^(?:JSON|json)\s*\n', '', text.strip())

    # Try to find JSON array in markdown code blocks
    json_match = re.search(r'```json\s*\n(.*?)\n```', text_stripped, re.DOTALL)
    if json_match:
        text_to_parse = json_match.group(1)
    else:
        # Try to find raw JSON array
        arr_match = re.search(r'\[\s*\{.*?\}\s*\]', text_stripped, re.DOTALL)
        if arr_match:
            text_to_parse = arr_match.group(0)
        else:
            text_to_parse = text_stripped

    try:
        result = json.loads(text_to_parse)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Line-by-line fallback
    results = []
    for line in text_to_parse.strip().split("\n"):
        line = line.strip().rstrip(",")
        if line.startswith("{"):
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    if results:
        return results

    # Truncated JSON recovery: extract complete objects by brace depth
    objects = []
    depth = 0
    current = ""
    for char in text_to_parse:
        if char == "{":
            depth += 1
        if depth > 0:
            current += char
        if char == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(current)
                    if "qa_id" in obj:  # validate it's a score object
                        objects.append(obj)
                except json.JSONDecodeError:
                    pass
                current = ""
    return objects


# ---------------------------------------------------------------------------
# Score saving
# ---------------------------------------------------------------------------

def save_scores(scored_items: list[dict], provider: str) -> int:
    """Save parsed scores back to the JSONL file."""
    if not scored_items:
        return 0

    # Load all records
    records = []
    index = {}
    for line in SCORED_FILE.read_text("utf-8").strip().split("\n"):
        if line.strip():
            try:
                rec = json.loads(line)
                index[rec["qa_id"]] = len(records)
                records.append(rec)
            except (json.JSONDecodeError, KeyError):
                pass

    updated = 0
    scorer_name = f"llm_{provider}"
    now = datetime.now(timezone.utc).isoformat()

    for item in scored_items:
        qa_id = item.get("qa_id", "")
        if qa_id not in index:
            continue

        idx = index[qa_id]
        scores = {}
        for dim in DIMS:
            val = item.get(dim)
            if val is not None:
                scores[dim] = int(val) if isinstance(val, (int, float)) else val
        scores["overall"] = item.get("overall")
        scores["comment"] = item.get("comment", "")

        # Store as llm scores (separate from human)
        records[idx].setdefault("scores_llm", {})[provider] = {
            **scores,
            "scored_at": now,
            "scorer": scorer_name,
        }

        # If no human scores yet, also populate scores_human for UI display
        if not records[idx].get("scores_human", {}).get("overall"):
            records[idx]["scores_human"] = scores
            records[idx]["human_scorer"] = scorer_name
            records[idx]["human_scored_at"] = now
            if scores.get("overall"):
                records[idx]["status"] = "llm_scored"

        updated += 1

    # Write back
    with open(SCORED_FILE, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return updated


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------

def load_progress(provider: str) -> dict:
    """Load progress from file."""
    if PROGRESS_FILE.exists():
        try:
            data = json.loads(PROGRESS_FILE.read_text("utf-8"))
            if data.get("provider") == provider:
                return data
        except (json.JSONDecodeError, KeyError):
            pass
    return {
        "provider": provider,
        "completed_batches": 0,
        "completed_batch_indices": [],
        "total_scored": 0,
        "errors": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "jobs": [],
    }


def save_progress(progress: dict) -> None:
    """Save progress to file."""
    PROGRESS_FILE.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_batch_scoring(
    provider: str,
    batch_size: int = BATCH_SIZE_DEFAULT,
    max_batches: int = 0,
    domain_filter: str = "",
    split: str = "",  # "odd", "even", or ""
    dry_run: bool = False,
):
    """Run batch scoring loop."""
    # Load records
    records = []
    for line in SCORED_FILE.read_text("utf-8").strip().split("\n"):
        if line.strip():
            try:
                rec = json.loads(line)
                records.append(rec)
            except json.JSONDecodeError:
                continue

    # Filter candidates (not yet LLM-scored by this provider, and not rejected)
    candidates = []
    for r in records:
        if r.get("status") == "rejected":
            continue
        if domain_filter and r.get("domain", "") != domain_filter:
            continue
        # Skip if already scored by this provider
        if r.get("scores_llm", {}).get(provider, {}).get("overall"):
            continue
        candidates.append(r)

    if not candidates:
        print("✅ No unscored records for this provider/domain.")
        return

    # Split into batches
    batches = []
    for i in range(0, len(candidates), batch_size):
        batches.append(candidates[i:i + batch_size])

    # Apply split (odd/even)
    if split == "odd":
        batches = [b for i, b in enumerate(batches) if i % 2 == 0]
    elif split == "even":
        batches = [b for i, b in enumerate(batches) if i % 2 == 1]

    if max_batches > 0:
        batches = batches[:max_batches]

    # Load progress
    progress = load_progress(provider)
    skip_count = progress.get("completed_batches", 0) if not domain_filter else 0

    print(f"\n{'='*60}")
    print(f"🧠 Batch Scoring Runner")
    print(f"{'='*60}")
    print(f"Provider:      {provider}")
    print(f"Batch size:    {batch_size}")
    print(f"Candidates:    {len(candidates)}")
    print(f"Total batches: {len(batches)}")
    print(f"Skip (resume): {skip_count}")
    print(f"Split:         {split or 'none'}")
    if domain_filter:
        print(f"Domain:        {domain_filter}")
    if dry_run:
        print(f"Mode:          DRY RUN")
    print(f"{'='*60}\n")

    total_scored = 0
    total_errors = 0

    for batch_idx, batch in enumerate(batches):
        if batch_idx < skip_count:
            continue

        global_batch_num = batch_idx + 1
        qa_ids = [r.get("qa_id", "") for r in batch]

        print(f"\n📦 Batch {global_batch_num}/{len(batches)} "
              f"({len(batch)} items, IDs: {qa_ids[0][:12]}...{qa_ids[-1][:12]})")

        # Build prompt
        prompt = build_scoring_prompt(batch, global_batch_num)
        prompt_chars = len(prompt)
        print(f"  📝 Prompt: {prompt_chars} chars (~{prompt_chars // 4} tokens)")

        if dry_run:
            print(f"  🔍 DRY RUN — skipping submission")
            print(f"  First 200 chars: {prompt[:200]}...")
            continue

        # Submit
        try:
            job_id = submit_scoring_job(prompt, provider, global_batch_num)
        except Exception as e:
            print(f"  ❌ Submit failed: {e}")
            total_errors += 1
            continue

        # Wait
        result = wait_for_job(job_id)

        if result.get("status") != "completed":
            print(f"  ❌ Job did not complete: {result.get('status')}")
            total_errors += 1
            progress["errors"] = total_errors
            progress["jobs"].append({
                "batch": global_batch_num,
                "job_id": job_id,
                "status": result.get("status"),
            })
            save_progress(progress)
            continue

        # Read answer
        answer_text = read_answer(job_id)
        if not answer_text:
            # Try preview
            answer_text = result.get("preview", "")

        if not answer_text:
            print(f"  ❌ Empty answer")
            total_errors += 1
            continue

        print(f"  📖 Answer: {len(answer_text)} chars")

        # Parse scores
        scored_items = parse_scoring_response(answer_text)
        print(f"  📊 Parsed {len(scored_items)} scores from response")

        if not scored_items:
            print(f"  ⚠️ Could not parse scores, saving raw answer")
            # Save raw answer for manual review
            raw_dir = Path(__file__).parent / "llm_scoring_prompts"
            raw_dir.mkdir(exist_ok=True)
            (raw_dir / f"raw_{provider}_batch_{global_batch_num:03d}.md").write_text(
                answer_text, encoding="utf-8"
            )
            total_errors += 1
            continue

        # Validate scores
        valid_items = []
        for item in scored_items:
            if item.get("qa_id") and item.get("overall"):
                valid_items.append(item)
            else:
                print(f"  ⚠️ Skipping incomplete item: {item.get('qa_id', '?')}")

        # Save to JSONL
        saved = save_scores(valid_items, provider)
        total_scored += saved
        print(f"  ✅ Saved {saved} scores")

        # Update progress
        progress["completed_batches"] = batch_idx + 1
        progress["completed_batch_indices"].append(global_batch_num)
        progress["total_scored"] = total_scored
        progress["errors"] = total_errors
        progress["jobs"].append({
            "batch": global_batch_num,
            "job_id": job_id,
            "status": "completed",
            "scored": saved,
        })
        save_progress(progress)

    # Summary
    print(f"\n{'='*60}")
    print(f"🏁 Batch Scoring Complete")
    print(f"{'='*60}")
    print(f"Batches run: {len(batches) - skip_count}")
    print(f"Total scored: {total_scored}")
    print(f"Errors:      {total_errors}")
    print(f"Progress saved to: {PROGRESS_FILE}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Batch Q&A scoring via ChatgptREST API"
    )
    parser.add_argument("--provider", choices=["chatgpt", "gemini"],
                        required=True, help="LLM provider")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    parser.add_argument("--max-batches", type=int, default=0,
                        help="Max batches to run (0=all)")
    parser.add_argument("--domain", type=str, default="",
                        help="Filter by domain")
    parser.add_argument("--split", choices=["odd", "even", ""],
                        default="", help="Split mode for parallel runs")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate prompts only, don't submit")
    parser.add_argument("--reset-progress", action="store_true",
                        help="Reset progress tracking")
    args = parser.parse_args()

    if args.reset_progress and PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        print("Progress reset.")

    run_batch_scoring(
        provider=args.provider,
        batch_size=args.batch_size,
        max_batches=args.max_batches,
        domain_filter=args.domain,
        split=args.split,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
