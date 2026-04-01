#!/usr/bin/env python3
"""
Best-effort helper to click Cloudflare Turnstile in the current CDP Chrome session.

This does not bypass Cloudflare; it only automates the same click a human would do
in noVNC. It is useful when the challenge checkbox is visible but tedious to operate.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.request
from dataclasses import dataclass

from playwright.async_api import async_playwright


def _resolve_ws_url(cdp_url: str) -> str:
    if cdp_url.startswith("ws://") or cdp_url.startswith("wss://"):
        return cdp_url
    base = cdp_url.rstrip("/")
    with urllib.request.urlopen(f"{base}/json/version", timeout=10) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    ws = str(payload.get("webSocketDebuggerUrl") or "").strip()
    if not ws:
        raise RuntimeError(f"Missing webSocketDebuggerUrl from {base}/json/version")
    return ws


def _is_blocked_title_or_url(title: str, url: str) -> bool:
    t = (title or "").lower()
    u = (url or "").lower()
    if "just a moment" in t:
        return True
    if "__cf_chl_" in u or "/cdn-cgi/challenge-platform/" in u:
        return True
    return False


@dataclass
class AttemptResult:
    clicked: bool
    where: str
    title_before: str
    url_before: str
    title_after: str
    url_after: str


async def _find_turnstile_frame(page, timeout_seconds: float):
    start = time.time()
    while (time.time() - start) < timeout_seconds:
        for frame in page.frames:
            url = (frame.url or "").lower()
            if "challenges.cloudflare.com" in url and "turnstile" in url:
                return frame
        await page.wait_for_timeout(300)
    return None


async def _attempt_click(page, wait_frame_seconds: float) -> tuple[bool, str]:
    frame = await _find_turnstile_frame(page, timeout_seconds=wait_frame_seconds)
    if frame is not None:
        try:
            box = await frame.locator("body").bounding_box()
        except Exception:
            box = None
        if box:
            await page.mouse.click(box["x"] + box["width"] / 2.0, box["y"] + box["height"] / 2.0)
            return True, "turnstile-frame-center"
    try:
        box = await page.locator("body").bounding_box()
    except Exception:
        box = None
    if box:
        await page.mouse.click(box["x"] + box["width"] / 2.0, box["y"] + min(420.0, box["height"] / 2.0))
        return True, "page-fallback-center"
    return False, "no-click-target"


async def run(args: argparse.Namespace) -> int:
    ws_url = _resolve_ws_url(args.cdp_url)
    print(f"[cf-click-assist] cdp={args.cdp_url}")
    print(f"[cf-click-assist] ws={ws_url}")

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(ws_url)
        if browser.contexts:
            context = browser.contexts[0]
            created_context = False
        else:
            context = await browser.new_context()
            created_context = True

        if context.pages:
            page = context.pages[0]
            created_page = False
        else:
            page = await context.new_page()
            created_page = True

        if args.navigate:
            await page.goto(args.url, wait_until="domcontentloaded", timeout=int(args.goto_timeout_seconds * 1000))
            await page.wait_for_timeout(int(args.settle_before_click_seconds * 1000))

        results: list[AttemptResult] = []

        for i in range(1, args.max_clicks + 1):
            title_before = (await page.title()).strip()
            url_before = page.url
            blocked_before = _is_blocked_title_or_url(title_before, url_before)
            print(
                f"[cf-click-assist] attempt={i} before title={title_before!r} "
                f"url={url_before!r} blocked_like={blocked_before}"
            )
            if not blocked_before:
                print("[cf-click-assist] page does not look blocked; stop.")
                if created_page:
                    await page.close()
                if created_context:
                    await context.close()
                return 0

            clicked, where = await _attempt_click(page, wait_frame_seconds=args.wait_frame_seconds)
            await page.wait_for_timeout(int(args.settle_after_click_seconds * 1000))

            title_after = (await page.title()).strip()
            url_after = page.url
            blocked_after = _is_blocked_title_or_url(title_after, url_after)
            results.append(
                AttemptResult(
                    clicked=clicked,
                    where=where,
                    title_before=title_before,
                    url_before=url_before,
                    title_after=title_after,
                    url_after=url_after,
                )
            )
            print(
                f"[cf-click-assist] attempt={i} clicked={clicked} where={where} "
                f"after title={title_after!r} url={url_after!r} blocked_like={blocked_after}"
            )
            if clicked and (not blocked_after):
                print("[cf-click-assist] looks unblocked after click.")
                if created_page:
                    await page.close()
                if created_context:
                    await context.close()
                return 0

        print("[cf-click-assist] still blocked after all attempts.")
        if created_page:
            await page.close()
        if created_context:
            await context.close()
        return 10


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Best-effort Cloudflare turnstile click helper for ChatGPT CDP Chrome")
    ap.add_argument("--cdp-url", default="http://127.0.0.1:9222", help="CDP endpoint (http://host:port or ws://...)")
    ap.add_argument("--url", default="https://chatgpt.com/", help="Target URL to open before clicking")
    ap.add_argument("--max-clicks", type=int, default=4, help="Max click attempts")
    ap.add_argument("--wait-frame-seconds", type=float, default=8.0, help="Per-attempt wait for turnstile frame")
    ap.add_argument("--settle-before-click-seconds", type=float, default=2.0, help="Wait after initial navigation")
    ap.add_argument("--settle-after-click-seconds", type=float, default=5.0, help="Wait after each click")
    ap.add_argument("--goto-timeout-seconds", type=float, default=120.0, help="Navigation timeout")
    ap.add_argument("--no-navigate", dest="navigate", action="store_false", help="Use current page without navigation")
    ap.set_defaults(navigate=True)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"[cf-click-assist] error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

