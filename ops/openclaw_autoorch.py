#!/usr/bin/env python3
"""Compatibility wrapper for the old autoorch CLI entrypoint.

`finbot` is now the canonical OpenClaw investment-research scout.
This script keeps the legacy command path working during migration.
"""

from __future__ import annotations

from openclaw_finbot import main


if __name__ == "__main__":
    raise SystemExit(main())
