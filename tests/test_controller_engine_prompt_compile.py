from __future__ import annotations

from chatgptrest.controller.engine import ControllerEngine


def test_build_enriched_question_prefers_compiled_prompt() -> None:
    engine = ControllerEngine({})

    question = engine._build_enriched_question(
        question="raw question",
        stable_context={
            "compiled_prompt": {
                "user_prompt": "compiled question body",
            }
        },
        kb_chunks=[],
    )

    assert question == "compiled question body"


def test_build_enriched_question_falls_back_to_raw_question() -> None:
    engine = ControllerEngine({})

    question = engine._build_enriched_question(
        question="raw question",
        stable_context={},
        kb_chunks=[],
    )

    assert question == "raw question"
