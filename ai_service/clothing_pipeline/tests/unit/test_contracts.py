"""Guard artifact class ordering and shared architectural constants."""

import pytest

from gardirop_ai_clothing import contracts
from gardirop_ai_clothing.labeling import category, legacy_category


def test_taxonomy_preserves_artifact_class_order():
    expected = (
        "Gömlek",
        "T-shirt",
        "Bluz",
        "Kazak",
        "Hırka",
        "Kapüşonlu üst",
        "Atlet",
        "Spor üst",
        "Tunik",
        "Pantolon",
        "Jean",
        "Etek",
        "Şort",
        "Yağmurluk pantolonu",
        "Kışlık pantolon",
        "Ceket",
        "Blazer",
        "Kot ceket",
        "Yağmurluk",
        "Kışlık ceket",
    )
    assert tuple(name for _, name in contracts.TAXONOMY) == expected
    assert category.TAXONOMY is contracts.TAXONOMY
    assert contracts.NUM_CLASSES == 20


@pytest.mark.parametrize(
    ("parent", "indices"),
    [("üst", tuple(range(9))), ("alt", tuple(range(9, 15))), ("dış", tuple(range(15, 20)))],
)
def test_parent_rows_match_artifact_layout(parent, indices):
    assert contracts.class_ids_for_category(parent) == indices
    assert contracts.subcategories_for_category(parent) == tuple(
        contracts.TAXONOMY[i][1] for i in indices
    )


@pytest.mark.parametrize("parent", ["UST_GIYIM", "ayakkabı", "", "ÜST"])
def test_unsupported_internal_parent_is_rejected(parent):
    with pytest.raises(ValueError):
        contracts.class_ids_for_category(parent)


def test_feature_contract_and_legacy_classifier_are_distinct():
    assert contracts.VIEW_ORDER == ("FRONT", "BACK")
    assert contracts.VIEW_EMBEDDING_DIMENSION == 768
    assert contracts.EMBEDDING_DIMENSION == 1536
    assert contracts.FUSION_METHOD == "concat_unit_front_back_div_sqrt2"
    assert legacy_category.EMBEDDING_DIM == 768
    assert category.EMBEDDING_DIM == 1536


def test_manifest_matches_shared_feature_contract():
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[2]
    data = yaml.safe_load((root / "configs/model_manifest.yaml").read_text())
    pipeline = data["pipeline"]
    assert pipeline["embedding_dimension_per_view"] == contracts.VIEW_EMBEDDING_DIMENSION
    assert pipeline["combined_embedding_dimension"] == contracts.EMBEDDING_DIMENSION
    assert pipeline["subcategory_count"] == contracts.NUM_CLASSES
    assert pipeline["taxonomy_version"] == contracts.TAXONOMY_VERSION
    assert tuple(pipeline["view_order"]) == contracts.VIEW_ORDER
    assert pipeline["fusion_method"] == contracts.FUSION_METHOD
    assert pipeline["classifier_input_dimension"] == contracts.EMBEDDING_DIMENSION
    assert pipeline["classifier_architecture"] == "parent_logistic_regression"
