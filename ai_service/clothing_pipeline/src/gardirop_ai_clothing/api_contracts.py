"""Public category contracts; independent of neural model loading."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from gardirop_ai_clothing.contracts import (
    EMBEDDING_DIMENSION,
    TAXONOMY,
    TAXONOMY_VERSION,
    VIEW_EMBEDDING_DIMENSION,
    VIEW_ORDER,
    MainCategory,
)


class ApiCategory(StrEnum):
    UPPER = "UST_GIYIM"
    LOWER = "ALT_GIYIM"
    OUTER = "DIS_GIYIM"

    def to_internal(self) -> MainCategory:
        return _TO_INTERNAL[self]

    @classmethod
    def from_internal(cls, category: MainCategory | str) -> Self:
        return cls(_FROM_INTERNAL[MainCategory(category)])


_TO_INTERNAL = {
    ApiCategory.UPPER: MainCategory.UPPER,
    ApiCategory.LOWER: MainCategory.LOWER,
    ApiCategory.OUTER: MainCategory.OUTER,
}
_FROM_INTERNAL = {native: wire for wire, native in _TO_INTERNAL.items()}


class ApiModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )


class HealthResponse(ApiModel):
    status: Literal["ALIVE"] = "ALIVE"
    api_version: Literal["v1"] = Field(default="v1", alias="apiVersion")
    photo_processing_available: bool = Field(
        default=False,
        alias="photoProcessingAvailable",
    )


class ReadinessResponse(ApiModel):
    status: Literal["READY", "NOT_READY"]
    models_warmed: bool = Field(alias="modelsWarmed")
    loaded_models: tuple[str, ...] = Field(default=(), alias="loadedModels")
    startup_preparation_seconds: float | None = Field(
        default=None, alias="startupPreparationSeconds", ge=0
    )
    device: str | None = None
    segmentation_backend: Literal["pytorch", "tensorrt_with_pytorch_fallback"] | None = Field(
        default=None, alias="segmentationBackend"
    )


class CategoryInfo(ApiModel):
    code: ApiCategory
    label: str
    sub_category_count: int = Field(alias="subCategoryCount", ge=1)


class SubcategoryInfo(ApiModel):
    class_id: int = Field(alias="classId", ge=0)
    category: ApiCategory
    label: str


class TaxonomyResponse(ApiModel):
    taxonomy_version: str = Field(alias="taxonomyVersion")
    categories: tuple[CategoryInfo, ...]
    sub_categories: tuple[SubcategoryInfo, ...] = Field(alias="subCategories")
    view_embedding_dimension: int = Field(alias="viewEmbeddingDimension", ge=1)
    embedding_dimension: int = Field(alias="embeddingDimension", ge=1)
    view_order: tuple[str, str] = Field(alias="viewOrder")


def build_taxonomy() -> TaxonomyResponse:
    labels = (
        (ApiCategory.UPPER, "Üst giyim"),
        (ApiCategory.LOWER, "Alt giyim"),
        (ApiCategory.OUTER, "Dış giyim"),
    )
    categories = tuple(
        CategoryInfo(
            code=code,
            label=label,
            sub_category_count=sum(parent == code.to_internal() for parent, _ in TAXONOMY),
        )
        for code, label in labels
    )
    subcategories = tuple(
        SubcategoryInfo(
            class_id=index,
            category=ApiCategory.from_internal(parent),
            label=label,
        )
        for index, (parent, label) in enumerate(TAXONOMY)
    )
    return TaxonomyResponse(
        taxonomy_version=TAXONOMY_VERSION,
        categories=categories,
        sub_categories=subcategories,
        view_embedding_dimension=VIEW_EMBEDDING_DIMENSION,
        embedding_dimension=EMBEDDING_DIMENSION,
        view_order=VIEW_ORDER,
    )
