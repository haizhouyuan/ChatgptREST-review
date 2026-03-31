import ast
import inspect

import chatgpt_web_mcp.server as server


def _extract_list_literals(tree: ast.AST, *, func_name: str, var_name: str) -> list[str]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        if node.name != func_name:
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            if len(stmt.targets) != 1:
                continue
            target = stmt.targets[0]
            if not isinstance(target, ast.Name) or target.id != var_name:
                continue
            if not isinstance(stmt.value, ast.List):
                continue
            items: list[str] = []
            for elt in stmt.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    items.append(elt.value)
            return items
    raise AssertionError(f"Could not find literal list assignment {func_name}.{var_name}")


def test_gemini_open_tools_drawer_supports_mode_menu_trigger() -> None:
    src = inspect.getsource(server._gemini_open_tools_drawer)
    tree = ast.parse(src)

    tools_btn_candidates = _extract_list_literals(
        tree,
        func_name="_gemini_open_tools_drawer",
        var_name="tools_btn_candidates",
    )
    assert "[data-test-id='bard-mode-menu-button']" in tools_btn_candidates
    assert "[data-test-id='bard-mode-menu-button'] button" in tools_btn_candidates

    open_markers = _extract_list_literals(tree, func_name="_gemini_open_tools_drawer", var_name="open_markers")
    assert "[data-test-id='bard-mode-menu-button'][aria-expanded='true']" in open_markers
    assert "button.toolbox-drawer-button[aria-expanded='true']" in open_markers
    assert "div.cdk-overlay-container:visible [role='menuitemcheckbox']" in open_markers
    assert "div.cdk-overlay-pane:visible [role='menuitemcheckbox']" in open_markers
    assert "text=Deep Research" not in open_markers
