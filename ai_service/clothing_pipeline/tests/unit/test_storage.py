"""Local persistence is non-pickled, checked, atomic, and owned by one process."""

import io

import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing.errors import DraftNotFoundError, LocalStorageError
from gardirop_ai_clothing.storage import LocalDraftRepository


def photo():
    buffer = io.BytesIO()
    Image.new("RGB", (40, 60), (200, 20, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_view_roundtrip_preserves_features_and_image_products(tmp_path, analysis_factory):
    service, _ = analysis_factory()
    original = service.prepare_view(photo(), view_type="FRONT")
    repo = LocalDraftRepository(tmp_path)
    try:
        draft_id, job_id = "a" * 32, "b" * 32
        repo.create({"id": draft_id})
        relative = repo.save_view(draft_id, job_id, 1, original)
        loaded = repo.load_view(relative)
        assert loaded.view_type == original.view_type and loaded.options == original.options
        np.testing.assert_array_equal(loaded.embedding, original.embedding)
        np.testing.assert_array_equal(loaded.prepared.raw_alpha, original.prepared.raw_alpha)
        np.testing.assert_array_equal(loaded.prepared.final_alpha, original.prepared.final_alpha)
        np.testing.assert_array_equal(loaded.prepared.white_rgb, original.prepared.white_rgb)
        assert loaded.prepared.transparent_webp == original.prepared.transparent_webp
        assert loaded.prepared.white_webp == original.prepared.white_webp
        assert loaded.prepared.delivery_webp == (repo.path(relative) / "clean.webp").read_bytes()
        with Image.open(io.BytesIO(loaded.prepared.delivery_webp)) as image:
            assert image.mode == "RGB"
            np.testing.assert_array_equal(image, original.prepared.white_rgb)
        assert loaded.prepared.source_size == original.prepared.source_size
        assert not loaded.embedding.flags.writeable
        (repo.path(relative) / "clean.webp").write_bytes(b"changed")
        with pytest.raises(LocalStorageError, match="SHA256"):
            repo.load_view(relative)
    finally:
        repo.close()


def test_repository_rejects_second_owner_and_can_reopen_after_release(tmp_path):
    first = LocalDraftRepository(tmp_path)
    try:
        with pytest.raises(LocalStorageError, match="owned"):
            LocalDraftRepository(tmp_path)
        first.create({"id": "a" * 32, "revision": 1})
    finally:
        first.close()
    second = LocalDraftRepository(tmp_path)
    try:
        assert second.get("a" * 32)["revision"] == 1
        with pytest.raises(LocalStorageError, match="closed"):
            first.get("a" * 32)
    finally:
        second.close()


@pytest.mark.parametrize("bad", ["../../etc", "", "a" * 33, "/tmp/draft"])
def test_draft_id_cannot_be_a_filesystem_path(tmp_path, bad):
    repo = LocalDraftRepository(tmp_path)
    try:
        with pytest.raises(DraftNotFoundError):
            repo.get(bad)
        with pytest.raises(LocalStorageError, match="escapes"):
            repo.path("../../outside")
    finally:
        repo.close()


def test_failed_json_write_keeps_previous_record(tmp_path):
    repo = LocalDraftRepository(tmp_path)
    try:
        record = {"id": "a" * 32, "revision": 1}
        repo.create(record)
        with pytest.raises(ValueError):
            repo.save({**record, "bad": float("nan")})
        assert repo.get(record["id"]) == record
        assert not list(repo.draft_dir(record["id"]).glob(".write-*"))
    finally:
        repo.close()


@pytest.mark.parametrize("job_id,attempt", [("../escape", 1), ("b" * 32, 0)])
def test_view_job_paths_and_attempts_are_validated_before_writing(tmp_path, job_id, attempt):
    repo = LocalDraftRepository(tmp_path)
    try:
        with pytest.raises(LocalStorageError):
            repo.save_view("a" * 32, job_id, attempt, None)
        assert not list((tmp_path / "drafts").iterdir())
    finally:
        repo.close()


def test_pre_white_migration_record_stays_readable_and_keeps_original_delivery_bytes(
    tmp_path, analysis_factory
):
    from gardirop_ai_clothing.storage import sha256

    service, _ = analysis_factory()
    original = service.prepare_view(photo(), view_type="FRONT")
    repo = LocalDraftRepository(tmp_path)
    try:
        draft_id, job_id = "a" * 32, "b" * 32
        repo.create({"id": draft_id})
        relative = repo.save_view(draft_id, job_id, 1, original)
        # Reconstruct the exact pre-migration record layout.
        old_bytes = original.prepared.transparent_webp
        (repo.path(relative) / "clean.webp").write_bytes(old_bytes)
        record = repo.read_json(f"{relative}/view.json")
        record.pop("image_output")
        record["files"]["clean.webp"] = sha256(repo.path(f"{relative}/clean.webp"))
        repo.write_json(f"{relative}/view.json", record)
        loaded = repo.load_view(relative)
        assert loaded.prepared.white_webp is None
        assert loaded.prepared.delivery_profile == "legacy-transparent-webp"
        assert loaded.prepared.delivery_webp == old_bytes
        np.testing.assert_array_equal(loaded.embedding, original.embedding)
    finally:
        repo.close()
