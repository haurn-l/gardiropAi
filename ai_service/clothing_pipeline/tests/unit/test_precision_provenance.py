"""Preserve stored precision and reject mixed-view pairs without neural reruns."""

import io
from dataclasses import replace

import pytest
from PIL import Image

from gardirop_ai_clothing.analysis import create_analysis_service
from gardirop_ai_clothing.config import Settings
from gardirop_ai_clothing.errors import ConfigurationError, ModelArtifactError
from gardirop_ai_clothing.storage import LocalDraftRepository


def view(analysis):
    data = io.BytesIO()
    Image.new("RGB", (40, 60), "red").save(data, format="PNG")
    return analysis.prepare_view(data.getvalue(), view_type="FRONT")


@pytest.mark.parametrize("compact", [False, True])
@pytest.mark.parametrize("precision", ["fp32", "fp16"])
def test_stored_precision_survives_close_reopen(tmp_path, analysis_factory, compact, precision):
    analysis, _ = analysis_factory()
    original = replace(view(analysis), encoder_precision=precision)
    root = tmp_path / "store"
    repo = LocalDraftRepository(root, compact=compact)
    try:
        repo.create({"id": "a" * 32})
        path = repo.save_view("a" * 32, "b" * 32, 1, original)
    finally:
        repo.close()
    repo = LocalDraftRepository(root, compact=compact)
    try:
        assert repo.load_view(path).encoder_precision == precision
    finally:
        repo.close()


@pytest.mark.parametrize("compact", [False, True])
def test_legacy_precision_defaults_to_fp32(tmp_path, analysis_factory, compact):
    analysis, _ = analysis_factory()
    repo = LocalDraftRepository(tmp_path / "store", compact=compact)
    try:
        repo.create({"id": "a" * 32})
        path = repo.save_view("a" * 32, "b" * 32, 1, view(analysis))
        record = repo.read_json(f"{path}/view.json")
        record.pop("encoder_precision")
        repo.write_json(f"{path}/view.json", record)
        assert repo.load_view(path).encoder_precision == "fp32"
    finally:
        repo.close()


def test_mixed_precisions_are_rejected_before_lr(tmp_path, analysis_factory):
    analysis, counts = analysis_factory()
    front = view(analysis)
    back = replace(front, view_type=type(front.view_type).BACK, encoder_precision="fp16")
    before = counts.copy()
    with pytest.raises(ValueError, match="precisions differ"):
        analysis.finish_pair(front=front, back=back, main_category="üst")
    assert counts == before


@pytest.mark.parametrize("precision", ["auto", "fp32", "fp16"])
def test_auto_is_the_default_and_explicit_precision_is_forwarded(monkeypatch, precision):
    from gardirop_ai_clothing import analysis as module

    monkeypatch.delenv("GARDROPAI_MARQO_PRECISION", raising=False)
    assert Settings(_env_file=None).marqo_precision == "auto"
    captured = []

    def load(path, *, device, precision):
        captured.append((device, precision))
        raise ConfigurationError("synthetic sentinel")

    monkeypatch.setattr(module, "load_marqo_encoder", load)
    service = create_analysis_service(
        Settings(_env_file=None, device="cuda", marqo_precision=precision)
    )
    with pytest.raises(ModelArtifactError, match="Failed to load"):
        service.manager.get_model("marqo_fashionsiglip")
    assert captured == [("cuda", precision)]
