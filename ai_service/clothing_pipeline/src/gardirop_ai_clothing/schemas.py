"""Internal contracts for the agreed clothing pipeline."""

import math
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    JsonValue,
    StringConstraints,
    model_validator,
)

from gardirop_ai_clothing.contracts import (
    EMBEDDING_DIMENSION,
    FUSION_METHOD,
    NORM_ABS_TOLERANCE,
    TAXONOMY_VERSION,
    VIEW_EMBEDDING_DIMENSION,
    MainCategory,
    subcategories_for_category,
)

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
ShortText = Identifier
ImageReference = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)
]
GitRevision = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ViewType(StrEnum):
    FRONT = "FRONT"
    BACK = "BACK"


class DraftStatus(StrEnum):
    WAITING_VIEWS = "WAITING_VIEWS"
    ANALYZING = "ANALYZING"
    REVIEW_READY = "REVIEW_READY"
    FAILED = "FAILED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class PhotoTaskStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DISCARDED = "DISCARDED"


class JobStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class AnalysisVersions(ContractModel):
    """Actual producer identities must be supplied, never guessed by defaults."""

    taxonomy_version: ShortText
    preprocessing_version: ShortText
    embedding_revision: GitRevision
    classifier_artifact_sha256: Sha256
    fusion_method: ShortText

    @model_validator(mode="after")
    def validate_contract_versions(self) -> Self:
        if self.taxonomy_version != TAXONOMY_VERSION:
            raise ValueError("Unsupported taxonomy version.")
        if self.fusion_method != FUSION_METHOD:
            raise ValueError("Unsupported embedding fusion method.")
        return self


class PhotoSubmission(ContractModel):
    item_session_id: Identifier
    capture_id: Identifier
    draft_revision: int = Field(strict=True, ge=1)
    view_type: ViewType
    selected_category: MainCategory


class PhotoJobResult(ContractModel):
    job_id: Identifier
    item_session_id: Identifier
    capture_id: Identifier
    draft_revision: int = Field(strict=True, ge=1)
    view_type: ViewType
    status: JobStatus
    processed_image_ref: ImageReference | None = None
    error_code: ShortText | None = None

    @model_validator(mode="after")
    def validate_status_fields(self) -> Self:
        if self.status == JobStatus.READY:
            if self.processed_image_ref is None or self.error_code is not None:
                raise ValueError("READY requires an image reference and no error.")
        elif self.status == JobStatus.FAILED:
            if self.error_code is None or self.processed_image_ref is not None:
                raise ValueError("FAILED requires an error and no result image.")
        elif self.processed_image_ref is not None or self.error_code is not None:
            raise ValueError("Unfinished jobs cannot contain a final result or error.")
        return self


class ItemStatus(StrEnum):
    TEMIZ = "TEMIZ"
    KIRLI = "KIRLI"


class ClothingTags(ContractModel):
    sub_category: ShortText | None = None
    color: ShortText | None = None
    season: ShortText | None = None
    has_print: bool | None = None
    user_rating: int | None = Field(default=None, strict=True, ge=1, le=5)
    item_status: ItemStatus | None = None
    custom_tags: tuple[ShortText, ...] = Field(default=(), max_length=20)


class ClothingAnalysisResult(ContractModel):
    """FRONT then BACK, each unit vector scaled by 1/sqrt(2)."""

    item_session_id: Identifier
    draft_revision: int = Field(strict=True, ge=1)
    category: MainCategory
    front_image_ref: ImageReference
    back_image_ref: ImageReference
    tags: ClothingTags
    model_diagnostics: dict[str, JsonValue] = Field(default_factory=dict)
    embedding_model: ShortText
    versions: AnalysisVersions
    embedding: tuple[FiniteFloat, ...] = Field(
        min_length=EMBEDDING_DIMENSION,
        max_length=EMBEDDING_DIMENSION,
    )

    @model_validator(mode="after")
    def validate_analysis(self) -> Self:
        subcategory = self.tags.sub_category
        if subcategory is not None and subcategory not in subcategories_for_category(self.category):
            raise ValueError("Subcategory does not belong to the selected parent.")
        for half in (
            self.embedding[:VIEW_EMBEDDING_DIMENSION],
            self.embedding[VIEW_EMBEDDING_DIMENSION:],
        ):
            if not math.isclose(
                math.hypot(*half),
                1.0 / math.sqrt(2.0),
                abs_tol=NORM_ABS_TOLERANCE,
                rel_tol=0.0,
            ):
                raise ValueError("Each embedding half must have norm 1/sqrt(2).")
        return self
