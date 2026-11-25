"""HTTP contract checks without model inference or backend access."""

import pytest
from fastapi.testclient import TestClient

from gardirop_ai_clothing.api_contracts import ApiCategory
from gardirop_ai_clothing.app import create_app
from gardirop_ai_clothing.contracts import MainCategory


@pytest.fixture
def client():
    with TestClient(create_app()) as instance:
        yield instance


@pytest.mark.parametrize(
    ("wire", "native"),
    [
        ("UST_GIYIM", MainCategory.UPPER),
        ("ALT_GIYIM", MainCategory.LOWER),
        ("DIS_GIYIM", MainCategory.OUTER),
    ],
)
def test_public_category_mapping_preserves_internal_categories(wire, native):
    category = ApiCategory(wire)
    assert category.to_internal() == native
    assert ApiCategory.from_internal(native).value == wire


@pytest.mark.parametrize("value", ["AYAKKABI", "AKSESUAR", "üst"])
def test_unsupported_public_category_codes_are_rejected(value):
    with pytest.raises(ValueError):
        ApiCategory(value)


def test_liveness_does_not_claim_photo_processing_is_connected(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ALIVE"
    assert response.json()["photoProcessingAvailable"] is False


def test_taxonomy_preserves_class_ids_and_external_category_codes(client):
    response = client.get("/v1/clothing/taxonomy")
    assert response.status_code == 200
    data = response.json()

    assert data["taxonomyVersion"] == "clothing20-v1"
    assert data["viewEmbeddingDimension"] == 768
    assert data["embeddingDimension"] == 1536
    assert data["viewOrder"] == ["FRONT", "BACK"]

    assert {item["code"]: item["subCategoryCount"] for item in data["categories"]} == {
        "UST_GIYIM": 9,
        "ALT_GIYIM": 6,
        "DIS_GIYIM": 5,
    }

    rows = data["subCategories"]
    assert [row["classId"] for row in rows] == list(range(20))
    assert rows[10] == {"classId": 10, "category": "ALT_GIYIM", "label": "Jean"}
    assert rows[17] == {"classId": 17, "category": "DIS_GIYIM", "label": "Kot ceket"}


def test_openapi_exposes_the_public_get_contracts(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    assert "get" in schema["paths"]["/health/live"]
    assert "get" in schema["paths"]["/v1/clothing/taxonomy"]
    assert set(schema["components"]["schemas"]["ApiCategory"]["enum"]) == {
        "UST_GIYIM",
        "ALT_GIYIM",
        "DIS_GIYIM",
    }


@pytest.mark.parametrize("path", ["/health/live", "/v1/clothing/taxonomy"])
def test_read_endpoints_reject_post_requests(client, path):
    response = client.post(path)
    assert response.status_code == 405
