"""Compact snapshots preserve pair results, restarts and corruption detection."""

import io
import json

import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing.errors import DraftConflictError, LocalStorageError
from gardirop_ai_clothing.jobs import DraftService
from gardirop_ai_clothing.labeling.attribute_bank import ENTRIES
from gardirop_ai_clothing.labeling.attributes import AttributeService
from gardirop_ai_clothing.labeling.color import (
    combine_view_palettes,
    detect_pair_color,
    view_palette,
)
from gardirop_ai_clothing.storage import LocalDraftRepository
from gardirop_ai_clothing.view_snapshot import StoredGarmentImage


def photo(color="red"):
    stream = io.BytesIO()
    Image.new("RGB", (40, 60), color).save(stream, format="PNG")
    return stream.getvalue()


def analysis_with_attributes(analysis_factory, tmp_path):
    attributes = AttributeService(tmp_path / "unused-prototype-directory")
    attributes._bank = (np.eye(len(ENTRIES), 768, dtype=np.float32), {"sha256": "a" * 64})
    return analysis_factory(attributes=attributes)


def test_restart_preserves_every_pair_output_without_pngs_or_alpha_arrays(
    tmp_path, analysis_factory
):
    analysis, _ = analysis_with_attributes(analysis_factory, tmp_path)
    front = analysis.prepare_view(photo(), view_type="FRONT")
    back = analysis.prepare_view(photo("blue"), view_type="BACK")
    expected = analysis.finish_pair(front=front, back=back, main_category="üst")
    root = tmp_path / "store"
    with_repository = LocalDraftRepository(root, compact=True)
    try:
        with_repository.create({"id": "a" * 32})
        a = with_repository.save_view("a" * 32, "b" * 32, 1, front)
        b = with_repository.save_view("a" * 32, "c" * 32, 1, back)
        assert {p.name for p in with_repository.path(a).iterdir()} == {
            "view.json",
            "features.json",
            "clean.webp",
        }
    finally:
        with_repository.close()
    repo = LocalDraftRepository(root, compact=True)
    try:
        first, second = repo.load_view(a), repo.load_view(b)
        assert isinstance(first.prepared, StoredGarmentImage)
        assert first.prepared.delivery_webp == front.prepared.delivery_webp
        assert second.prepared.delivery_webp == back.prepared.delivery_webp
        actual = analysis.finish_pair(front=first, back=second, main_category="üst")
        np.testing.assert_array_equal(actual.embedding, expected.embedding)
        assert actual.tags == expected.tags
        assert actual.classification == expected.classification
        assert actual.diagnostics == expected.diagnostics
        assert actual.versions == expected.versions
    finally:
        repo.close()


@pytest.mark.parametrize("filename", ["clean.webp", "features.json"])
def test_cached_files_are_revalidated_after_external_change(tmp_path, analysis_factory, filename):
    analysis, _ = analysis_factory()
    repo = LocalDraftRepository(tmp_path / "store", compact=True)
    try:
        repo.create({"id": "a" * 32})
        path = repo.save_view(
            "a" * 32, "b" * 32, 1, analysis.prepare_view(photo(), view_type="FRONT")
        )
        repo.load_view(path)
        (repo.path(path) / filename).write_bytes(b"tampered")
        with pytest.raises(LocalStorageError, match="SHA256"):
            repo.load_view(path)
    finally:
        repo.close()


def test_disabled_cache_and_legacy_format_remain_supported(tmp_path, analysis_factory):
    analysis, _ = analysis_factory()
    view = analysis.prepare_view(photo(), view_type="FRONT")
    root = tmp_path / "store"
    repo = LocalDraftRepository(root)
    try:
        repo.create({"id": "a" * 32})
        legacy = repo.save_view("a" * 32, "b" * 32, 1, view)
    finally:
        repo.close()
    repo = LocalDraftRepository(root, compact=True, cache_max_bytes=0)
    try:
        np.testing.assert_array_equal(
            repo.load_view(legacy).prepared.raw_alpha, view.prepared.raw_alpha
        )
        new = repo.save_view("a" * 32, "c" * 32, 1, view)
        np.testing.assert_array_equal(repo.load_view(new).embedding, view.embedding)
        assert not repo._view_cache and repo._cache_bytes == 0
    finally:
        repo.close()


def test_cache_is_bounded_and_returned_feature_objects_are_detached(tmp_path, analysis_factory):
    analysis, _ = analysis_factory()
    view = analysis.prepare_view(photo(), view_type="FRONT")
    limit = len(view.prepared.delivery_webp) + view.embedding.nbytes + 4096
    repo = LocalDraftRepository(tmp_path / "store", compact=True, cache_max_bytes=limit)
    try:
        repo.create({"id": "a" * 32})
        a = repo.save_view("a" * 32, "b" * 32, 1, view)
        b = repo.save_view("a" * 32, "c" * 32, 1, view)
        assert len(repo._view_cache) == 1 and repo._cache_bytes <= limit
        loaded = repo.load_view(b)
        assert not loaded.embedding.flags.writeable
        loaded.embedding.setflags(write=True)
        loaded.embedding[:] = 0
        loaded.prepared.color_palette["Kırmızı"] = 0
        again = repo.load_view(b)
        np.testing.assert_array_equal(again.embedding, view.embedding)
        assert again.prepared.color_palette["Kırmızı"] > 0
        assert repo.load_view(a).prepared.delivery_webp == view.prepared.delivery_webp
        repo.remove("a" * 32)
        assert not repo._view_cache and repo._cache_bytes == 0
    finally:
        repo.close()


def test_cancel_and_replacement_release_cached_views(tmp_path, analysis_factory):
    analysis, _ = analysis_factory()
    repo = LocalDraftRepository(tmp_path / "store", compact=True)
    service = DraftService(repo, analysis)
    try:
        identifier = service.create_draft("üst")["id"]
        service.submit_photo(
            identifier,
            view_type="FRONT",
            capture_id="front1",
            image_bytes=photo(),
            expected_revision=1,
        )
        service.wait_idle(10)
        old_path = service.get(identifier)["jobs"][service.get(identifier)["views"]["FRONT"]][
            "view_path"
        ]
        assert old_path in repo._view_cache
        state = service.get(identifier)
        service.submit_photo(
            identifier,
            view_type="FRONT",
            capture_id="front2",
            image_bytes=photo("blue"),
            expected_revision=state["revision"],
        )
        service.wait_idle(10)
        assert old_path not in repo._view_cache
        service.cancel(identifier, expected_revision=service.get(identifier)["revision"])
        assert not repo._view_cache
    finally:
        service.close()


def test_compact_pair_can_change_category_after_service_restart(tmp_path, analysis_factory):
    analysis, counts = analysis_with_attributes(analysis_factory, tmp_path)
    root = tmp_path / "store"
    service = DraftService(LocalDraftRepository(root, compact=True), analysis)
    identifier = service.create_draft("üst")["id"]
    try:
        for name in ("FRONT", "BACK"):
            service.submit_photo(
                identifier,
                view_type=name,
                capture_id=name,
                image_bytes=photo(),
                expected_revision=service.get(identifier)["revision"],
            )
        service.wait_idle(10)
        expected = service.get_result(identifier)
    finally:
        service.close()
    before = counts.copy()
    service = DraftService(LocalDraftRepository(root, compact=True), analysis)
    try:
        service.change_category(
            identifier, "dış", expected_revision=service.get(identifier)["revision"]
        )
        service.wait_idle(10)
        actual = service.get_result(identifier)
        assert actual.embedding == expected.embedding
        assert actual.tags.color == expected.tags.color
        assert (
            counts["segmentation"] == before["segmentation"] and counts["marqo"] == before["marqo"]
        )
        service.cancel(identifier, expected_revision=service.get(identifier)["revision"])
        with pytest.raises(DraftConflictError):
            service.get_result(identifier)
    finally:
        service.close()


def test_palette_summary_is_identical_even_with_transparency_and_missing_foreground():
    a = Image.new("RGBA", (40, 60), (190, 25, 35, 255))
    b = Image.new("RGBA", (60, 40), (10, 30, 70, 0))
    assert combine_view_palettes(view_palette(a), view_palette(b)) == detect_pair_color(a, b)


def test_unknown_compact_profile_is_rejected(tmp_path, analysis_factory):
    analysis, _ = analysis_factory()
    repo = LocalDraftRepository(tmp_path / "store", compact=True, cache_max_bytes=0)
    try:
        repo.create({"id": "a" * 32})
        path = repo.save_view(
            "a" * 32, "b" * 32, 1, analysis.prepare_view(photo(), view_type="FRONT")
        )
        record = repo.read_json(f"{path}/view.json")
        record["storage_profile"] = "unsupported"
        repo.path(f"{path}/view.json").write_text(json.dumps(record))
        with pytest.raises(LocalStorageError):
            repo.load_view(path)
    finally:
        repo.close()


def test_failed_pair_analysis_retries_from_compact_records_after_restart(
    tmp_path, analysis_factory
):
    analysis, counts = analysis_factory()
    finish = analysis.finish_pair

    def fail(**kwargs):
        raise RuntimeError("synthetic pair failure")

    analysis.finish_pair = fail
    root = tmp_path / "store"
    service = DraftService(LocalDraftRepository(root, compact=True), analysis)
    identifier = service.create_draft("üst")["id"]
    try:
        for name in ("FRONT", "BACK"):
            service.submit_photo(
                identifier,
                view_type=name,
                capture_id=name,
                image_bytes=photo(),
                expected_revision=service.get(identifier)["revision"],
            )
        service.wait_idle(10)
        assert service.get(identifier)["status"] == "FAILED"
    finally:
        service.close()
    analysis.finish_pair = finish
    before = counts.copy()
    service = DraftService(LocalDraftRepository(root, compact=True), analysis)
    try:
        service.retry_analysis(identifier, expected_revision=service.get(identifier)["revision"])
        service.wait_idle(10)
        assert service.get(identifier)["status"] == "REVIEW_READY"
        assert service.get_result(identifier).tags.sub_category is not None
        assert counts["segmentation"] == before["segmentation"]
        assert counts["marqo"] == before["marqo"]
    finally:
        service.close()
