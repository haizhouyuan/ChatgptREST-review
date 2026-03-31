from __future__ import annotations

import os
from pathlib import Path


def _gemini_output_dir() -> Path:
    raw = (os.environ.get("GEMINI_OUTPUT_DIR") or os.environ.get("GEMINI_IMAGE_DIR") or "artifacts").strip()
    return Path(raw).expanduser()
