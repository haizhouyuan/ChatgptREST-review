#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from google_auth_oauthlib.flow import InstalledAppFlow
from playwright.async_api import async_playwright


_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/tasks",
]

_CLICK_LABELS = [
    "继续",
    "Continue",
    "允许",
    "Allow",
    "下一步",
    "Next",
    "同意并继续",
    "同意",
    "Accept",
    "批准",
    "Approve",
]


async def _maybe_click_account_chooser(page: Any) -> bool:
    try:
        body_text = await page.locator("body").inner_text(timeout=2000)
    except Exception:
        return False
    if "请选择账号" not in body_text and "Choose an account" not in body_text:
        return False
    selectors = [
        "[data-identifier]",
        "li [data-identifier]",
        "div[role='link'][data-identifier]",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if await locator.count() > 0:
                target = locator.first
                if await target.is_visible():
                    await target.click()
                    return True
        except Exception:
            continue
    try:
        locator = page.get_by_text(r".+@.+", exact=False)
        if await locator.count() > 0 and await locator.first.is_visible():
            await locator.first.click()
            return True
    except Exception:
        return False
    return False


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass
class CallbackResult:
    authorization_response: str = ""
    error: str = ""


class _CallbackHandler(BaseHTTPRequestHandler):
    result: CallbackResult

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if query.get("error"):
            self.result.error = str(query.get("error", [""])[0])
        self.result.authorization_response = f"http://127.0.0.1:{self.server.server_port}{self.path}"  # type: ignore[attr-defined]
        body = (
            "<html><body><h1>Google Workspace authorization completed.</h1>"
            "<p>You can close this tab now.</p></body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _start_callback_server(port: int) -> tuple[HTTPServer, CallbackResult, threading.Thread]:
    result = CallbackResult()

    class _BoundHandler(_CallbackHandler):
        pass

    _BoundHandler.result = result
    server = HTTPServer(("127.0.0.1", port), _BoundHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    return server, result, thread


async def _click_if_present(page: Any, label: str) -> bool:
    candidates = [
        page.get_by_role("button", name=label, exact=False),
        page.get_by_role("link", name=label, exact=False),
        page.get_by_text(label, exact=False),
    ]
    for locator in candidates:
        try:
            if await locator.count() > 0:
                target = locator.first
                if await target.is_visible():
                    await target.click()
                    return True
        except Exception:
            continue
    return False


async def _complete_google_warning_page(page: Any) -> bool:
    # Google renders this unverified-app screen inside components that do not
    # reliably expose normal button selectors. The "continue" button consistently
    # carries the `eR0mzb` class in the live flow, and Playwright can pierce
    # the component tree for this selector.
    try:
        locator = page.locator(".eR0mzb")
        if await locator.count() > 0:
            await locator.first.click(timeout=3000)
            return True
    except Exception:
        return False
    return False


async def _accept_google_workspace_scopes(page: Any) -> bool:
    try:
        boxes = page.locator("input[type=checkbox]")
        count = await boxes.count()
        if count <= 0:
            return False
        for i in range(count):
            box = boxes.nth(i)
            if not await box.is_checked():
                await box.check(force=True)
        continue_locator = page.get_by_text("继续", exact=False)
        if await continue_locator.count() > 0:
            await continue_locator.first.click(timeout=3000)
            return True
    except Exception:
        return False
    return False


async def _complete_google_flow_via_cdp(*, cdp_url: str, auth_url: str, timeout_seconds: float) -> None:
    deadline = asyncio.get_running_loop().time() + max(30.0, float(timeout_seconds))
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url)
        try:
            if not browser.contexts:
                raise RuntimeError("No existing Chrome context available on the configured CDP endpoint.")
            context = browser.contexts[0]
            page = await context.new_page()
            try:
                await page.goto(auth_url, wait_until="domcontentloaded", timeout=30000)
                while asyncio.get_running_loop().time() < deadline:
                    if page.url.startswith("http://127.0.0.1:"):
                        return
                    try:
                        body_text = await page.locator("body").inner_text(timeout=2000)
                    except Exception:
                        body_text = ""
                    if "此应用未经 Google 验证" in body_text or "This app isn’t verified" in body_text:
                        if await _complete_google_warning_page(page):
                            await page.wait_for_timeout(1500)
                            continue
                    if "想要访问您的 Google 账号" in body_text or "wants to access your Google Account" in body_text:
                        if await _accept_google_workspace_scopes(page):
                            await page.wait_for_timeout(1500)
                            continue
                    if await _maybe_click_account_chooser(page):
                        await page.wait_for_timeout(2000)
                        if page.url.startswith("http://127.0.0.1:"):
                            return
                    for label in _CLICK_LABELS:
                        clicked = await _click_if_present(page, label)
                        if clicked:
                            await page.wait_for_timeout(1500)
                            break
                    if page.url.startswith("http://127.0.0.1:"):
                        return
                    await page.wait_for_timeout(1000)
                raise TimeoutError("Timed out waiting for Google Workspace OAuth flow to finish.")
            finally:
                await page.close()
        finally:
            await browser.close()


def run_reauth(*, credentials_path: Path, token_path: Path, cdp_url: str, timeout_seconds: float) -> dict[str, Any]:
    port = _find_free_port()
    redirect_uri = f"http://127.0.0.1:{port}/"
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), _SCOPES)
    flow.redirect_uri = redirect_uri
    auth_url, _state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    server, callback, thread = _start_callback_server(port)
    try:
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
        asyncio.run(_complete_google_flow_via_cdp(cdp_url=cdp_url, auth_url=auth_url, timeout_seconds=timeout_seconds))
        thread.join(timeout=max(5.0, timeout_seconds))
        if callback.error:
            raise RuntimeError(f"Google authorization returned error: {callback.error}")
        if not callback.authorization_response:
            raise RuntimeError("Google authorization did not reach the local callback.")
        flow.fetch_token(authorization_response=callback.authorization_response)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(flow.credentials.to_json(), encoding="utf-8")
        return {
            "ok": True,
            "token_path": str(token_path),
            "redirect_uri": redirect_uri,
            "expiry": str(flow.credentials.expiry or ""),
        }
    finally:
        try:
            server.server_close()
        except Exception:
            pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Re-authorize Google Workspace token via the existing Chrome CDP session.")
    parser.add_argument(
        "--credentials-path",
        default=str(Path.home() / ".openmind" / "google_credentials.json"),
        help="Path to Google OAuth desktop-app credentials JSON",
    )
    parser.add_argument(
        "--token-path",
        default=str(Path.home() / ".openmind" / "google_token.json"),
        help="Path to write refreshed Google token JSON",
    )
    parser.add_argument(
        "--cdp-url",
        default="http://127.0.0.1:9226",
        help="Existing Chrome CDP endpoint carrying the logged-in Google session",
    )
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    result = run_reauth(
        credentials_path=Path(args.credentials_path).expanduser(),
        token_path=Path(args.token_path).expanduser(),
        cdp_url=str(args.cdp_url),
        timeout_seconds=float(args.timeout_seconds),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
