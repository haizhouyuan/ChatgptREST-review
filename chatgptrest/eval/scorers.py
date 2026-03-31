"""Scorers — evaluation metrics for comparing predictions to references."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class Scorer(ABC):
    """Abstract base class for scorers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the scorer."""
        pass

    @abstractmethod
    def score(self, prediction: str, reference: str) -> float:
        """Score a prediction against a reference.

        Args:
            prediction: The model's output
            reference: The expected/gold-standard output

        Returns:
            Score (higher is better, typically 0-1 or 0-100)
        """
        pass


class RougeScorer(Scorer):
    """ROUGE-L score (longest common subsequence)."""

    def __init__(self) -> None:
        try:
            import rouge_score
            self._rouge = rouge_score
        except ImportError:
            self._rouge = None

    @property
    def name(self) -> str:
        return "rouge_l"

    def score(self, prediction: str, reference: str) -> float:
        """Calculate ROUGE-L score."""
        if not prediction or not reference:
            return 0.0

        if self._rouge is None:
            # Fallback: simple LCS-based approximation
            return self._lcs_score(prediction, reference)

        try:
            scorer = self._rouge.RougeScorer(
                ['rougeL'], use_stemmer=True
            )
            scores = scorer.score(reference, prediction)
            return scores['rougeL'].fmeasure
        except Exception:
            return self._lcs_score(prediction, reference)

    def _lcs_score(self, pred: str, reference: str) -> float:
        """Simple LCS-based fallback."""
        pred_tokens = pred.lower().split()
        ref_tokens = reference.lower().split()

        # Build LCS table
        m, n = len(pred_tokens), len(ref_tokens)
        if m == 0 or n == 0:
            return 0.0

        dp = [[0] * (n + 1) for _ in range(2)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if pred_tokens[i-1] == ref_tokens[j-1]:
                    dp[i % 2][j] = dp[(i-1) % 2][j-1] + 1
                else:
                    dp[i % 2][j] = max(dp[(i-1) % 2][j], dp[i % 2][j-1])

        lcs_len = dp[m % 2][n]
        return lcs_len / max(m, n) if max(m, n) > 0 else 0.0


class SemanticSimilarityScorer(Scorer):
    """Semantic similarity using embeddings."""

    def __init__(self) -> None:
        self._model = None

    @property
    def name(self) -> str:
        return "semantic_similarity"

    def _get_model(self):
        """Lazy-load embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer('all-MiniLM-L6-v2')
            except ImportError:
                pass
        return self._model

    def score(self, prediction: str, reference: str) -> float:
        """Calculate semantic similarity score."""
        if not prediction or not reference:
            return 0.0

        model = self._get_model()
        if model is None:
            # Fallback: word overlap
            return self._word_overlap(prediction, reference)

        try:
            embeddings = model.encode([prediction, reference])
            pred_emb = embeddings[0]
            ref_emb = embeddings[1]

            # Cosine similarity
            dot = np.dot(pred_emb, ref_emb)
            norm_pred = np.linalg.norm(pred_emb)
            norm_ref = np.linalg.norm(ref_emb)

            if norm_pred == 0 or norm_ref == 0:
                return 0.0

            return float(dot / (norm_pred * norm_ref))
        except Exception:
            return self._word_overlap(prediction, reference)

    def _word_overlap(self, pred: str, reference: str) -> float:
        """Simple word overlap fallback."""
        pred_words = set(pred.lower().split())
        ref_words = set(reference.lower().split())

        if not pred_words or not ref_words:
            return 0.0

        intersection = pred_words & ref_words
        return len(intersection) / max(len(pred_words), len(ref_words))


class LLMJudgeScorer(Scorer):
    """LLM-as-judge scoring using an external LLM."""

    def __init__(self, judge_model: str = "qwen3-coder-plus") -> None:
        self.judge_model = judge_model

    @property
    def name(self) -> str:
        return f"llm_judge_{self.judge_model}"

    def score(self, prediction: str, reference: str) -> float:
        """Score using LLM judge.

        This is a placeholder - in production, call the LLM to evaluate.
        """
        # Placeholder implementation
        # In production, this would call the LLM connector
        if not prediction or not reference:
            return 0.0

        # Simple length and keyword overlap as placeholder
        overlap = self._word_overlap(prediction, reference)
        return overlap

    def _word_overlap(self, pred: str, reference: str) -> float:
        """Simple word overlap fallback."""
        pred_words = set(pred.lower().split())
        ref_words = set(reference.lower().split())

        if not pred_words or not ref_words:
            return 0.0

        intersection = pred_words & ref_words
        return len(intersection) / max(len(pred_words), len(ref_words))
