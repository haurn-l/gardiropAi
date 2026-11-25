"""Validate cross-field rules without loading a neural model."""

import math

import pytest
from pydantic import ValidationError

from gardirop_ai_clothing.contracts import FUSION_METHOD, TAXONOMY_VERSION, MainCategory
from gardirop_ai_clothing.schemas import (
    AnalysisVersions,
    ClothingAnalysisResult,
    ClothingTags,
    PhotoJobResult,
    PhotoSubmission,
)


def sample_analysis():
    vector = [0.0] * 1536
    vector[0] = vector[768] = 1.0 / math.sqrt(2.0)
    return {
        "item_session_id": "session-001",
        "draft_revision": 1,
        "category": "üst",
        "front_image_ref": "temporary/front.webp",
        "back_image_ref": "temporary/back.webp",
        "tags": {"sub_category": "Gömlek"},
        "embedding_model": "marqo-fashionSigLIP",
        "versions": {
            "taxonomy_version": TAXONOMY_VERSION,
            "preprocessing_version": "test-preprocessing-v1",
            "embedding_revision": "a" * 40,
            "classifier_artifact_sha256": "b" * 64,
            "fusion_method": FUSION_METHOD,
        },
        "embedding": vector,
    }


def photo_data():
    return {
        "item_session_id": "session-001",
        "capture_id": "front-001",
        "draft_revision": 1,
        "view_type": "FRONT",
        "selected_category": "üst",
    }


def job_data(status="PROCESSING"):
    data = photo_data()
    data.pop("selected_category")
    return {**data, "job_id": "job-001", "status": status}


def test_valid_photo_and_json_category():
    result = PhotoSubmission(**photo_data())
    assert result.selected_category is MainCategory.UPPER
    assert result.model_dump(mode="json")["selected_category"] == "üst"


@pytest.mark.parametrize("parent", ["UST_GIYIM", "AYAKKABI", "", "üst "])
def test_photo_rejects_invalid_internal_category(parent):
    with pytest.raises(ValidationError):
        PhotoSubmission(**{**photo_data(), "selected_category": parent})


@pytest.mark.parametrize("revision", [0, -1, True, "1"])
def test_revision_must_be_a_positive_integer(revision):
    with pytest.raises(ValidationError):
        PhotoSubmission(**{**photo_data(), "draft_revision": revision})


def test_unknown_fields_and_missing_revision_are_rejected():
    with pytest.raises(ValidationError):
        PhotoSubmission(**photo_data(), unknown_field=True)
    data = photo_data()
    data.pop("draft_revision")
    with pytest.raises(ValidationError):
        PhotoSubmission(**data)


@pytest.mark.parametrize(
    ("status", "fields", "valid"),
    [
        ("READY", {"processed_image_ref": "tmp/front.webp"}, True),
        ("READY", {}, False),
        ("READY", {"processed_image_ref": "tmp/front.webp", "error_code": "ERR"}, False),
        ("FAILED", {"error_code": "ERR"}, True),
        ("FAILED", {}, False),
        ("FAILED", {"error_code": "ERR", "processed_image_ref": "tmp/front.webp"}, False),
        ("PROCESSING", {}, True),
        ("PROCESSING", {"processed_image_ref": "tmp/front.webp"}, False),
        ("RECEIVED", {"error_code": "ERR"}, False),
    ],
)
def test_job_status_cannot_contradict_result(status, fields, valid):
    data = {**job_data(status), **fields}
    if valid:
        PhotoJobResult(**data)
    else:
        with pytest.raises(ValidationError):
            PhotoJobResult(**data)


def test_analysis_roundtrip_and_immutable_vector():
    result = ClothingAnalysisResult(**sample_analysis())
    assert isinstance(result.embedding, tuple)
    assert math.hypot(*result.embedding) == pytest.approx(1.0)
    assert ClothingAnalysisResult.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        result.category = MainCategory.LOWER
    with pytest.raises(TypeError):
        result.embedding[0] = 0.0


@pytest.mark.parametrize("subcategory", ["Jean", "Sweatshirt"])
def test_analysis_rejects_wrong_parent_or_unsupported_subtype(subcategory):
    data = sample_analysis()
    data["tags"] = {"sub_category": subcategory}
    with pytest.raises(ValidationError):
        ClothingAnalysisResult(**data)


@pytest.mark.parametrize("kind", ["short", "nan", "inf", "zero", "unscaled", "one_half"])
def test_invalid_feature_contract_is_rejected(kind):
    data = sample_analysis()
    if kind == "short":
        data["embedding"] = data["embedding"][:768]
    elif kind in {"nan", "inf"}:
        data["embedding"][0] = float(kind)
    elif kind == "zero":
        data["embedding"] = [0.0] * 1536
    elif kind == "unscaled":
        data["embedding"][0] = data["embedding"][768] = 1.0
    else:
        # Overall norm is one, but the back half is absent.
        data["embedding"][0], data["embedding"][768] = 1.0, 0.0
    with pytest.raises(ValidationError):
        ClothingAnalysisResult(**data)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("taxonomy_version", "old18"),
        ("fusion_method", "mean768"),
        ("embedding_revision", "main"),
        ("classifier_artifact_sha256", "not-a-hash"),
    ],
)
def test_invalid_versions_are_rejected(field, bad_value):
    data = sample_analysis()["versions"]
    data[field] = bad_value
    with pytest.raises(ValidationError):
        AnalysisVersions(**data)


def test_version_metadata_is_required():
    data = sample_analysis()
    data.pop("versions")
    with pytest.raises(ValidationError):
        ClothingAnalysisResult(**data)


def test_long_image_references_and_unknown_attributes_are_supported():
    data = sample_analysis()
    data["front_image_ref"] = "https://example.test/" + "x" * 300
    result = ClothingAnalysisResult(**data)
    assert len(result.front_image_ref) > 128
    assert result.tags.color is None
    assert result.tags.season is None
    assert result.tags.has_print is None
    assert ClothingTags().sub_category is None
