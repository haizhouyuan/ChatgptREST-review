from __future__ import annotations

import ast
from pathlib import Path


def _imports_tools_impl(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "chatgpt_web_mcp._tools_impl" or name.endswith(".chatgpt_web_mcp._tools_impl"):
                    return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            level = int(getattr(node, "level", 0) or 0)

            if mod == "chatgpt_web_mcp._tools_impl" or mod.endswith(".chatgpt_web_mcp._tools_impl"):
                return True

            # Common absolute bypass: `from chatgpt_web_mcp import _tools_impl`.
            if level == 0 and mod == "chatgpt_web_mcp":
                if any(alias.name == "_tools_impl" for alias in node.names):
                    return True

            # Common relative bypasses inside the providers package.
            if level >= 1:
                if mod in {"", None} and any(alias.name == "_tools_impl" for alias in node.names):
                    return True
                if mod == "_tools_impl":
                    return True
                if mod.endswith("._tools_impl"):
                    return True

    return False


def test_provider_modules_do_not_import_tools_impl() -> None:
    providers_dir = Path("chatgpt_web_mcp/providers")
    paths = sorted(p for p in providers_dir.glob("*.py") if p.name != "__init__.py")
    assert paths, "No provider modules found to scan."

    offenders: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _imports_tools_impl(tree):
            offenders.append(str(path))

    assert not offenders, "Provider modules must not import chatgpt_web_mcp._tools_impl: " + ", ".join(offenders)
