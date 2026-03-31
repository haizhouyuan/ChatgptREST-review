"""Plane detection — identify which planes are relevant to a task.

Uses keyword matching against plane_registry.yaml to rank planes by confidence.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def detect_planes(
    task_description: str = "",
    changed_files: list[str] | None = None,
    goal_hint: str = "",
) -> list[dict[str, Any]]:
    """Detect relevant planes for a task.

    Args:
        task_description: Natural language task description
        changed_files: List of changed file paths
        goal_hint: Optional goal hint (e.g., "execution", "public_agent")

    Returns:
        List of detected planes with confidence scores, sorted by confidence desc.
        [
            {"plane": "public_agent", "confidence": 0.9, "reason": "..."},
            {"plane": "execution", "confidence": 0.6, "reason": "..."},
            ...
        ]
    """
    registry_path = REPO_ROOT / "ops" / "registries" / "plane_registry.yaml"
    if not registry_path.exists():
        return []

    with open(registry_path) as f:
        data = yaml.safe_load(f)

    planes = data.get("planes", {})
    scores: dict[str, float] = {}
    reasons: dict[str, list[str]] = {}

    # Combine all text for keyword matching
    text = f"{task_description} {goal_hint}".lower()

    for plane_name, plane_data in planes.items():
        score = 0.0
        plane_reasons = []

        # Keyword matching
        keywords = plane_data.get("keywords", [])
        matched_keywords = [kw for kw in keywords if kw.lower() in text]
        if matched_keywords:
            score += len(matched_keywords) * 0.1
            plane_reasons.append(f"keywords: {', '.join(matched_keywords[:5])}")

        # File path matching
        if changed_files:
            key_dirs = plane_data.get("key_dirs", [])
            matched_files = []
            for file_path in changed_files:
                for key_dir in key_dirs:
                    if key_dir in file_path:
                        matched_files.append(file_path)
                        break
            if matched_files:
                score += len(matched_files) * 0.3
                plane_reasons.append(f"files: {', '.join(matched_files[:3])}")

        # Goal hint exact match
        if goal_hint.lower() == plane_name.lower():
            score += 1.0
            plane_reasons.append("goal_hint exact match")

        if score > 0:
            scores[plane_name] = min(score, 1.0)  # Cap at 1.0
            reasons[plane_name] = plane_reasons

    # Sort by score descending
    results = [
        {
            "plane": plane,
            "confidence": scores[plane],
            "reason": "; ".join(reasons[plane]),
        }
        for plane in sorted(scores.keys(), key=lambda p: scores[p], reverse=True)
    ]

    return results
