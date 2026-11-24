"""Historical 768D classifier; not part of the active V1 pipeline."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from gardirop_ai_clothing.contracts import (
    MAIN_CATEGORIES,
    NUM_CLASSES,
    TAXONOMY,
    VIEW_EMBEDDING_DIMENSION,
)

# Legacy 768D head. Parent LR migration is a later implementation step.
EMBEDDING_DIM = VIEW_EMBEDDING_DIMENSION


@dataclass(frozen=True)
class ClassCandidate:
    class_id: int
    name: str
    score: float


@dataclass(frozen=True)
class ClassificationResult:
    class_id: int
    main_category: str
    sub_category: str
    score: float
    alternatives: tuple[ClassCandidate, ...]


class CategoryClassifier:
    """CPU-only classifier for normalized Marqo embeddings."""

    def __init__(
        self,
        weights: np.ndarray,
        bias: np.ndarray,
    ) -> None:
        weights = np.asarray(weights, dtype=np.float64)
        bias = np.asarray(bias, dtype=np.float64)

        if weights.shape != (NUM_CLASSES, EMBEDDING_DIM):
            raise ValueError(f"Expected weights (20, 768), got {weights.shape}")

        if bias.shape != (NUM_CLASSES,):
            raise ValueError(f"Expected bias (20,), got {bias.shape}")

        if not (np.isfinite(weights).all() and np.isfinite(bias).all()):
            raise ValueError("Classifier weights must be finite.")

        self.weights = weights.copy()
        self.bias = bias.copy()

    @classmethod
    def from_npz(cls, path: str | Path) -> "CategoryClassifier":
        """Load a trusted, non-pickled classifier artifact."""

        with np.load(path, allow_pickle=False) as data:
            required = {"weights", "bias", "class_ids"}

            if not required.issubset(data.files):
                raise ValueError("Incomplete classifier artifact.")

            class_ids = data["class_ids"]

            if not np.array_equal(
                class_ids,
                np.arange(NUM_CLASSES),
            ):
                raise ValueError("Classifier class ordering mismatch.")

            weights = data["weights"]
            bias = data["bias"]

        return cls(weights, bias)

    def classify(
        self,
        embedding: np.ndarray,
        main_category: str,
        top_k: int = 3,
    ) -> ClassificationResult:
        """Predict a subcategory under the known main category."""

        if main_category not in MAIN_CATEGORIES:
            raise ValueError(f"Unsupported main category: {main_category}")

        if isinstance(top_k, bool) or not isinstance(top_k, int):
            raise ValueError("top_k must be a positive integer.")

        if top_k < 1:
            raise ValueError("top_k must be positive.")

        vector = np.asarray(embedding, dtype=np.float64)

        if vector.shape != (EMBEDDING_DIM,):
            raise ValueError("Expected a 768D embedding.")

        if not np.isfinite(vector).all():
            raise ValueError("Embedding contains NaN or Infinity.")

        norm = float(np.linalg.norm(vector))

        if not np.isclose(norm, 1.0, atol=1e-3, rtol=0):
            raise ValueError("Embedding must be L2-normalized.")

        # Equivalent to sklearn LogisticRegression.decision_function.
        scores = self.weights @ vector + self.bias

        # Only classes belonging to the selected parent category.
        allowed = [
            class_id for class_id, (category, _) in enumerate(TAXONOMY) if category == main_category
        ]

        ranked = sorted(
            allowed,
            key=lambda class_id: (-scores[class_id], class_id),
        )

        candidates = tuple(
            ClassCandidate(
                class_id=class_id,
                name=TAXONOMY[class_id][1],
                score=float(scores[class_id]),
            )
            for class_id in ranked[:top_k]
        )

        winner = candidates[0]

        return ClassificationResult(
            class_id=winner.class_id,
            main_category=main_category,
            sub_category=winner.name,
            score=winner.score,
            alternatives=candidates,
        )
