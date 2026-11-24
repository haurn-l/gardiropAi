import numpy as np
import pytest

from gardirop_ai_clothing.labeling.legacy_category import (
    CategoryClassifier,
    ClassificationResult,
)


@pytest.fixture
def classifier():
    weights = np.zeros((20, 768), dtype=np.float64)
    bias = np.zeros(20, dtype=np.float64)

    # Deliberately assign the strongest score to JEAN.
    # Parent-category masking must prevent wrong-parent results.
    weights[10, 0] = 10.0  # Jean / alt
    weights[1, 0] = 5.0  # T-shirt / üst
    weights[16, 0] = 3.0  # Blazer / dış

    return CategoryClassifier(weights, bias)


@pytest.fixture
def embedding():
    vector = np.zeros(768, dtype=np.float64)
    vector[0] = 1.0
    return vector


@pytest.mark.parametrize(
    ("category", "expected_id"),
    [
        ("üst", 1),
        ("alt", 10),
        ("dış", 16),
    ],
)
def test_parent_category_mask(
    classifier,
    embedding,
    category,
    expected_id,
):
    result = classifier.classify(embedding, category)
    assert isinstance(result, ClassificationResult)
    assert result.class_id == expected_id


def test_alternatives_stay_in_parent(classifier, embedding):
    result = classifier.classify(
        embedding,
        "üst",
        top_k=5,
    )

    assert len(result.alternatives) == 5
    assert all(0 <= candidate.class_id <= 8 for candidate in result.alternatives)


@pytest.mark.parametrize(
    "bad_embedding",
    [
        np.zeros(768),
        np.zeros(512),
        np.zeros(1536),
        np.full(768, np.nan),
        np.full(768, np.inf),
    ],
)
def test_invalid_embeddings(
    classifier,
    bad_embedding,
):
    with pytest.raises(ValueError):
        classifier.classify(bad_embedding, "üst")


def test_unsupported_category(classifier, embedding):
    with pytest.raises(ValueError):
        classifier.classify(embedding, "ayakkabı")


def test_invalid_weights():
    with pytest.raises(ValueError):
        CategoryClassifier(
            np.zeros((18, 768)),
            np.zeros(18),
        )


def test_npz_artifact_roundtrip(tmp_path, classifier, embedding):
    path = tmp_path / "classifier.npz"

    np.savez_compressed(
        path,
        weights=classifier.weights,
        bias=classifier.bias,
        class_ids=np.arange(20),
    )

    loaded = CategoryClassifier.from_npz(path)

    original = classifier.classify(embedding, "üst")
    restored = loaded.classify(embedding, "üst")

    assert original == restored
