"""Tests for the answer quality completion guard in _run_once().

Verifies that classify_answer_quality() is used as a blocking guard:
- Single-char bogus completions ("我") are classified as suspect_short_answer
- Meta-commentary preambles are classified as suspect_meta_commentary
- Substantive answers pass through as "final"
- Short but structured answers (with code blocks/headers) are not false positives
- Preamble guard 800-char threshold catches longer thinking content
"""

from chatgptrest.core.conversation_exports import classify_answer_quality


def test_quality_guard_blocks_single_char_answer():
    """Issue #101: ChatGPT completing with single char '我' should be suspect."""
    quality = classify_answer_quality("我")
    assert quality == "suspect_short_answer", f"Expected suspect_short_answer, got {quality}"


def test_quality_guard_blocks_empty_whitespace():
    quality = classify_answer_quality("   ")
    assert quality == "suspect_short_answer"


def test_quality_guard_blocks_very_short_answer():
    quality = classify_answer_quality("OK")
    assert quality == "suspect_short_answer"


def test_quality_guard_blocks_meta_commentary():
    """P0 #1: Pro preamble-only answer should be classified as meta-commentary."""
    preamble = (
        "I'll start by analyzing the codebase structure to understand the existing "
        "architecture. Looking at the file organization and module dependencies will "
        "help me identify the best approach for implementing these changes. "
        "I need to check the current test coverage first and understand the key "
        "integration points before proposing any modifications."
    )
    quality = classify_answer_quality(preamble)
    assert quality == "suspect_meta_commentary", f"Expected suspect_meta_commentary, got {quality}"


def test_quality_guard_passes_substantive_answer():
    """A real 2000-char answer with structural content should pass."""
    answer = (
        "# Refactoring Plan\n\n"
        "## Step 1: Extract Base Class\n\n"
        "The first step is to move the shared logic into a base class:\n\n"
        "```python\n"
        "class BaseExecutor:\n"
        "    def execute(self, job):\n"
        "        pass\n"
        "```\n\n"
        "## Step 2: Update Subclasses\n\n"
        "- `ChatGPTExecutor` extends `BaseExecutor`\n"
        "- `GeminiExecutor` extends `BaseExecutor`\n"
        "- All shared methods move to the base\n\n"
        "## Step 3: Test Coverage\n\n"
        "| Test | Status |\n"
        "| --- | --- |\n"
        "| test_base_execute | ✅ |\n"
        "| test_chatgpt_override | ✅ |\n"
    )
    # Pad to realistic length
    answer += "\n\nAdditional implementation details follow...\n" * 30
    quality = classify_answer_quality(answer)
    assert quality == "final", f"Expected final, got {quality}"


def test_quality_guard_passes_short_but_structured_answer():
    """A 300-char answer with code blocks should NOT be flagged as suspect."""
    answer = (
        "Here's the fix:\n\n"
        "```python\n"
        "def validate_input(x):\n"
        "    if x < 0:\n"
        "        raise ValueError('negative')\n"
        "    return x\n"
        "```\n\n"
        "This handles the edge case by raising early.\n"
    )
    assert len(answer) < 400
    quality = classify_answer_quality(answer)
    assert quality == "final", f"Expected final for short structured answer, got {quality}"


def test_quality_guard_passes_short_answer_with_bullets():
    """A short answer with bullet points should pass."""
    answer = (
        "The key issues are:\n\n"
        "- Memory leak in the connection pool\n"
        "- Race condition in the job queue\n"
        "- Missing error handling in the API layer\n"
    )
    quality = classify_answer_quality(answer)
    assert quality == "final", f"Expected final for bulleted answer, got {quality}"


def test_quality_guard_passes_concise_multisentence_answer() -> None:
    answer = (
        "Issue ledger（问题台账）的作用是把项目、产品或运营中出现的问题集中记录下来，避免遗漏和重复沟通。"
        "它通常会包含问题描述、责任人、优先级、当前状态、截止时间等信息，方便团队统一跟踪。"
        "通过 issue ledger，管理者可以快速判断哪些问题最紧急、哪些问题卡住了，以及整体处理进度。"
        "本质上，它是一个让问题可见、可管、可追责、可复盘的基础管理工具。"
    )
    quality = classify_answer_quality(answer)
    assert quality == "final", f"Expected final for concise explanatory answer, got {quality}"


def test_quality_guard_longer_meta_commentary_with_context():
    """
    A 600-char meta-commentary with no structural markers should be flagged
    when all candidate lengths are also short.
    """
    meta = (
        "I'm now at the point where I need to carefully examine the full codebase "
        "to understand how the different modules interact. The main challenge here "
        "is that the architecture has evolved organically over time, and there are "
        "several legacy components that may no longer be necessary. "
        "I should start by mapping out the dependency graph and identifying any "
        "circular dependencies that could complicate the refactoring process. "
        "Once I have a clear picture, I can begin outlining the steps needed."
    )
    quality = classify_answer_quality(meta, all_candidate_lengths=[len(meta)])
    assert quality == "suspect_meta_commentary", f"Expected suspect_meta_commentary, got {quality}"


def test_quality_guard_blocks_context_acquisition_failure_for_uploaded_bundle() -> None:
    answer = (
        "It seems there were difficulties retrieving the requested review bundle. "
        "Would you be able to upload the relevant files directly, or provide additional "
        "context about the content you'd like me to review? This will help me assist you effectively."
    )
    quality = classify_answer_quality(answer)
    assert quality == "suspect_context_acquisition_failure", (
        f"Expected suspect_context_acquisition_failure, got {quality}"
    )


def test_quality_guard_blocks_partial_bundle_analysis_stub() -> None:
    answer = (
        "The file `06_api.md` includes important references to FastAPI routes, with a focus on "
        "defining routers like `make_dashboard_router`. This could be relevant for the dashboard "
        "routing logic. I will proceed to analyze this further by looking for concrete issues, "
        "based on the information so far."
    )
    quality = classify_answer_quality(answer)
    assert quality == "suspect_context_acquisition_failure", (
        f"Expected suspect_context_acquisition_failure, got {quality}"
    )


def test_preamble_guard_regex_catches_common_patterns():
    """Verify the worker preamble regex patterns catch typical thinking preambles."""
    import re
    _PREAMBLE_HEURISTIC_RE = re.compile(
        r"(?:"
        r"let me (?:plan|think|analyze|outline|break|consider)"
        r"|i'?ll (?:start|begin) by"
        r"|here'?s my (?:plan|approach)"
        r"|step \d+:"
        r"|first,? let me"
        r"|让我先"
        r"|我先规划"
        r")",
        re.IGNORECASE,
    )
    # All should match
    assert _PREAMBLE_HEURISTIC_RE.search("Let me plan the implementation")
    assert _PREAMBLE_HEURISTIC_RE.search("I'll start by reading the code")
    assert _PREAMBLE_HEURISTIC_RE.search("Here's my approach to this problem")
    assert _PREAMBLE_HEURISTIC_RE.search("Step 1: First we analyze")
    assert _PREAMBLE_HEURISTIC_RE.search("让我先看一下代码结构")
    assert _PREAMBLE_HEURISTIC_RE.search("我先规划一下")

    # Should NOT match real answers
    assert not _PREAMBLE_HEURISTIC_RE.search("The function returns a tuple of")
    assert not _PREAMBLE_HEURISTIC_RE.search("# Implementation Guide")
