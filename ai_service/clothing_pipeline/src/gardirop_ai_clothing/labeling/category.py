"""Active V1 parent-specific LR on fused FRONT/BACK Marqo features."""

from dataclasses import dataclass

import numpy as np

from gardirop_ai_clothing.contracts import (
    EMBEDDING_DIMENSION,
    NUM_CLASSES,
    TAXONOMY,
    MainCategory,
    class_ids_for_category,
)
from gardirop_ai_clothing.embeddings.fusion import validate_fused_embedding

EMBEDDING_DIM = EMBEDDING_DIMENSION
SCORE_KIND = "linear_margin_not_probability"


@dataclass(frozen=True)
class ClassCandidate:
    class_id: int
    name: str
    score: float
    score_kind: str = SCORE_KIND


@dataclass(frozen=True)
class ClassificationResult:
    class_id: int
    main_category: MainCategory
    sub_category: str
    score: float
    alternatives: tuple[ClassCandidate, ...]
    score_kind: str = SCORE_KIND


class CategoryClassifier:
    """CPU-only parent LR. Production instances come from verified artifact loaders."""

    def __init__(
        self, weights: np.ndarray, bias: np.ndarray, *, artifact_sha256: str | None = None
    ):
        weights, bias = np.asarray(weights), np.asarray(bias)
        if weights.shape != (NUM_CLASSES, EMBEDDING_DIM) or bias.shape != (NUM_CLASSES,):
            raise ValueError("Parent LR requires weights (20,1536) and bias (20,).")
        if weights.dtype.kind != "f" or bias.dtype.kind != "f":
            raise ValueError("Parent LR parameters must be floating point.")
        if not (np.isfinite(weights).all() and np.isfinite(bias).all()):
            raise ValueError("Parent LR parameters must be finite.")
        self.weights = weights.astype(np.float64, copy=True)
        self.bias = bias.astype(np.float64, copy=True)
        self.weights.setflags(write=False)
        self.bias.setflags(write=False)
        self.artifact_sha256 = artifact_sha256

    def classify(
        self,
        embedding: np.ndarray,
        main_category: MainCategory | str,
        top_k: int = 3,
    ) -> ClassificationResult:
        parent = MainCategory(main_category)
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer.")
        vector = validate_fused_embedding(embedding)
        allowed = class_ids_for_category(parent)
        # The selected parent's independently trained rows only; no other head is evaluated.
        indices = np.asarray(allowed)
        scores = self.weights[indices] @ vector + self.bias[indices]
        if not np.isfinite(scores).all():
            raise ValueError("Parent LR returned non-finite scores.")
        ranked = sorted(range(len(allowed)), key=lambda i: (-float(scores[i]), allowed[i]))
        candidates = tuple(
            ClassCandidate(
                class_id=allowed[i], name=TAXONOMY[allowed[i]][1], score=float(scores[i])
            )
            for i in ranked[:top_k]
        )
        winner = candidates[0]
        return ClassificationResult(
            class_id=winner.class_id,
            main_category=parent,
            sub_category=winner.name,
            score=winner.score,
            alternatives=candidates,
        )
