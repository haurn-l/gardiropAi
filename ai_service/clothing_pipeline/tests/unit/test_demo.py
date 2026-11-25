"""Local UI actions and portable export with synthetic neural runners only."""

import hashlib
import io
import json
import os
import zipfile

import gradio as gr
import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing.demo_controller import DemoController
from gardirop_ai_clothing.errors import DraftConflictError, ImageProcessingError, LocalStorageError
from gardirop_ai_clothing.exports import EXPORT_FILES, export_confirmed_draft
from gardirop_ai_clothing.jobs import DraftService
from gardirop_ai_clothing.local_demo import (
    build_demo,
    empty_session,
    hydrate_tags,
    preview_image,
    review_revision,
)
from gardirop_ai_clothing.schemas import ClothingAnalysisResult
from gardirop_ai_clothing.storage import LocalDraftRepository


@pytest.fixture
def environment(tmp_path, analysis_factory):
    analysis, calls = analysis_factory()
    service = DraftService(LocalDraftRepository(tmp_path / "store"), analysis)
    controller = DemoController(service, tmp_path / "exports")
    paths = []
    for name, color in (("front", (220, 20, 30)), ("back", (20, 30, 220))):
        path = tmp_path / f"{name}.png"
        Image.new("RGB", (40, 60), color).save(path)
        paths.append(path)
    yield service, controller, calls, paths
    service.close()


def ready(environment):
    service, controller, _, paths = environment
    draft_id = service.create_draft("üst")["id"]
    for view, path in zip(("FRONT", "BACK"), paths, strict=True):
        controller.upload(draft_id, view, path, expected_revision=service.get(draft_id)["revision"])
    service.wait_idle(10)
    return draft_id


def test_confirm_saves_visible_unsaved_tags_and_export_is_portable_and_idempotent(environment):
    service, controller, counts, _ = environment
    draft_id = ready(environment)
    before = service.get_result(draft_id)
    tags = {**before.tags.model_dump(), "color": "mavi", "has_print": False}
    path = controller.confirm_and_export(draft_id, tags, expected_revision=before.draft_revision)
    saved = service.get_result(draft_id)
    assert saved.tags.color == "mavi" and saved.tags.has_print is False
    assert saved.embedding == before.embedding and counts["marqo"] == 2
    with zipfile.ZipFile(path) as archive:
        assert set(archive.namelist()) == EXPORT_FILES and archive.testzip() is None
        result = ClothingAnalysisResult.model_validate_json(archive.read("result.json"))
        assert result.front_image_ref == "front.webp" and result.back_image_ref == "back.webp"
        assert result.tags == saved.tags and result.embedding == saved.embedding
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["backend_persisted"] is False
        assert manifest["user_tag_overrides"]["color"] == "mavi"
        for name, expected in manifest["files_sha256"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected
        with np.load(io.BytesIO(archive.read("embedding.npz")), allow_pickle=False) as arrays:
            assert arrays["embedding"].shape == (1536,) and arrays["embedding"].dtype == np.float32
            assert arrays["view_order"].tolist() == ["FRONT", "BACK"]
            np.testing.assert_allclose(arrays["embedding"], saved.embedding, atol=1e-7, rtol=0)
            assert arrays["front"][0] == 1 and arrays["back"][2] == 1
    # Existing verified exports are returned without rewriting the file.
    os.utime(path, ns=(1_000_000_000, 1_000_000_000))
    assert (
        controller.confirm_and_export(draft_id, tags, expected_revision=saved.draft_revision)
        == path
    )
    assert path.stat().st_mtime_ns == 1_000_000_000
    assert len(list(controller.export_dir.glob("*.zip"))) == 1
    assert service.get_result(draft_id).front_image_ref == saved.front_image_ref


def test_export_refuses_unconfirmed_or_stale_revisions(environment):
    service, controller, _, _ = environment
    draft_id = ready(environment)
    result = service.get_result(draft_id)
    with pytest.raises(DraftConflictError):
        export_confirmed_draft(
            service, draft_id, controller.export_dir, expected_revision=result.draft_revision
        )
    service.confirm(draft_id, expected_revision=result.draft_revision)
    with pytest.raises(DraftConflictError):
        export_confirmed_draft(
            service, draft_id, controller.export_dir, expected_revision=result.draft_revision - 1
        )
    assert not controller.export_dir.exists()


def test_export_refuses_corrupt_view_or_existing_zip(environment):
    service, controller, _, _ = environment
    draft_id = ready(environment)
    result = service.get_result(draft_id)
    path = controller.confirm_and_export(
        draft_id, result.tags.model_dump(), expected_revision=result.draft_revision
    )
    path.write_bytes(b"not a ZIP")
    with pytest.raises(LocalStorageError, match="corrupt"):
        export_confirmed_draft(
            service, draft_id, controller.export_dir, expected_revision=result.draft_revision
        )
    path.unlink()
    service.repository.path(result.front_image_ref).write_bytes(b"corrupt photo")
    with pytest.raises(LocalStorageError, match="SHA256"):
        export_confirmed_draft(
            service, draft_id, controller.export_dir, expected_revision=result.draft_revision
        )
    assert not list(controller.export_dir.glob("*.zip"))


def test_export_refuses_embedding_from_different_views_even_with_valid_norm(environment):
    service, controller, _, _ = environment
    draft_id = ready(environment)
    result = service.get_result(draft_id)
    service.confirm(draft_id, expected_revision=result.draft_revision)
    state = service.get(draft_id)
    tampered = result.model_copy(update={"embedding": tuple(-x for x in result.embedding)})
    service.repository.write_json(state["result_path"], tampered.model_dump(mode="json"))
    with pytest.raises(LocalStorageError, match="does not match"):
        export_confirmed_draft(
            service, draft_id, controller.export_dir, expected_revision=result.draft_revision
        )


def test_snapshot_shows_ready_front_before_back_and_retake_clears_front_only(environment):
    service, controller, _, paths = environment
    draft_id = service.create_draft("üst")["id"]
    controller.upload(draft_id, "FRONT", paths[0], expected_revision=1, rotation=90)
    service.wait_idle(10)
    snapshot = controller.snapshot(draft_id)
    assert snapshot["previews"]["FRONT"] and snapshot["previews"]["BACK"] is None
    assert snapshot["state"]["status"] == "WAITING_VIEWS"
    job = snapshot["state"]["jobs"][snapshot["state"]["views"]["FRONT"]]
    assert job["options"]["manual_rotation"] == 90 and job["options"]["auto_align"] is False


def test_upload_size_and_stale_confirmation_do_not_change_draft(environment, tmp_path):
    service, controller, _, _ = environment
    draft_id = ready(environment)
    before = service.get(draft_id)
    service.analysis.images.max_upload_bytes = 1
    oversized = tmp_path / "big.png"
    oversized.write_bytes(b"abc")
    with pytest.raises(ImageProcessingError):
        controller.upload(draft_id, "FRONT", oversized, expected_revision=before["revision"])
    with pytest.raises(DraftConflictError):
        controller.confirm_and_export(
            draft_id,
            controller.snapshot(draft_id)["tags"],
            expected_revision=before["revision"] - 1,
        )
    assert service.get(draft_id) == before


def test_poll_hydration_and_browser_revision_are_separate():
    session = {**empty_session("draft-a"), "hydrated": ["draft-a", 3]}
    assert not hydrate_tags(session, "draft-a", 3)
    assert hydrate_tags(session, "draft-a", 4)
    assert review_revision(session, {"id": "draft-a", "revision": 3}) == ("draft-a", 3)
    with pytest.raises(DraftConflictError):
        review_revision(session, {"id": "draft-b", "revision": 3})


def test_ui_callbacks_preserve_typed_fields_and_confirm_visible_labels(environment):
    service, controller, counts, paths = environment
    app = build_demo(controller)
    blocks = list(app.blocks.values())
    state_component = next(c for c in blocks if isinstance(c, gr.State))
    token_component = next(c for c in blocks if isinstance(c, gr.JSON))
    color_component = next(c for c in blocks if getattr(c, "label", None) == "Renk")

    def callback(component, event):
        dependency = next(
            d
            for d in app.config["dependencies"]
            if (component._id, event) in [tuple(t) for t in d["targets"]]
        )
        return app.fns[dependency["id"]].fn

    new = next(c for c in blocks if getattr(c, "value", None) == "Yeni kıyafet")
    answer = callback(new, "click")("üst")
    current, token = answer[state_component], answer[token_component]
    for title, path in zip(("Ön", "Arka"), paths, strict=True):
        upload = next(
            c for c in blocks if getattr(c, "label", None) == f"{title} fotoğrafı seç / yeniden çek"
        )
        answer = callback(upload, "upload")(str(path), 0, "üst", current, token)
        current = answer[state_component]
        service.wait_idle(10)
        timer = next(c for c in blocks if isinstance(c, gr.Timer))
        answer = callback(timer, "tick")(current)
        current, token = answer[state_component], answer[token_component]
    # Once hydrated, another poll must omit field values to keep browser edits.
    answer = callback(timer, "tick")(current)
    assert "value" not in answer[color_component]
    current = answer[state_component]
    confirm = next(c for c in blocks if getattr(c, "value", None) == "Onayla ve ZIP indir")
    old_token = token.copy()
    answer = callback(confirm, "click")(
        "üst", "Bluz", "mavi", "yaz", "no", 4, "TEMIZ", "rahat, favori", current, token
    )
    current, token = answer[state_component], answer[token_component]
    saved = service.get_result(current["id"])
    assert (
        saved.tags.sub_category == "Bluz"
        and saved.tags.color == "mavi"
        and saved.tags.has_print is False
        and saved.tags.user_rating == 4
        and saved.tags.item_status == "TEMIZ"
        and saved.tags.custom_tags == ("rahat", "favori")
    )
    assert service.get(current["id"])["status"] == "CONFIRMED" and counts["marqo"] == 2
    with pytest.raises(gr.Error):
        callback(confirm, "click")(
            "üst", "Bluz", "mavi", "yaz", "no", 4, "TEMIZ", "rahat, favori", current, old_token
        )
    assert all(d["api_visibility"] == "private" for d in app.config["dependencies"])


def test_legacy_confirmed_export_remains_byte_compatible(environment):
    service, controller, _, _ = environment
    draft_id = ready(environment)
    result = service.get_result(draft_id)
    state = service.get(draft_id)
    raw = service.repository.read_json(state["result_path"])
    raw.pop("model_diagnostics")
    for name in ("user_rating", "item_status", "custom_tags"):
        raw["tags"].pop(name)
    service.repository.write_json(state["result_path"], raw)
    service.confirm(draft_id, expected_revision=result.draft_revision)
    path = export_confirmed_draft(
        service, draft_id, controller.export_dir, expected_revision=result.draft_revision
    )
    before = path.read_bytes()
    assert (
        export_confirmed_draft(
            service, draft_id, controller.export_dir, expected_revision=result.draft_revision
        ).read_bytes()
        == before
    )
    with zipfile.ZipFile(path) as archive:
        saved = json.loads(archive.read("result.json"))
        assert "model_diagnostics" not in saved and "user_rating" not in saved["tags"]


def test_preview_stored_primary_file_and_export_all_contain_real_white_pixels(environment):
    service, controller, counts, _ = environment
    draft_id = ready(environment)
    snap = controller.snapshot(draft_id)
    state = service.get(draft_id)
    for side in ("FRONT", "BACK"):
        with Image.open(snap["previews"][side]) as image:
            assert image.format == "WEBP" and image.mode == "RGB"
            assert image.width == image.height
            assert image.getpixel((0, 0)) == (255, 255, 255)
        job = state["jobs"][state["views"][side]]
        view = service.repository.load_view(job["view_path"])
        with Image.open(snap["previews"][side]) as image:
            np.testing.assert_array_equal(image, view.prepared.white_rgb)
    current = service.get_result(draft_id)
    path = controller.confirm_and_export(
        draft_id, current.tags.model_dump(), expected_revision=current.draft_revision
    )
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        for side, filename in [("FRONT", "front.webp"), ("BACK", "back.webp")]:
            assert manifest["image_output"][side]["background"] == "#FFFFFF"
            assert manifest["image_output"][side]["lossless"] is True
            with Image.open(io.BytesIO(archive.read(filename))) as image:
                assert image.mode == "RGB" and image.getpixel((0, 0)) == (255, 255, 255)
            job = state["jobs"][state["views"][side]]
            assert (
                archive.read(filename)
                == service.repository.path(f"{job['view_path']}/clean.webp").read_bytes()
            )
    assert counts["segmentation"] == counts["marqo"] == 2


def test_preview_download_is_full_resolution_lossless_png(environment, monkeypatch, tmp_path):
    monkeypatch.setenv("GRADIO_TEMP_DIR", str(tmp_path / "gradio"))
    _, controller, _, _ = environment
    app = build_demo(controller)
    previews = [
        block
        for block in app.blocks.values()
        if isinstance(block, gr.Image) and block.label.startswith("Temizlenmiş")
    ]
    assert len(previews) == 2
    # High frequency texture detects accidental lossy recompression, unlike flat colors.
    pixels = np.random.default_rng(7).integers(0, 256, (811, 1237, 3), dtype=np.uint8)
    image = Image.fromarray(pixels)
    for component in previews:
        assert component.format == "png" and component.image_mode == "RGB"
        saved = component.postprocess(image)
        with Image.open(saved.path) as actual:
            assert actual.format == "PNG" and actual.size == image.size
            np.testing.assert_array_equal(actual, pixels)


def test_legacy_transparent_preview_is_white_without_changing_saved_record(tmp_path):
    path = tmp_path / "old.png"
    image = Image.new("RGBA", (123, 157), (15, 25, 35, 0))
    image.putpixel((60, 70), (30, 50, 80, 255))
    image.putpixel((61, 70), (255, 0, 0, 128))
    image.save(path)
    original_bytes = path.read_bytes()
    actual = preview_image(path)
    assert actual.mode == "RGB" and actual.size == (123, 157)
    assert actual.getpixel((0, 0)) == (255, 255, 255)
    assert actual.getpixel((60, 70)) == (30, 50, 80)
    assert actual.getpixel((61, 70)) == (255, 127, 127)
    assert path.read_bytes() == original_bytes
