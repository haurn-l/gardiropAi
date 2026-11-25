"""Run the packaged lifecycle scenario with synthetic analysis runners."""

import importlib.util
import json
from pathlib import Path

import pytest

from gardirop_ai_clothing.jobs import DraftService
from gardirop_ai_clothing.storage import LocalDraftRepository

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("smoke_drafts", ROOT / "scripts/smoke_drafts.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_lifecycle_scenario_confirms_once_with_two_encoder_calls(
    tmp_path, analysis_factory, monkeypatch, synthetic_photo_files
):
    monkeypatch.setattr(module, "FIXTURES", synthetic_photo_files)
    analysis, counts = analysis_factory()
    output = tmp_path / "run"
    output.mkdir()
    with DraftService(LocalDraftRepository(output / "store"), analysis) as service:
        report = module.run_smoke(service, output)
        assert report["status"] == "PASSED" and report["final_status"] == "CONFIRMED"
        assert report["duplicate_upload_same_job"] and report["duplicate_confirmation_same_result"]
        assert report["dimension"] == 1536 and report["final_revision"] == 4
        assert counts["marqo"] == counts["segmentation"] == 2
        assert Path(report["result_file"]).is_file()


def test_failed_front_produces_failed_smoke_report(
    tmp_path, analysis_factory, monkeypatch, synthetic_photo_files
):
    monkeypatch.setattr(module, "FIXTURES", synthetic_photo_files)
    analysis, _ = analysis_factory()

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic model error")

    analysis.prepare_view = fail
    output = tmp_path / "run"
    output.mkdir()
    with DraftService(LocalDraftRepository(output / "store"), analysis) as service:
        with pytest.raises(AssertionError, match="Front job failed"):
            module.run_smoke(service, output)
    report = json.loads((output / "report.json").read_text())
    assert report["status"] == "FAILED" and "result_file" not in report
