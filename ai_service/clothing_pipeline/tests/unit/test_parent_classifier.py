"""Active 1536D head routing, margins and view-dependent decisions."""

import numpy as np
import pytest

from gardirop_ai_clothing.contracts import MainCategory, class_ids_for_category
from gardirop_ai_clothing.embeddings.fusion import fuse_views
from gardirop_ai_clothing.labeling.category import SCORE_KIND, CategoryClassifier


def pair_vector():
    front, back = np.zeros(768), np.zeros(768)
    front[0], back[1] = 1, 1
    return fuse_views(front=front, back=back)


@pytest.mark.parametrize("parent", list(MainCategory))
def test_only_selected_parents_rows_are_ranked(parent):
    weights, bias = np.zeros((20, 1536)), np.full(20, 1e8)
    allowed = class_ids_for_category(parent)
    bias[list(allowed)] = np.arange(len(allowed)) - 20
    result = CategoryClassifier(weights, bias).classify(pair_vector(), parent)
    assert result.class_id == allowed[-1]
    assert result.main_category == parent
    assert [x.class_id for x in result.alternatives] == list(reversed(allowed[-3:]))
    assert result.score == len(allowed) - 21
    assert result.score_kind == SCORE_KIND
    assert all(x.score_kind == SCORE_KIND for x in result.alternatives)


def test_front_back_halves_affect_classifier_in_the_trained_order():
    weights, bias = np.zeros((20, 1536)), np.zeros(20)
    weights[0, 0], weights[1, 768] = 4, 4
    classifier = CategoryClassifier(weights, bias)
    vector = pair_vector()
    assert classifier.classify(vector, "üst").class_id == 0
    swapped = np.r_[vector[768:], vector[:768]]
    assert classifier.classify(swapped, "üst").class_id == 1


def test_top_k_is_capped_at_parent_size_and_ties_use_class_order():
    classifier = CategoryClassifier(np.zeros((20, 1536)), np.zeros(20))
    result = classifier.classify(pair_vector(), "alt", top_k=100)
    assert [x.class_id for x in result.alternatives] == list(range(9, 15))


@pytest.mark.parametrize("bad", [True, 0, -1, 1.5, "3"])
def test_invalid_top_k_rejected(bad):
    classifier = CategoryClassifier(np.zeros((20, 1536)), np.zeros(20))
    with pytest.raises(ValueError, match="top_k"):
        classifier.classify(pair_vector(), "üst", top_k=bad)


@pytest.mark.parametrize("bad", ["UST_GIYIM", "ÜST", "ayakkabı", "", None])
def test_unknown_parent_is_not_guessed(bad):
    classifier = CategoryClassifier(np.zeros((20, 1536)), np.zeros(20))
    with pytest.raises(ValueError):
        classifier.classify(pair_vector(), bad)


@pytest.mark.parametrize(
    "weights,bias",
    [
        (np.zeros((20, 768)), np.zeros(20)),
        (np.zeros((20, 1536)), np.zeros(19)),
        (np.zeros((20, 1536), dtype=int), np.zeros(20)),
        (np.full((20, 1536), np.nan), np.zeros(20)),
        (np.zeros((20, 1536)), np.full(20, np.inf)),
    ],
)
def test_incompatible_parameters_rejected(weights, bias):
    with pytest.raises(ValueError):
        CategoryClassifier(weights, bias)


def test_classifier_copies_parameters_and_rejects_legacy_768_input():
    weights, bias = np.zeros((20, 1536)), np.zeros(20)
    classifier = CategoryClassifier(weights, bias)
    bias[1] = 100
    assert classifier.classify(pair_vector(), "üst").class_id == 0
    assert not classifier.weights.flags.writeable and not classifier.bias.flags.writeable
    with pytest.raises(ValueError, match="1536"):
        classifier.classify(np.ones(768) / np.sqrt(768), "üst")
