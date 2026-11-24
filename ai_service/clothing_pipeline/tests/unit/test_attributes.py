"""Attribute provenance, foreground isolation and lifecycle integration."""

import hashlib
import io
import json
import zipfile

import numpy as np
import pytest
from PIL import Image
from pydantic import ValidationError

from gardirop_ai_clothing.demo_controller import DemoController
from gardirop_ai_clothing.errors import ModelArtifactError
from gardirop_ai_clothing.jobs import DraftService
from gardirop_ai_clothing.labeling.attribute_bank import (
    ATTRIBUTE_VERSION,
    ENTRIES,
    PROMPTS_SHA256,
    TOKENIZER_REVISION,
    load_bank,
)
from gardirop_ai_clothing.labeling.attributes import AttributeService
from gardirop_ai_clothing.labeling.color import detect_pair_color
from gardirop_ai_clothing.labeling.print_detection import detect_print
from gardirop_ai_clothing.labeling.season import suggest_season
from gardirop_ai_clothing.model_specs import MARQO_REVISION
from gardirop_ai_clothing.schemas import ClothingTags
from gardirop_ai_clothing.storage import LocalDraftRepository


def bank(directory):
    directory.mkdir()
    # Orthogonal synthetic text features test score wiring, not model accuracy.
    vectors = np.eye(len(ENTRIES), 768, dtype=np.float32)
    path = directory / "prototypes.npz"
    np.savez_compressed(
        path, vectors=vectors, labels=np.array([f"{g}:{label}" for g, label, _ in ENTRIES])
    )
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "attribute_version": ATTRIBUTE_VERSION,
                "encoder_revision": MARQO_REVISION,
                "tokenizer_revision": TOKENIZER_REVISION,
                "prompts_sha256": PROMPTS_SHA256,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    )
    return vectors


def test_color_excludes_transparent_rgb_and_weights_views_equally():
    first = Image.new("RGBA", (80, 80), (255, 255, 255, 0))
    for x in range(20, 60):
        for y in range(20, 60):
            first.putpixel((x, y), (190, 25, 35, 255))
    other = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    other.paste(first.crop((20, 20, 60, 60)), (20, 20))
    assert detect_pair_color(first, first) == detect_pair_color(other, other)
    assert detect_pair_color(first, first)["value"] == "Kırmızı"
    blue = Image.new("RGBA", (20, 20), (35, 100, 200, 255))
    result = detect_pair_color(first, blue)
    assert {p["label"] for p in result["palette"]} == {"Kırmızı", "Mavi"}
    assert all(p["foreground_fraction"] == pytest.approx(0.5) for p in result["palette"])
    assert (
        detect_pair_color(Image.new("RGBA", (30, 30)), Image.new("RGBA", (30, 30)))["value"] is None
    )


def test_bank_rejects_wrong_identity_and_corruption(tmp_path):
    directory = tmp_path / "bank"
    bank(directory)
    load_bank(directory)
    metadata = json.loads((directory / "metadata.json").read_text())
    metadata["encoder_revision"] = "0" * 40
    (directory / "metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(ModelArtifactError):
        load_bank(directory)
    metadata["encoder_revision"] = MARQO_REVISION
    (directory / "metadata.json").write_text(json.dumps(metadata))
    (directory / "prototypes.npz").write_bytes(b"corrupt")
    with pytest.raises(ModelArtifactError):
        load_bank(directory)


def test_back_only_print_and_ambiguous_season_remain_separate(tmp_path):
    vectors = bank(tmp_path / "bank")
    front = vectors[5]  # plain front
    back = vectors[6]  # graphic back
    result = detect_print(vectors, front, back)
    assert result["value"] is True
    assert result["decoration_minus_plain"]["front"] < 0
    assert result["decoration_minus_plain"]["back"] > 0
    assert detect_print(vectors, front, front)["value"] is False
    season = suggest_season(vectors, front, back)
    assert season["value"] is None and len(season["candidates"]) == 5
    assert season["threshold_calibrated"] is False
    assert suggest_season(vectors, vectors[0], vectors[0])["value"] == "KIS"


@pytest.mark.parametrize(
    "patch",
    [
        {"user_rating": 0},
        {"user_rating": 6},
        {"user_rating": True},
        {"user_rating": 2.5},
        {"item_status": "FAKE"},
        {"custom_tags": ["a"] * 21},
    ],
)
def test_invalid_user_database_fields_rejected(patch):
    with pytest.raises(ValidationError):
        ClothingTags.model_validate(patch)


def test_all_tags_and_original_scores_survive_edit_restart_and_export(tmp_path, analysis_factory):
    directory = tmp_path / "bank"
    bank(directory)
    analysis, counts = analysis_factory(attributes=AttributeService(directory))
    root = tmp_path / "store"
    service = DraftService(LocalDraftRepository(root), analysis)
    controller = DemoController(service, tmp_path / "exports")
    draft_id = service.create_draft("üst")["id"]
    try:
        stream = io.BytesIO()
        Image.new("RGB", (40, 60), (190, 25, 35)).save(stream, format="PNG")
        for view in ("FRONT", "BACK"):
            service.submit_photo(
                draft_id,
                view_type=view,
                capture_id=view,
                image_bytes=stream.getvalue(),
                expected_revision=service.get(draft_id)["revision"],
            )
        service.wait_idle(10)
        original = service.get_result(draft_id)
        assert original.tags.color == "Kırmızı"
        assert original.tags.user_rating is original.tags.item_status is None
        assert len(original.model_diagnostics["classification"]["alternatives"]) == 9
        assert len(original.model_diagnostics["attributes"]["season"]["candidates"]) == 5
        assert len(original.model_diagnostics["attributes"]["has_print"]["candidates"]) == 8
        service.edit_tags(
            draft_id,
            {
                "color": "Bordo",
                "user_rating": 5,
                "item_status": "KIRLI",
                "custom_tags": ["favori", "spor"],
            },
            expected_revision=original.draft_revision,
        )
        repeated = service.edit_tags(
            draft_id,
            {
                "color": "Bordo",
                "user_rating": 5,
                "item_status": "KIRLI",
                "custom_tags": ["favori", "spor"],
            },
            expected_revision=original.draft_revision,
        )
        assert repeated["revision"] == original.draft_revision + 1
        snapshot = controller.snapshot(draft_id)
        rows = controller.tag_sources(snapshot)
        assert len(rows) == 8
        assert next(r for r in rows if r[0] == "Renk")[1:] == [
            "Kırmızı",
            "Bordo",
            "Kullanıcı düzeltmesi",
        ]
        current = service.get_result(draft_id)
        assert current.model_diagnostics == original.model_diagnostics
        assert current.embedding == original.embedding and counts["marqo"] == 2
    finally:
        service.close()
    with DraftService(LocalDraftRepository(root), analysis) as restarted:
        controller = DemoController(restarted, tmp_path / "exports")
        result = restarted.get_result(draft_id)
        path = controller.confirm_and_export(
            draft_id, result.tags.model_dump(), expected_revision=result.draft_revision
        )
        with zipfile.ZipFile(path) as archive:
            saved = json.loads(archive.read("result.json"))
            assert saved["tags"]["item_status"] == "KIRLI"
            assert saved["tags"]["custom_tags"] == ["favori", "spor"]
            assert saved["model_diagnostics"]["original_tags"]["color"] == "Kırmızı"
        assert counts["marqo"] == 2


@pytest.mark.parametrize("rgb", [(65, 90, 110), (110, 135, 155), (95, 120, 140)])
def test_muted_denim_is_blue_instead_of_neutral_gray(rgb):
    image = Image.new("RGBA", (40, 50), (*rgb, 255))
    result = detect_pair_color(image, image)
    assert result["value"] == "Mavi"
    assert result["palette_version"] == "foreground-lab-palette-v2-muted-blue"


@pytest.mark.parametrize("rgb", [(65, 65, 65), (110, 110, 110), (175, 175, 175)])
def test_neutral_gray_does_not_become_denim_blue(rgb):
    image = Image.new("RGBA", (40, 50), (*rgb, 255))
    assert detect_pair_color(image, image)["value"] == "Gri"


def test_single_view_fabric_pattern_abstains_but_back_only_logo_remains_suggested(tmp_path):
    vectors = bank(tmp_path / "bank")
    plain = vectors[5]
    checked = vectors[9]
    result = detect_print(vectors, plain, checked)
    assert result["value"] is None
    assert result["leading_pattern"] == "checked"
    assert result["decision_reason"] == "single_view_fabric_pattern_needs_review"
    assert detect_print(vectors, checked, checked)["value"] is True
    assert detect_print(vectors, plain, vectors[7])["value"] is True
