"""MCP tool entrypoints (stable names, thin wrappers).

These modules define `@mcp.tool(...)` functions and delegate into provider/runtime
implementations. Keeping tool entrypoints small makes refactors safer and keeps
the tool registry snapshot-testable.
"""
