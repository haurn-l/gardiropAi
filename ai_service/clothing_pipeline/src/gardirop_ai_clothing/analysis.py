"""Backend-free application core: photo -> prepared view -> paired LR result."""

import hashlib
import json
from dataclasses import asdict, dataclass, field

import numpy as np

from gardirop_ai_clothing.config import Settings
from gardirop_ai_clothing.contracts import FUSION_METHOD, TAXONOMY_VERSION, MainCategory
from gardirop_ai_clothing.embeddings.marqo import MARQO_MODEL_NAME, MarqoEncoder, load_marqo_encoder
from gardirop_ai_clothing.errors import ConfigurationError, InferenceError
from gardirop_ai_clothing.image.birefnet_local import BIREFNET_MODEL_NAME, load_birefnet_segmenter
from gardirop_ai_clothing.image.segmentation import BiRefNetSegmenter
from gardirop_ai_clothing.labeling.artifacts import (
    CLASSIFIER_MODEL_NAME,
    load_classifier_from_manifest,
)
from gardirop_ai_clothing.labeling.attributes import AttributeService
from gardirop_ai_clothing.labeling.category import ClassificationResult
from gardirop_ai_clothing.labeling.service import ParentClassificationService
from gardirop_ai_clothing.model_manager import ModelManager
from gardirop_ai_clothing.model_specs import BIREFNET_REVISION, MARQO_REVISION, SEGMENTATION_PROFILE
from gardirop_ai_clothing.pipeline import (
    ClothingImagePipeline,
    ImagePreparationOptions,
    PreparedGarmentImage,
)
from gardirop_ai_clothing.schemas import AnalysisVersions, ClothingTags, ViewType

PREPROCESSING_VERSION = "clothing-image-v2-dynamic"


@dataclass(frozen=True)
class AnalyzedView:
    view_type: ViewType
    prepared: PreparedGarmentImage
    embedding: np.ndarray
    options: ImagePreparationOptions
    preprocessing_version: str = PREPROCESSING_VERSION
    embedding_revision: str = MARQO_REVISION
    segmentation_revision: str = BIREFNET_REVISION


@dataclass(frozen=True)
class AnalyzedClothingPair:
    front: AnalyzedView
    back: AnalyzedView
    embedding: np.ndarray
    classification: ClassificationResult
    versions: AnalysisVersions
    attribute_tags: dict = field(default_factory=dict)
    diagnostics: dict = field(default_factory=dict)

    @property
    def tags(self) -> ClothingTags:
        return ClothingTags(sub_category=self.classification.sub_category, **self.attribute_tags)


class _ManagedSegmenter:
    def __init__(self, manager: ModelManager):
        self.manager = manager

    def predict_alpha(self, image):
        segmenter = self.manager.get_model(BIREFNET_MODEL_NAME)
        if not isinstance(segmenter, BiRefNetSegmenter):
            raise InferenceError("Registered segmenter is not a BiRefNetSegmenter.")
        return segmenter.predict_alpha(image)


def _caused_by_oom(exc: Exception) -> bool:
    import torch

    seen = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, torch.OutOfMemoryError):
            return True
        current = current.__cause__ or current.__context__
    return False


class ClothingAnalysisService:
    """Create once per process. Both neural stages share one lazy manager and slot.

    Models remain cached on their resolved devices. This does not guarantee
    CUDA co-residency fits; OOM fails explicitly, without silent CPU fallback.
    Draft state, queues, retries and persistence are implemented in later steps.
    """

    def __init__(
        self,
        manager: ModelManager,
        *,
        default_options: ImagePreparationOptions | None = None,
        max_upload_bytes: int = 20 * 1024 * 1024,
        max_pixels: int = 24_000_000,
        attributes: AttributeService | None = None,
    ):
        self.manager = manager
        self.attributes = attributes
        self.images = ClothingImagePipeline(
            _ManagedSegmenter(manager),
            default_options=default_options,
            max_upload_bytes=max_upload_bytes,
            max_pixels=max_pixels,
        )
        self.classifier = ParentClassificationService(manager)

    def prepare_view(
        self,
        image_bytes: bytes,
        *,
        view_type: ViewType | str,
        options: ImagePreparationOptions | None = None,
        timeout_seconds: float | None = None,
    ) -> AnalyzedView:
        view = ViewType(view_type)
        options = options or self.images.default_options
        # This outer slot includes first-time allocation and both neural stages.
        # Use the low-level encoder here: the Marqo service would acquire twice.
        try:
            with self.manager.gpu_slot(timeout_seconds=timeout_seconds):
                prepared = self.images.prepare_photo(image_bytes, options=options)
                encoder = self.manager.get_model(MARQO_MODEL_NAME)
                if not isinstance(encoder, MarqoEncoder):
                    raise InferenceError("Registered encoder is not a MarqoEncoder.")
                embedding = encoder.encode(prepared.white_rgb)
        except Exception as exc:
            if _caused_by_oom(exc):
                raise InferenceError(
                    "GPU memory exhausted during clothing analysis. No CPU fallback was used. "
                    "Free GPU memory or explicitly retry with device='cpu'."
                ) from exc
            raise
        return AnalyzedView(view_type=view, prepared=prepared, embedding=embedding, options=options)

    def finish_pair(
        self,
        *,
        front: AnalyzedView,
        back: AnalyzedView,
        main_category: MainCategory | str,
    ) -> AnalyzedClothingPair:
        parent = MainCategory(main_category)
        for view, expected in ((front, ViewType.FRONT), (back, ViewType.BACK)):
            if not isinstance(view, AnalyzedView) or view.view_type != expected:
                raise ValueError("A FRONT view and a BACK view are required in that order.")
            if (
                view.preprocessing_version != PREPROCESSING_VERSION
                or view.embedding_revision != MARQO_REVISION
                or view.segmentation_revision != BIREFNET_REVISION
            ):
                raise ValueError("View producer versions differ from the active pipeline.")
        pair = self.classifier.analyze_views(
            front=front.embedding,
            back=back.embedding,
            main_category=parent,
            top_k=20,
        )
        head = self.manager.get_model(CLASSIFIER_MODEL_NAME)
        policy = json.dumps(
            {
                "version": PREPROCESSING_VERSION,
                "segmentation_revision": BIREFNET_REVISION,
                "segmentation_profile": SEGMENTATION_PROFILE,
                "FRONT": asdict(front.options),
                "BACK": asdict(back.options),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        stamp = hashlib.sha256(policy.encode()).hexdigest()[:16]
        versions = AnalysisVersions(
            taxonomy_version=TAXONOMY_VERSION,
            preprocessing_version=f"{PREPROCESSING_VERSION}:{stamp}",
            embedding_revision=MARQO_REVISION,
            classifier_artifact_sha256=head.artifact_sha256,
            fusion_method=FUSION_METHOD,
        )
        attribute_tags, attributes = (
            self.attributes.analyze(front, back)
            if self.attributes
            else ({}, {"status": "not_configured"})
        )
        diagnostics = {
            "image_output": {
                "FRONT": front.prepared.delivery_profile,
                "BACK": back.prepared.delivery_profile,
                "compression": "lossless_webp",
                "background": "#FFFFFF",
                "resolution_policy": "source_pixels_preserved_no_upscaling",
                "views": {
                    name: {
                        "source_size": list(view.prepared.source_size),
                        "output_size": list(view.prepared.white_rgb.size),
                        "encoded_bytes": len(view.prepared.delivery_webp),
                        "rotation_degrees": view.prepared.rotation_degrees,
                    }
                    for name, view in (("FRONT", front), ("BACK", back))
                },
            },
            "segmentation": {
                "model": BIREFNET_MODEL_NAME,
                "revision": BIREFNET_REVISION,
                "preprocessing_profile": SEGMENTATION_PROFILE,
            },
            "classification": json.loads(json.dumps(asdict(pair.classification))),
            "attributes": attributes,
            "original_tags": ClothingTags(
                sub_category=pair.classification.sub_category, **attribute_tags
            ).model_dump(mode="json"),
            "embedding": {
                "dimension": 1536,
                "view_dimension": 768,
                "view_order": ["FRONT", "BACK"],
                "norm": float(np.linalg.norm(pair.embedding)),
                "encoder_revision": MARQO_REVISION,
            },
        }
        return AnalyzedClothingPair(
            front=front,
            back=back,
            embedding=pair.embedding,
            classification=pair.classification,
            versions=versions,
            attribute_tags=attribute_tags,
            diagnostics=diagnostics,
        )

    def analyze_pair(
        self,
        front_bytes: bytes,
        back_bytes: bytes,
        main_category: MainCategory | str,
        *,
        front_options: ImagePreparationOptions | None = None,
        back_options: ImagePreparationOptions | None = None,
        timeout_seconds: float | None = None,
    ) -> AnalyzedClothingPair:
        parent = MainCategory(main_category)
        front = self.prepare_view(
            front_bytes,
            view_type=ViewType.FRONT,
            options=front_options,
            timeout_seconds=timeout_seconds,
        )
        back = self.prepare_view(
            back_bytes,
            view_type=ViewType.BACK,
            options=back_options,
            timeout_seconds=timeout_seconds,
        )
        return self.finish_pair(front=front, back=back, main_category=parent)


def create_analysis_service(settings: Settings) -> ClothingAnalysisService:
    if settings.max_concurrent_gpu_jobs != 1:
        raise ConfigurationError(
            "The combined pipeline currently requires max_concurrent_gpu_jobs=1."
        )
    path = settings.model_manifest_path.expanduser().resolve()
    manager = ModelManager(
        {
            BIREFNET_MODEL_NAME: lambda: load_birefnet_segmenter(path, device=settings.device),
            MARQO_MODEL_NAME: lambda: load_marqo_encoder(path, device=settings.device),
            CLASSIFIER_MODEL_NAME: lambda: load_classifier_from_manifest(path),
        },
        max_concurrent_gpu_jobs=1,
    )
    return ClothingAnalysisService(
        manager,
        attributes=AttributeService(settings.attribute_bank_dir),
        max_upload_bytes=settings.max_upload_mb * 1024 * 1024,
        max_pixels=settings.max_image_pixels,
        default_options=ImagePreparationOptions(
            use_cleanup=settings.image_use_cleanup,
            auto_align=settings.image_auto_align,
            padding=settings.image_padding,
            square_margin_fraction=settings.image_square_margin_fraction,
        ),
    )
