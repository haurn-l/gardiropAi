"""FRONT/BACK ordering and independent normalization are storage contracts."""

import numpy as np
import pytest

from gardirop_ai_clothing.embeddings.fusion import fuse_views, validate_fused_embedding


def test_fusion_keeps_front_first_and_back_second_without_mutating_inputs():
    front, back = np.zeros(768, dtype=np.float32), np.zeros(768, dtype=np.float32)
    front[2], back[6] = 3, -9
    result = fuse_views(front=front, back=back)
    expected = np.zeros(1536, dtype=np.float32)
    expected[2], expected[768 + 6] = 1 / np.sqrt(2), -1 / np.sqrt(2)
    np.testing.assert_array_equal(result, expected)
    assert result.dtype == np.float32 and not result.flags.writeable
    assert np.linalg.norm(result) == pytest.approx(1, abs=1e-6)
    assert front[2] == 3 and back[6] == -9
    np.testing.assert_array_equal(validate_fused_embedding(result), result)


def test_fusion_is_independent_of_each_views_positive_scale():
    rng = np.random.default_rng(32)
    front, back = rng.normal(size=(2, 768))
    np.testing.assert_allclose(
        fuse_views(front=front, back=back),
        fuse_views(front=front * 100, back=back / 17),
        atol=1e-7,
        rtol=0,
    )
    assert not np.array_equal(
        fuse_views(front=front, back=back), fuse_views(front=back, back=front)
    )


@pytest.mark.parametrize(
    "bad",
    [
        None,
        np.zeros(768),
        np.ones(767),
        np.ones((1, 768)),
        np.ones(768, dtype=int),
        np.full(768, np.nan),
        np.full(768, np.inf),
        np.full(768, 1 + 2j),
    ],
)
@pytest.mark.parametrize("view", ["front", "back"])
def test_invalid_or_missing_view_cannot_produce_a_pair(bad, view):
    views = {"front": np.ones(768), "back": np.ones(768)}
    views[view] = bad
    with pytest.raises(ValueError):
        fuse_views(**views)


@pytest.mark.parametrize(
    "bad",
    [
        np.ones(768),
        np.ones((2, 768)),
        np.ones(1536, dtype=int),
        np.full(1536, np.nan),
        np.zeros(1536),
        np.r_[np.ones(768) / np.sqrt(768), np.zeros(768)],
    ],
)
def test_invalid_fused_vector_is_rejected_even_when_total_norm_is_one(bad):
    with pytest.raises(ValueError):
        validate_fused_embedding(bad)
