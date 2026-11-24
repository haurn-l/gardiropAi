"""One real local draft lifecycle. This scratch repository is separate from the app."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from gardirop_ai_clothing.config import get_settings
from gardirop_ai_clothing.jobs import create_draft_service

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/pipeline"


def run_smoke(service, output: Path) -> dict:
    report = {
        "status": "STARTED",
        "scope": "One local draft lifecycle; not accuracy or throughput evaluation.",
        "training_run": False,
        "backend_connected": False,
        "local_confirmation_only": True,
        "steps": [],
    }
    try:
        draft = service.create_draft("üst")
        draft_id = draft["id"]
        report["draft_id"] = draft_id
        report["repository"] = str(service.repository.root)
        front_bytes = (FIXTURES / "G001_front_raw.jpg").read_bytes()
        front = service.submit_photo(
            draft_id,
            view_type="FRONT",
            capture_id="demo-front",
            image_bytes=front_bytes,
            expected_revision=draft["revision"],
        )
        duplicate = service.submit_photo(
            draft_id,
            view_type="FRONT",
            capture_id="demo-front",
            image_bytes=front_bytes,
            expected_revision=draft["revision"],
        )
        if duplicate["id"] != front["id"]:
            raise AssertionError("Duplicate upload opened a second job.")
        report["duplicate_upload_same_job"] = True
        print(
            "Front submitted; background worker starts before the back photo arrives.", flush=True
        )
        service.wait_idle(timeout=120)
        draft = service.get(draft_id)
        if draft["jobs"][front["id"]]["status"] != "READY" or draft["status"] != "WAITING_VIEWS":
            raise AssertionError(f"Front job failed: {draft['jobs'][front['id']]}")
        report["steps"].append("FRONT_READY_WITHOUT_BACK")
        service.submit_photo(
            draft_id,
            view_type="BACK",
            capture_id="demo-back",
            image_bytes=(FIXTURES / "G001_back_raw.jpg").read_bytes(),
            expected_revision=draft["revision"],
        )
        service.wait_idle(timeout=120)
        draft = service.get(draft_id)
        result = service.get_result(draft_id)
        report["steps"].append("REVIEW_READY")
        report["suggested_tags"] = result.tags.model_dump(mode="json")
        # Explicit manual example, not an inferred colour or a dataset truth label.
        service.edit_tags(
            draft_id, {"color": "kullanıcı-demo"}, expected_revision=draft["revision"]
        )
        draft = service.get(draft_id)
        edited = service.get_result(draft_id)
        if result.embedding != edited.embedding:
            raise AssertionError("Manual tag edit changed the embedding.")
        report["steps"].append("USER_TAG_EDIT_WITHOUT_ENCODER")
        confirmed = service.confirm(draft_id, expected_revision=draft["revision"])
        repeated = service.confirm(draft_id, expected_revision=draft["revision"])
        if repeated != confirmed:
            raise AssertionError("Duplicate confirmation changed the result.")
        report["steps"].append("CONFIRMED_LOCALLY")
        report.update(
            status="PASSED",
            final_status=service.get(draft_id)["status"],
            duplicate_confirmation_same_result=True,
            dimension=len(confirmed.embedding),
            final_revision=confirmed.draft_revision,
            manual_color_source="explicit demo user edit, not AI",
            confirmed_tags=confirmed.tags.model_dump(mode="json"),
            result_file=str(service.repository.path(service.get(draft_id)["result_path"])),
            health=service.health(),
        )
        if report["health"]["worker_errors"]:
            raise AssertionError("Worker reported unexpected internal errors.")
    except Exception as exc:
        report.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Run real models through one isolated local draft."
    )
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    settings = get_settings()
    output = args.output_dir or settings.output_dir / "draft_smoke" / f"run_{uuid4().hex[:10]}"
    output.mkdir(parents=True, exist_ok=False)
    settings = settings.model_copy(
        update={"draft_root": output / "store", "device": args.device or settings.device}
    )
    print(
        "Real local models; no training/backend. Sample raw photos remain sideways. First load can take time.",
        flush=True,
    )
    with create_draft_service(settings) as service:
        run_smoke(service, output)


if __name__ == "__main__":
    main()
