from __future__ import annotations

import sys
from pathlib import Path

from chatgptrest.mcp import server


def test_mcp_autostart_prefers_repo_venv_python_when_present() -> None:
    venv_bin = (server._REPO_ROOT / ".venv" / "bin" / "python").resolve(strict=False)
    got = Path(server._preferred_api_python_bin())
    if venv_bin.exists():
        assert got == venv_bin
    else:
        assert str(got) == str(sys.executable)

