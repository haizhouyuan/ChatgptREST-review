from __future__ import annotations

import pytest

from chatgptrest.core import issue_family_registry as registry_mod


@pytest.mark.parametrize(
    ("issue", "expected_id", "expected_label"),
    [
        (
            {
                "kind": "gemini_web.ask",
                "symptom": "WaitNoThreadUrlTimeout: wait phase timed out without stable conversation_url",
                "metadata": {"family_id": "gemini_no_thread_url"},
            },
            "gemini_no_thread_url",
            "Gemini wait / no thread URL",
        ),
        (
            {
                "kind": "gemini_web.ask",
                "symptom": "WaitNoThreadUrlTimeout: wait phase timed out without stable conversation_url",
                "family_id": "gemini_followup_thread_handoff",
            },
            "gemini_no_thread_url",
            "Gemini wait / no thread URL",
        ),
        (
            {
                "kind": "gemini_web.ask",
                "symptom": "WaitNoProgressTimeout: wait phase made no progress",
                "metadata": {"family_id": "gemini_wait_no_progress"},
            },
            "gemini_stable_thread_no_progress",
            "Gemini wait / stable thread no progress",
        ),
        (
            {
                "kind": "gemini_web.ask",
                "symptom": "WaitNoProgressTimeout: wait phase made no progress",
                "metadata": {"family_id": "gemini_stable_thread_no_progress"},
            },
            "gemini_stable_thread_no_progress",
            "Gemini wait / stable thread no progress",
        ),
    ],
)
def test_issue_family_registry_normalizes_gemini_wait_families(
    issue: dict[str, object],
    expected_id: str,
    expected_label: str,
) -> None:
    registry_mod.load_issue_family_registry.cache_clear()
    family_id, family_label = registry_mod.match_issue_family(issue)
    assert family_id == expected_id
    assert family_label == expected_label
