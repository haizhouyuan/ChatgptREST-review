"""Eval Datasets — test data management for evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EvalItem:
    """A single evaluation item with input, expected output, and reference."""
    input: str
    expected_intent: str = ""
    expected_route: str = ""
    reference_answer: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class EvalDataset:
    """Collection of EvalItems for evaluation.

    Usage::

        dataset = EvalDataset.from_file("eval_datasets/default.json")
        dataset = EvalDataset(items=[...])
    """

    def __init__(self, name: str, items: list[EvalItem]) -> None:
        self.name = name
        self.items = items

    @classmethod
    def from_file(cls, path: str | Path) -> EvalDataset:
        """Load dataset from JSON file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Dataset not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        name = data.get("name", path.stem)
        items = [
            EvalItem(
                input=item["input"],
                expected_intent=item.get("expected_intent", ""),
                expected_route=item.get("expected_route", ""),
                reference_answer=item.get("reference_answer", ""),
                metadata=item.get("metadata", {}),
            )
            for item in data.get("items", [])
        ]
        return cls(name=name, items=items)

    def save(self, path: str | Path) -> None:
        """Save dataset to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "name": self.name,
            "items": [
                {
                    "input": item.input,
                    "expected_intent": item.expected_intent,
                    "expected_route": item.expected_route,
                    "reference_answer": item.reference_answer,
                    "metadata": item.metadata,
                }
                for item in self.items
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)
