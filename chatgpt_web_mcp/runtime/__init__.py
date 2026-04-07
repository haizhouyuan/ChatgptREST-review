"""Driver runtime helpers.

These modules host shared state and primitives that are used across provider
implementations (ChatGPT/Gemini/Qwen). Keeping them outside the legacy
`_tools_impl.py` makes large refactors safer and easier to review.
"""
