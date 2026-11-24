"""Shared category and feature contracts; no model inference."""

from enum import StrEnum

VIEW_EMBEDDING_DIMENSION = 768
EMBEDDING_DIMENSION = 2 * VIEW_EMBEDDING_DIMENSION
TAXONOMY_VERSION = "clothing20-v1"
FUSION_METHOD = "concat_unit_front_back_div_sqrt2"
VIEW_ORDER = ("FRONT", "BACK")
NORM_ABS_TOLERANCE = 1e-3


class MainCategory(StrEnum):
    UPPER = "üst"
    LOWER = "alt"
    OUTER = "dış"


# Class IDs are row indices. Never sort or reorder this tuple.
TAXONOMY = (
    ("üst", "Gömlek"),
    ("üst", "T-shirt"),
    ("üst", "Bluz"),
    ("üst", "Kazak"),
    ("üst", "Hırka"),
    ("üst", "Kapüşonlu üst"),
    ("üst", "Atlet"),
    ("üst", "Spor üst"),
    ("üst", "Tunik"),
    ("alt", "Pantolon"),
    ("alt", "Jean"),
    ("alt", "Etek"),
    ("alt", "Şort"),
    ("alt", "Yağmurluk pantolonu"),
    ("alt", "Kışlık pantolon"),
    ("dış", "Ceket"),
    ("dış", "Blazer"),
    ("dış", "Kot ceket"),
    ("dış", "Yağmurluk"),
    ("dış", "Kışlık ceket"),
)

NUM_CLASSES = len(TAXONOMY)
MAIN_CATEGORIES = frozenset(category.value for category in MainCategory)


def class_ids_for_category(category: MainCategory | str) -> tuple[int, ...]:
    """Return stable artifact row indices for a supported parent."""
    parent = MainCategory(category)
    return tuple(i for i, (name, _) in enumerate(TAXONOMY) if name == parent)


def subcategories_for_category(category: MainCategory | str) -> tuple[str, ...]:
    return tuple(TAXONOMY[i][1] for i in class_ids_for_category(category))
