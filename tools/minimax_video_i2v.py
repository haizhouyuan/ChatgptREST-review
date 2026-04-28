#!/usr/bin/env python3
import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


def request_json(method: str, url: str, api_key: str, body: dict | None = None, timeout: int = 120) -> dict:
    data = None
    headers = {"Authorization": f"Bearer {api_key}"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    return json.loads(raw)


def check_base_resp(response: dict) -> None:
    base = response.get("base_resp") or {}
    status_code = base.get("status_code", 0)
    if status_code not in (0, "0", None):
        raise RuntimeError(f"MiniMax API error {status_code}: {base.get('status_msg', 'unknown')}")


def image_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit and poll a MiniMax image-to-video task.")
    parser.add_argument("--first-frame", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="MiniMax-Hailuo-2.3-Fast")
    parser.add_argument("--duration", type=int, default=6)
    parser.add_argument("--resolution", default="768P")
    parser.add_argument("--prompt-optimizer", action="store_true")
    parser.add_argument("--fast-pretreatment", action="store_true")
    parser.add_argument("--aigc-watermark", action="store_true")
    parser.add_argument("--poll-interval", type=int, default=10)
    parser.add_argument("--max-wait", type=int, default=600)
    args = parser.parse_args()

    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY is not set")
    api_host = os.environ.get("MINIMAX_API_HOST", "https://api.minimaxi.com").rstrip("/")
    base_url = f"{api_host}/v1"

    first_frame = Path(args.first_frame)
    if not first_frame.is_file():
        raise RuntimeError(f"first frame not found: {first_frame}")

    payload = {
        "model": args.model,
        "prompt": args.prompt,
        "duration": args.duration,
        "resolution": args.resolution,
        "first_frame_image": image_data_url(first_frame),
        "prompt_optimizer": bool(args.prompt_optimizer),
        "fast_pretreatment": bool(args.fast_pretreatment),
        "aigc_watermark": bool(args.aigc_watermark),
    }

    print("Creating video generation task...", file=sys.stderr)
    created = request_json("POST", f"{base_url}/video_generation", api_key, payload)
    check_base_resp(created)
    task_id = created.get("task_id")
    if not task_id:
        raise RuntimeError(f"no task_id in response: {created}")
    print(f"Task created: {task_id}", file=sys.stderr)

    started = time.time()
    file_id = None
    while time.time() - started <= args.max_wait:
        query = urllib.parse.urlencode({"task_id": task_id})
        response = request_json("GET", f"{base_url}/query/video_generation?{query}", api_key)
        status = response.get("status", "Unknown")
        elapsed = int(time.time() - started)
        print(f"  [{elapsed}s] Status: {status}", file=sys.stderr)
        if status == "Success":
            file_id = response.get("file_id")
            if not file_id:
                raise RuntimeError(f"task succeeded without file_id: {response}")
            break
        if status in {"Fail", "Failed", "Error"}:
            check_base_resp(response)
            raise RuntimeError(f"task failed: {response}")
        time.sleep(args.poll_interval)

    if not file_id:
        raise RuntimeError(f"task timed out after {args.max_wait}s: {task_id}")

    query = urllib.parse.urlencode({"file_id": file_id})
    retrieved = request_json("GET", f"{base_url}/files/retrieve?{query}", api_key)
    check_base_resp(retrieved)
    download_url = ((retrieved.get("file") or {}).get("download_url")) or ""
    if not download_url:
        raise RuntimeError(f"no download_url in file response: {retrieved}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    print("Downloading video...", file=sys.stderr)
    with urllib.request.urlopen(download_url, timeout=180) as resp:
        output.write_bytes(resp.read())
    print(f"Video saved to: {output} ({output.stat().st_size} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
