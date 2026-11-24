"""Force reorder/retake/cancel/restart races without GPU inference or sleeps."""

import io
from threading import Event

import numpy as np
import pytest
from PIL import Image
from pydantic import ValidationError

from gardirop_ai_clothing.errors import DraftConflictError, DraftNotFoundError, JobQueueFullError
from gardirop_ai_clothing.jobs import DraftService
from gardirop_ai_clothing.storage import LocalDraftRepository


def photo(color=(220, 20, 30)):
    buffer = io.BytesIO()
    Image.new("RGB", (40, 60), color).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def lifecycle(tmp_path, analysis_factory):
    instances, releases = [], []

    def make(root=None, **kwargs):
        analysis, counts = analysis_factory()
        service = DraftService(
            LocalDraftRepository(root or tmp_path / str(len(instances))), analysis, **kwargs
        )
        instances.append(service)
        return service, counts

    def block(service, method="prepare_view"):
        entered, release = Event(), Event()
        releases.append(release)
        original = getattr(service.analysis, method)

        def run(*args, **kwargs):
            entered.set()
            assert release.wait(10)
            return original(*args, **kwargs)

        setattr(service.analysis, method, run)
        return entered, release

    yield make, block
    for release in releases:
        release.set()
    for service in instances:
        service.close(timeout=15)


def submit(service, draft_id, view, capture, *, data=None):
    state = service.get(draft_id)
    return service.submit_photo(
        draft_id,
        view_type=view,
        capture_id=capture,
        image_bytes=data or photo(),
        expected_revision=state["revision"],
    )


def ready_pair(service, *, back_first=False):
    state = service.create_draft("üst")
    draft_id = state["id"]
    for view in ("BACK", "FRONT") if back_first else ("FRONT", "BACK"):
        submit(service, draft_id, view, view)
    service.wait_idle(10)
    assert service.get(draft_id)["status"] == "REVIEW_READY", service.get(draft_id)
    return draft_id


@pytest.mark.parametrize("back_first", [False, True])
def test_upload_order_does_not_change_front_back_binding(lifecycle, back_first):
    make, _ = lifecycle
    service, counts = make()
    draft_id = ready_pair(service, back_first=back_first)
    state = service.get(draft_id)
    result = service.get_result(draft_id)
    assert counts["marqo"] == counts["segmentation"] == 2
    assert result.draft_revision == state["revision"] == 3
    for view, reference in (("FRONT", result.front_image_ref), ("BACK", result.back_image_ref)):
        assert state["views"][view] in reference


def test_front_starts_immediately_and_duplicate_request_does_not_consume_capacity(lifecycle):
    make, block = lifecycle
    service, counts = make(max_pending_jobs=1)
    entered, release = block(service)
    draft_id = service.create_draft("üst")["id"]
    job = submit(service, draft_id, "FRONT", "capture1")
    assert entered.wait(5)
    duplicate = service.submit_photo(
        draft_id, view_type="FRONT", capture_id="capture1", image_bytes=photo(), expected_revision=1
    )
    assert duplicate["id"] == job["id"]
    assert service.get(draft_id)["revision"] == 2
    with pytest.raises(DraftConflictError, match="different"):
        service.submit_photo(
            draft_id,
            view_type="FRONT",
            capture_id="capture1",
            image_bytes=photo((20, 30, 220)),
            expected_revision=2,
        )
    with pytest.raises(JobQueueFullError):
        submit(service, draft_id, "BACK", "back1")
    assert "BACK" not in service.get(draft_id)["views"]
    release.set()
    service.wait_idle(10)
    assert counts["marqo"] == 1 and service.get(draft_id)["status"] == "WAITING_VIEWS"


def test_late_front_completion_cannot_replace_a_new_capture(lifecycle):
    make, block = lifecycle
    service, counts = make()
    entered, release = block(service)
    draft_id = service.create_draft("üst")["id"]
    old = submit(service, draft_id, "FRONT", "old")
    assert entered.wait(5)
    new = submit(service, draft_id, "FRONT", "new", data=photo((20, 30, 220)))
    back = submit(service, draft_id, "BACK", "back")
    release.set()
    service.wait_idle(10)
    state, result = service.get(draft_id), service.get_result(draft_id)
    assert state["jobs"][old["id"]]["status"] == "DISCARDED"
    assert state["views"] == {"FRONT": new["id"], "BACK": back["id"]}
    assert old["id"] not in result.front_image_ref and new["id"] in result.front_image_ref
    assert counts["marqo"] == 3


def test_retake_reuses_unchanged_back_and_rejects_old_confirmation(lifecycle):
    make, _ = lifecycle
    service, counts = make()
    draft_id = ready_pair(service)
    before = service.get(draft_id)
    old_result = service.get_result(draft_id)
    submit(service, draft_id, "FRONT", "retake", data=photo((20, 30, 220)))
    with pytest.raises(DraftConflictError):
        service.confirm(draft_id, expected_revision=before["revision"])
    service.wait_idle(10)
    result = service.get_result(draft_id)
    assert counts["marqo"] == 3
    assert (
        result.back_image_ref == old_result.back_image_ref
        and result.front_image_ref != old_result.front_image_ref
    )


def test_category_and_manual_tags_reuse_vectors_and_confirmation_is_idempotent(lifecycle):
    make, _ = lifecycle
    service, counts = make()
    draft_id = ready_pair(service)
    original = service.get_result(draft_id)
    state = service.get(draft_id)
    service.edit_tags(
        draft_id, {"color": "mavi", "sub_category": "Bluz"}, expected_revision=state["revision"]
    )
    state = service.get(draft_id)
    with pytest.raises(ValidationError):
        service.edit_tags(draft_id, {"sub_category": "Jean"}, expected_revision=state["revision"])
    service.change_category(draft_id, "alt", expected_revision=state["revision"])
    service.wait_idle(10)
    changed = service.get_result(draft_id)
    assert (
        changed.category == "alt"
        and changed.tags.sub_category == "Pantolon"
        and changed.tags.color == "mavi"
    )
    np.testing.assert_array_equal(original.embedding, changed.embedding)
    assert counts["marqo"] == counts["segmentation"] == 2
    revision = service.get(draft_id)["revision"]
    first = service.confirm(draft_id, expected_revision=revision)
    confirmation = service.get(draft_id)["confirmation"]
    assert service.confirm(draft_id, expected_revision=revision) == first
    assert service.get(draft_id)["confirmation"] == confirmation
    with pytest.raises(DraftConflictError):
        submit(service, draft_id, "FRONT", "after-confirm")


def test_late_lr_result_does_not_overwrite_new_category(lifecycle):
    make, block = lifecycle
    service, _ = make()
    draft_id = service.create_draft("üst")["id"]
    entered, release = block(service, "finish_pair")
    submit(service, draft_id, "FRONT", "front")
    submit(service, draft_id, "BACK", "back")
    assert entered.wait(5)
    service.change_category(draft_id, "dış", expected_revision=service.get(draft_id)["revision"])
    release.set()
    service.wait_idle(10)
    assert service.get_result(draft_id).category == "dış"


def test_cancel_and_cleanup_during_inference_never_resurrects_files(lifecycle):
    make, block = lifecycle
    service, _ = make(terminal_retention_seconds=0)
    entered, release = block(service)
    draft_id = service.create_draft("üst")["id"]
    submit(service, draft_id, "FRONT", "front")
    assert entered.wait(5)
    service.cancel(draft_id, expected_revision=service.get(draft_id)["revision"])
    assert service.cleanup() == [draft_id]
    release.set()
    service.wait_idle(10)
    with pytest.raises(DraftNotFoundError):
        service.get(draft_id)
    assert not service.repository.draft_dir(draft_id).exists()
    assert service.health()["worker_errors"] == []


def test_failed_view_can_retry_without_reencoding_ready_other_view(lifecycle):
    make, _ = lifecycle
    service, counts = make()
    draft_id = service.create_draft("üst")["id"]
    submit(service, draft_id, "BACK", "back")
    service.wait_idle(10)
    original = service.analysis.prepare_view

    def fail(*args, **kwargs):
        raise RuntimeError("transient failure")

    service.analysis.prepare_view = fail
    job = submit(service, draft_id, "FRONT", "front")
    service.wait_idle(10)
    assert service.get(draft_id)["jobs"][job["id"]]["status"] == "FAILED"
    service.analysis.prepare_view = original
    service.retry_photo(draft_id, job["id"], expected_revision=service.get(draft_id)["revision"])
    service.wait_idle(10)
    assert service.get(draft_id)["status"] == "REVIEW_READY" and counts["marqo"] == 2
    assert service.get(draft_id)["jobs"][job["id"]]["attempt"] == 2


def test_pair_failure_can_retry_from_persisted_views_without_any_encoder(lifecycle):
    make, _ = lifecycle
    service, counts = make()
    original = service.analysis.finish_pair

    def fail(**kwargs):
        raise RuntimeError("head load failure")

    service.analysis.finish_pair = fail
    draft_id = service.create_draft("üst")["id"]
    submit(service, draft_id, "FRONT", "front")
    submit(service, draft_id, "BACK", "back")
    service.wait_idle(10)
    assert service.get(draft_id)["status"] == "FAILED"
    service.analysis.finish_pair = original
    service.retry_analysis(draft_id, expected_revision=service.get(draft_id)["revision"])
    service.wait_idle(10)
    assert service.get(draft_id)["status"] == "REVIEW_READY" and counts["marqo"] == 2


def test_expiration_and_confirmed_retention(lifecycle):
    make, _ = lifecycle
    now = [1000.0]
    service, _ = make(clock=lambda: now[0], ttl_seconds=5, terminal_retention_seconds=0)
    expired = service.create_draft("üst")["id"]
    kept = ready_pair(service)
    service.confirm(kept, expected_revision=service.get(kept)["revision"])
    now[0] += 6
    assert service.get(expired)["status"] == "EXPIRED"
    assert service.cleanup() == [expired]
    assert service.get(kept)["status"] == "CONFIRMED"


def test_soft_processing_timeout_does_not_publish_view(lifecycle):
    make, _ = lifecycle
    now = [1000.0]
    service, _ = make(clock=lambda: now[0], processing_timeout_seconds=2)
    original = service.analysis.prepare_view

    def slow(*args, **kwargs):
        result = original(*args, **kwargs)
        now[0] += 3
        return result

    service.analysis.prepare_view = slow
    draft_id = service.create_draft("üst")["id"]
    job = submit(service, draft_id, "FRONT", "front")
    service.wait_idle(10)
    assert service.get(draft_id)["jobs"][job["id"]]["error"]["code"] == "PROCESSING_TIMEOUT"
    assert service.get(draft_id)["jobs"][job["id"]]["view_path"] is None


def test_restart_marks_interrupted_job_failed_and_keeps_ready_view(lifecycle, tmp_path):
    make, _ = lifecycle
    root = tmp_path / "restart"
    service, _ = make(root=root)
    draft_id = service.create_draft("üst")["id"]
    back = submit(service, draft_id, "BACK", "back")
    service.wait_idle(10)
    # Persist a crash-time snapshot; never kill a real worker/GPU in tests.
    with service.repository.lock:
        state = service.repository.get(draft_id)
        fake_id = "e" * 32
        state["jobs"][fake_id] = {
            **state["jobs"][back["id"]],
            "id": fake_id,
            "view_type": "FRONT",
            "status": "PROCESSING",
            "view_path": None,
        }
        state["views"]["FRONT"] = fake_id
        state["status"] = "ANALYZING"
        service.repository.save(state)
    service.close()
    restarted, _ = make(root=root)
    recovered = restarted.get(draft_id)
    assert recovered["status"] == "FAILED"
    assert recovered["jobs"][fake_id]["error"]["code"] == "PROCESS_RESTARTED"
    assert recovered["jobs"][back["id"]]["status"] == "READY"


def test_ready_review_survives_restart_without_encoder_work(lifecycle, tmp_path):
    make, _ = lifecycle
    root = tmp_path / "persisted"
    service, _ = make(root=root)
    draft_id = ready_pair(service)
    result = service.get_result(draft_id)
    service.close()
    restarted, counts = make(root=root)
    assert restarted.get_result(draft_id) == result
    restarted.confirm(draft_id, expected_revision=result.draft_revision)
    assert counts["marqo"] == counts["segmentation"] == 0


def test_queued_photo_timeout_does_not_run_encoder(lifecycle):
    make, block = lifecycle
    now = [1000.0]
    service, counts = make(clock=lambda: now[0], queue_timeout_seconds=2)
    entered, release = block(service)
    draft_id = service.create_draft("üst")["id"]
    submit(service, draft_id, "FRONT", "front")
    assert entered.wait(5)
    back = submit(service, draft_id, "BACK", "back")
    now[0] += 3
    release.set()
    service.wait_idle(10)
    assert service.get(draft_id)["jobs"][back["id"]]["error"]["code"] == "QUEUE_TIMEOUT"
    assert counts["marqo"] == 1


def test_attempt_limit_and_stale_user_revision_do_not_mutate_state(lifecycle):
    make, _ = lifecycle
    service, _ = make(max_attempts=1)
    draft_id = service.create_draft("üst")["id"]
    submit(service, draft_id, "FRONT", "bad", data=b"not an image")
    service.wait_idle(10)
    state = service.get(draft_id)
    job_id = state["views"]["FRONT"]
    with pytest.raises(DraftConflictError, match="attempt limit"):
        service.retry_photo(draft_id, job_id, expected_revision=state["revision"])
    with pytest.raises(DraftConflictError, match="revision"):
        service.submit_photo(
            draft_id, view_type="BACK", capture_id="back", image_bytes=photo(), expected_revision=1
        )
    assert service.get(draft_id) == state


def test_duplicate_category_and_tag_edits_do_not_bump_revision_or_queue_work(lifecycle):
    make, _ = lifecycle
    service, counts = make()
    draft_id = ready_pair(service)
    before = service.get(draft_id)["revision"]
    edited = service.edit_tags(draft_id, {"color": "mavi"}, expected_revision=before)
    assert service.edit_tags(draft_id, {"color": "mavi"}, expected_revision=before) == edited
    before = edited["revision"]
    service.change_category(draft_id, "alt", expected_revision=before)
    service.wait_idle(10)
    current = service.get(draft_id)
    assert service.change_category(draft_id, "alt", expected_revision=before) == current
    assert service.health()["pending_jobs"] == 0 and counts["marqo"] == 2


def test_restart_between_ready_views_and_pair_analysis_is_retryable(lifecycle, tmp_path):
    make, _ = lifecycle
    root = tmp_path / "unpublished-pair"
    service, _ = make(root=root)
    draft_id = ready_pair(service)
    with service.repository.lock:
        state = service.repository.get(draft_id)
        state.update(status="WAITING_VIEWS", result_path=None, result_revision=None)
        service.repository.save(state)
    service.close()
    restarted, counts = make(root=root)
    assert restarted.get(draft_id)["status"] == "FAILED"
    restarted.retry_analysis(draft_id, expected_revision=restarted.get(draft_id)["revision"])
    restarted.wait_idle(10)
    assert restarted.get(draft_id)["status"] == "REVIEW_READY"
    assert counts["marqo"] == 0
