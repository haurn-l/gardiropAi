"""Pair feature analysis; no image inference, storage or backend calls."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from gardirop_ai_clothing.contracts import MainCategory
from gardirop_ai_clothing.embeddings.fusion import fuse_views, validate_fused_embedding
from gardirop_ai_clothing.errors import InferenceError
from gardirop_ai_clothing.labeling.artifacts import (
    CLASSIFIER_MODEL_NAME,
    create_classifier_manager_from_manifest,
)
from gardirop_ai_clothing.labeling.category import CategoryClassifier, ClassificationResult
from gardirop_ai_clothing.model_manager import ModelManager


@dataclass(frozen=True)
class PairAnalysis:
    embedding: np.ndarray
    classification: ClassificationResult


class ParentClassificationService:
    """One lazy CPU head per manager; category edits reuse the same fused vector."""

    def __init__(self, manager: ModelManager):
        self.manager = manager

    def classify(
        self,
        embedding: np.ndarray,
        main_category: MainCategory | str,
        *,
        top_k: int = 3,
    ) -> ClassificationResult:
        parent = MainCategory(main_category)
        validate_fused_embedding(embedding)
        classifier = self.manager.get_model(CLASSIFIER_MODEL_NAME)
        if not isinstance(classifier, CategoryClassifier):
            raise InferenceError("Registered classifier is not the active 1536D parent LR.")
        return classifier.classify(embedding, parent, top_k=top_k)

    def analyze_views(
        self,
        *,
        front: np.ndarray,
        back: np.ndarray,
        main_category: MainCategory | str,
        top_k: int = 3,
    ) -> PairAnalysis:
        parent = MainCategory(main_category)
        fused = fuse_views(front=front, back=back)
        return PairAnalysis(
            embedding=fused, classification=self.classify(fused, parent, top_k=top_k)
        )


def create_parent_service(manifest_path: str | Path) -> ParentClassificationService:
    return ParentClassificationService(create_classifier_manager_from_manifest(manifest_path))
