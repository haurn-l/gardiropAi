"""Real image preparation and fusion connected to synthetic neural runners."""

import io
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event

import numpy as np
import pytest
import torch
from PIL import Image

from gardirop_ai_clothing import analysis as module
from gardirop_ai_clothing.config import Settings
from gardirop_ai_clothing.embeddings.marqo import MARQO_MODEL_NAME
from gardirop_ai_clothing.errors import ConfigurationError, ImageProcessingError, InferenceError
from gardirop_ai_clothing.image.birefnet_local import BIREFNET_MODEL_NAME
from gardirop_ai_clothing.pipeline import ImagePreparationOptions


def image_bytes(color=(240, 20, 30)):
    buffer = io.BytesIO()
    Image.new("RGB", (40, 60), color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_two_photos_produce_clean_views_and_one_correctly_ordered_pair(analysis_factory):
    service, calls = analysis_factory()
    result = service.analyze_pair(image_bytes(), image_bytes((20, 30, 240)), "üst")
    assert calls == {"segmentation": 2, "marqo": 2, "seg_load": 1, "marqo_load": 1, "head_load": 1}
    assert result.front.view_type == "FRONT" and result.back.view_type == "BACK"
    assert result.front.prepared.transparent_webp and result.back.prepared.transparent_webp
    assert result.embedding.shape == (1536,) and not result.embedding.flags.writeable
    assert result.embedding[0] == pytest.approx(1 / np.sqrt(2))
    assert result.embedding[768 + 2] == pytest.approx(1 / np.sqrt(2))
    assert result.classification.main_category == "üst"
    assert result.tags.sub_category == "Gömlek"
    assert (
        result.tags.color is None and result.tags.season is None and result.tags.has_print is None
    )
    assert result.versions.classifier_artifact_sha256 == "a" * 64
    assert result.front.prepared.rotation_degrees == result.back.prepared.rotation_degrees == 0


def test_front_can_finish_before_back_and_category_edits_only_run_lr(analysis_factory):
    service, calls = analysis_factory()
    front = service.prepare_view(image_bytes(), view_type="FRONT")
    assert calls["marqo"] == 1 and calls["head_load"] == 0
    back = service.prepare_view(image_bytes((20, 30, 240)), view_type="BACK")
    upper = service.finish_pair(front=front, back=back, main_category="üst")
    before = calls.copy()
    lower = service.finish_pair(front=front, back=back, main_category="alt")
    assert calls == before
    assert (
        upper.classification.sub_category == "Gömlek"
        and lower.classification.sub_category == "Pantolon"
    )
    np.testing.assert_array_equal(upper.embedding, lower.embedding)


@pytest.mark.parametrize("kwargs", [{"max_upload_bytes": 1}, {"max_pixels": 10}])
def test_configured_limits_reject_input_before_model_loading(analysis_factory, kwargs):
    service, _ = analysis_factory(**kwargs)
    with pytest.raises(ImageProcessingError, match="limit"):
        service.prepare_view(image_bytes(), view_type="FRONT")
    assert service.manager.loaded_models == ()


def test_unknown_parent_rejected_before_any_photo_processing(analysis_factory):
    service, calls = analysis_factory()
    with pytest.raises(ValueError):
        service.analyze_pair(image_bytes(), image_bytes(), "unknown")
    assert calls["segmentation"] == calls["marqo"] == 0


@pytest.mark.parametrize(
    "case",
    ["missing", "reversed", "embedding_revision", "preprocessing_version", "segmentation_revision"],
)
def test_incomplete_reversed_or_incompatible_views_never_load_head(analysis_factory, case):
    service, calls = analysis_factory()
    front = service.prepare_view(image_bytes(), view_type="FRONT")
    back = service.prepare_view(image_bytes(), view_type="BACK")
    if case == "missing":
        back = None
    elif case == "reversed":
        front, back = back, front
    else:
        front = replace(front, **{case: "incompatible"})
    with pytest.raises(ValueError):
        service.finish_pair(front=front, back=back, main_category="üst")
    assert calls["head_load"] == 0


def test_single_slot_covers_segmentation_and_encoding_and_recovers_after_timeout(analysis_factory):
    service, calls = analysis_factory()
    entered, release = Event(), Event()
    segmenter = service.manager.get_model(BIREFNET_MODEL_NAME)
    original = segmenter._runner

    def block(chw):
        entered.set()
        assert release.wait(5)
        return original(chw)

    segmenter._runner = block
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(service.prepare_view, image_bytes(), view_type="FRONT")
        try:
            assert entered.wait(5)
            with pytest.raises(InferenceError, match="slot"):
                service.prepare_view(image_bytes(), view_type="BACK", timeout_seconds=0)
        finally:
            release.set()
        front = future.result(timeout=5)
    back = service.prepare_view(image_bytes(), view_type="BACK", timeout_seconds=0)
    assert front.view_type == "FRONT" and back.view_type == "BACK"
    assert calls["segmentation"] == calls["marqo"] == 2


def test_wrapped_cuda_oom_is_explicit_and_releases_slot_without_fallback(analysis_factory):
    service, calls = analysis_factory()
    encoder = service.manager.get_model(MARQO_MODEL_NAME)
    original = encoder._runner

    def fail(image):
        raise torch.OutOfMemoryError("synthetic capacity failure")

    encoder._runner = fail
    with pytest.raises(InferenceError, match="No CPU fallback"):
        service.prepare_view(image_bytes(), view_type="FRONT")
    assert calls["head_load"] == 0
    encoder._runner = original
    service.prepare_view(image_bytes(), view_type="FRONT", timeout_seconds=0)
    assert calls["marqo"] == 1


def test_options_apply_per_view_and_are_recorded_in_preprocessing_version(analysis_factory):
    service, _ = analysis_factory(
        default_options=ImagePreparationOptions(padding=0, square_margin_fraction=0.2)
    )
    first = service.analyze_pair(image_bytes(), image_bytes(), "üst")
    second = service.analyze_pair(
        image_bytes(),
        image_bytes(),
        "üst",
        back_options=ImagePreparationOptions(manual_rotation=90),
    )
    assert first.front.options.square_margin_fraction == 0.2
    assert (
        first.front.prepared.white_rgb.width >= max(first.front.prepared.aligned_rgba.size) * 1.39
    )
    assert (
        second.front.prepared.rotation_degrees == 0 and second.back.prepared.rotation_degrees == 90
    )
    assert first.versions.preprocessing_version != second.versions.preprocessing_version


def test_factory_is_lazy_and_propagates_one_settings_source(
    analysis_factory, model_manifest, monkeypatch
):
    settings = Settings(
        _env_file=None,
        model_manifest_path=model_manifest,
        device="cpu",
        max_upload_mb=1,
        max_image_pixels=2000,
        image_auto_align=False,
        image_padding=7,
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Factory must not load models.")

    monkeypatch.setattr(module, "load_birefnet_segmenter", forbidden)
    monkeypatch.setattr(module, "load_marqo_encoder", forbidden)
    service = module.create_analysis_service(settings)
    assert service.manager.loaded_models == ()
    assert service.images.max_upload_bytes == 1024 * 1024 and service.images.max_pixels == 2000
    assert service.images.default_options.padding == 7
    with pytest.raises(ConfigurationError, match="max_concurrent_gpu_jobs=1"):
        module.create_analysis_service(settings.model_copy(update={"max_concurrent_gpu_jobs": 2}))
