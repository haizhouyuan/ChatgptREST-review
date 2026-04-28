#!/usr/bin/env python3
"""Tiny static server with SPA fallback for local prototype review."""

from __future__ import annotations

import argparse
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class SPAHandler(SimpleHTTPRequestHandler):
    def send_head(self):  # noqa: N802 - stdlib override
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        if os.path.exists(path):
            return super().send_head()
        index = Path(self.directory) / "index.html"
        if index.exists():
            self.path = "/index.html"
            return super().send_head()
        return super().send_head()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    handler = lambda *h_args, **h_kwargs: SPAHandler(*h_args, directory=args.directory, **h_kwargs)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {args.directory} on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
