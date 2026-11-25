"""Reproduce recorded LR margins using cached features, never encoder inference."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

import numpy as np

from gardirop_ai_clothing.config import get_settings
from gardirop_ai_clothing.contracts import FUSION_METHOD, TAXONOMY, VIEW_ORDER, MainCategory
from gardirop_ai_clothing.labeling.artifacts import CLASSIFIER_MODEL_NAME
from gardirop_ai_clothing.labeling.category import SCORE_KIND
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256
from gardirop_ai_clothing.labeling.service import ParentClassificationService, create_parent_service
from gardirop_ai_clothing.model_specs import MARQO_REVISION, PARENT_HEAD_SHA256

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/parent_lr"
SCORE_ATOL = 5e-6


def load_reference(features_path: Path, reference_path: Path) -> tuple[np.ndarray, dict]:
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    for key, expected in {
        "schema_version": 1,
        "classifier_sha256": PARENT_HEAD_SHA256,
        "encoder_revision": MARQO_REVISION,
        "fusion_method": FUSION_METHOD,
        "view_order": list(VIEW_ORDER),
        "score_kind": SCORE_KIND,
        "score_absolute_tolerance": SCORE_ATOL,
        "features_sha256": file_sha256(features_path),
    }.items():
        if reference.get(key) != expected:
            raise ValueError(f"Reference {key} mismatch.")
    cases = reference["cases"]
    if not cases or len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("Reference cases must be nonempty and unique.")
    with np.load(features_path, allow_pickle=False) as data:
        views = data["front_back"].copy()
        if data["case_ids"].tolist() != [c["case_id"] for c in cases]:
            raise ValueError("Reference case/feature alignment mismatch.")
    if views.shape != (len(cases), 2, 768) or views.dtype.kind != "f":
        raise ValueError("Reference must contain paired 768D floating features.")
    for case in cases:
        parent = MainCategory(case["selected_parent"])
        top3 = case["top3"]
        if len(top3) != 3 or len({p["class_id"] for p in top3}) != 3:
            raise ValueError("Reference requires three distinct candidates.")
        for candidate in top3:
            cid = candidate["class_id"]
            if not isinstance(cid, int) or not 0 <= cid < len(TAXONOMY):
                raise ValueError("Reference class ID mismatch.")
            if TAXONOMY[cid] != (parent.value, candidate["label"]):
                raise ValueError("Reference parent/label mismatch.")
            if candidate["score_kind"] != SCORE_KIND or not np.isfinite(candidate["score"]):
                raise ValueError("Reference requires finite margins.")
    return views, reference


def run_smoke(
    features_path: Path,
    reference_path: Path,
    output_dir: Path,
    *,
    service: ParentClassificationService,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "STARTED",
        "scope": "Fusion/LR implementation regression; not accuracy or full pipeline evaluation.",
        "training_run": False,
        "encoder_inference": False,
        "segmentation_run": False,
        "classification_run": True,
        "device": "cpu",
        "encoder_revision": MARQO_REVISION,
        "dimension": 1536,
        "score_kind": SCORE_KIND,
        "score_absolute_tolerance": SCORE_ATOL,
    }
    try:
        views, reference = load_reference(features_path, reference_path)
        classifier = service.manager.get_model(CLASSIFIER_MODEL_NAME)
        if classifier.artifact_sha256 != reference["classifier_sha256"]:
            raise ValueError("Loaded classifier does not match the recorded head.")
        report["classifier_sha256"] = classifier.artifact_sha256
        rows, embeddings, errors = [], [], []
        matched = 0
        for pair, case in zip(views, reference["cases"], strict=True):
            analysis = service.analyze_views(
                front=pair[0],
                back=pair[1],
                main_category=case["selected_parent"],
            )
            result = analysis.classification
            candidates = result.alternatives
            expected = case["top3"]
            ids_match = [c.class_id for c in candidates] == [c["class_id"] for c in expected]
            error = float(
                np.max(
                    np.abs(np.array([c.score for c in candidates]) - [c["score"] for c in expected])
                )
            )
            scores_match = error <= SCORE_ATOL
            matched += int(ids_match and scores_match)
            errors.append(error)
            embeddings.append(analysis.embedding)
            rows.append(
                {
                    "case_id": case["case_id"],
                    "selected_parent": case["selected_parent"],
                    "classification": asdict(result),
                    "recorded_top3": expected,
                    "top3_ids_match": ids_match,
                    "score_max_abs_error": error,
                    "scores_within_tolerance": scores_match,
                }
            )
        matrix = np.stack(embeddings)
        report.update(
            recorded_pairs=len(rows),
            matching_recorded_outputs=matched,
            score_max_abs_error=max(errors),
            max_unit_norm_error=float(np.max(np.abs(np.linalg.norm(matrix, axis=1) - 1))),
            example=rows[0],
        )
        (output_dir / "cases.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if matched != len(rows):
            raise ValueError("LR regression differs from recorded predictions; see cases.json.")
        np.savez_compressed(
            output_dir / "embeddings.npz",
            embeddings=matrix,
            case_ids=np.array([c["case_id"] for c in reference["cases"]]),
        )
        report.update(status="PASSED", cases_file=str(output_dir / "cases.json"))
    except Exception as exc:
        report.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        (output_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check 40 recorded pairs without GPU or downloads."
    )
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    settings = get_settings()
    service = create_parent_service(settings.model_manifest_path)
    output = args.output_dir or settings.output_dir / "parent_lr_smoke" / f"run_{uuid4().hex[:10]}"
    run_smoke(FIXTURES / "recorded_views.npz", FIXTURES / "reference.json", output, service=service)


if __name__ == "__main__":
    main()
