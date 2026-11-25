"""Quality comparison must detect changed tags, pixels and embeddings."""

import json

import pytest
from PIL import Image

from gardirop_ai_clothing.benchmark_comparison import compare_delivery_runs


def runs(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    for root in (old, new):
        root.mkdir()
        (root / "report.json").write_text(json.dumps({"status": "COMPLETED"}))
        for name in ("tshirt", "jeans", "jacket"):
            folder = root / "cases" / name
            folder.mkdir(parents=True)
            (folder / "result.json").write_text(
                json.dumps({"tags": {"color": "Mavi"}, "versions": {"encoder": "fixed"}})
            )
            (folder / "embedding.json").write_text(json.dumps({"values": [1.0] + [0.0] * 1535}))
            for view in ("front", "back"):
                Image.new("RGB", (16, 16), "white").save(folder / f"{view}.webp", lossless=True)
    return old, new


def test_equal_runs_are_accepted(tmp_path):
    old, new = runs(tmp_path)
    result = compare_delivery_runs(old, new)
    assert result["all_checks_passed"] is True


@pytest.mark.parametrize("change", ["tag", "embedding", "pixels"])
def test_output_regressions_are_rejected(tmp_path, change):
    old, new = runs(tmp_path)
    case = new / "cases" / "jacket"
    if change == "tag":
        record = json.loads((case / "result.json").read_text())
        record["tags"]["color"] = "Gri"
        (case / "result.json").write_text(json.dumps(record))
    elif change == "embedding":
        (case / "embedding.json").write_text(json.dumps({"values": [0.0, 1.0] + [0.0] * 1534}))
    else:
        Image.new("RGB", (16, 16), "red").save(case / "front.webp", lossless=True)
    assert compare_delivery_runs(old, new)["all_checks_passed"] is False
