"""Exercise edits, bounded retries and cancellation on the real queued core."""

import io
from threading import Event

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from gardirop_ai_clothing.api_jobs import analysis_attempt_count
from gardirop_ai_clothing.app import create_app
from gardirop_ai_clothing.config import Settings
from gardirop_ai_clothing.errors import InferenceError
from gardirop_ai_clothing.jobs import DraftService
from gardirop_ai_clothing.storage import LocalDraftRepository

KEY = "unit-test-only-service-key-000000000000"


def photo():
    stream = io.BytesIO()
    Image.new("RGB", (40, 60), "red").save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture
def control_case(tmp_path, analysis_factory):
    analysis, counts = analysis_factory()
    modes = {"photo_failures": 0, "analysis_failures": 0, "block": False}
    entered, release = Event(), Event()
    prepare, finish = analysis.prepare_view, analysis.finish_pair

    def prepare_view(*args, **kwargs):
        if modes["block"]:
            entered.set()
            assert release.wait(10)
        if modes["photo_failures"]:
            modes["photo_failures"] -= 1
            raise InferenceError("Synthetic temporary photo failure.")
        return prepare(*args, **kwargs)

    def finish_pair(*args, **kwargs):
        if modes["analysis_failures"]:
            modes["analysis_failures"] -= 1
            raise InferenceError("Synthetic temporary analysis failure.")
        return finish(*args, **kwargs)

    analysis.prepare_view, analysis.finish_pair = prepare_view, finish_pair
    now = [1000.0]
    service = DraftService(
        LocalDraftRepository(tmp_path / "store"), analysis, max_pending_jobs=1, clock=lambda: now[0]
    )
    settings = Settings(api_draft_root=tmp_path / "store")
    app = create_app(
        processing_enabled=True, api_key=KEY, settings=settings, service_factory=lambda _: service
    )
    with TestClient(app, headers={"X-API-Key": KEY}) as client:
        try:
            yield client, service, counts, modes, entered, release, now
        finally:
            release.set()


def create(case, key="first"):
    client, service, *_ = case
    response = client.post(
        "/v1/clothing/jobs",
        headers={"Idempotency-Key": key},
        data={"category": "UST_GIYIM", "captureId": "front"},
        files={"image": ("front.png", photo(), "image/png")},
    )
    assert response.status_code == 202, response.text
    return response.json()["jobId"]


def pair(case):
    client, service, *_ = case
    job_id = create(case)
    service.wait_idle(10)
    response = client.put(
        f"/v1/clothing/jobs/{job_id}/views/BACK",
        data={"captureId": "back", "expectedRevision": "2"},
        files={"image": ("back.png", photo(), "image/png")},
    )
    assert response.status_code == 202, response.text
    service.wait_idle(10)
    return job_id


def retry(case, job_id, stage, revision=None):
    client, service, *_ = case
    revision = service.get(job_id)["revision"] if revision is None else revision
    return client.post(
        f"/v1/clothing/jobs/{job_id}/retry", json={"stage": stage, "expectedRevision": revision}
    )


def test_category_change_reuses_embeddings_and_invalidates_old_result(control_case):
    client, service, counts, *_ = control_case
    job_id = pair(control_case)
    previous = service.get_result(job_id)
    request = {"category": "ALT_GIYIM", "expectedRevision": 3}
    changed = client.patch(f"/v1/clothing/jobs/{job_id}/category", json=request)
    assert changed.status_code == 200 and changed.json()["revision"] == 4
    replay = client.patch(f"/v1/clothing/jobs/{job_id}/category", json=request)
    assert replay.status_code == 200 and replay.json()["revision"] == 4
    service.wait_idle(10)
    result = service.get_result(job_id)
    assert result.tags.sub_category == "Pantolon" and result.embedding == previous.embedding
    assert counts["segmentation"] == counts["marqo"] == 2
    assert client.get(f"/v1/clothing/jobs/{job_id}/results/3").status_code == 409
    assert client.get(f"/v1/clothing/jobs/{job_id}/results/4").status_code == 200
    stale = client.patch(
        f"/v1/clothing/jobs/{job_id}/category",
        json={"category": "DIS_GIYIM", "expectedRevision": 3},
    )
    assert stale.status_code == 409


def test_failed_photo_retry_is_bounded_and_duplicate_revision_does_not_resubmit(control_case):
    client, service, counts, modes, *_ = control_case
    modes["photo_failures"] = 3
    job_id = create(control_case)
    service.wait_idle(10)
    for revision in (2, 3):
        response = retry(control_case, job_id, "FRONT", revision)
        assert response.status_code == 202, response.text
        assert retry(control_case, job_id, "FRONT", revision).status_code == 409
        service.wait_idle(10)
    state = client.get(f"/v1/clothing/jobs/{job_id}").json()
    assert state["views"]["FRONT"]["attempt"] == 3 and state["error"]["retryable"] is False
    assert retry(control_case, job_id, "FRONT").status_code == 409
    assert counts["marqo"] == 0


def test_recovered_photo_uses_ready_opposite_view_without_reencoding(control_case):
    _, service, counts, modes, *_ = control_case
    modes["photo_failures"] = 1
    job_id = pair(control_case)
    assert service.get(job_id)["status"] == "FAILED" and counts["marqo"] == 1
    assert retry(control_case, job_id, "FRONT").status_code == 202
    service.wait_idle(10)
    assert service.get(job_id)["status"] == "REVIEW_READY" and counts["marqo"] == 2


def test_analysis_retry_reuses_both_views_and_stops_after_three_attempts(control_case):
    client, service, counts, modes, *_ = control_case
    modes["analysis_failures"] = 3
    job_id = pair(control_case)
    for revision in (3, 4):
        assert retry(control_case, job_id, "ANALYSIS", revision).status_code == 202
        assert retry(control_case, job_id, "ANALYSIS", revision).status_code == 409
        service.wait_idle(10)
    assert analysis_attempt_count(service.get(job_id)) == 3
    state = client.get(f"/v1/clothing/jobs/{job_id}").json()
    assert state["error"]["retryable"] is False
    assert retry(control_case, job_id, "ANALYSIS").status_code == 409
    assert counts["segmentation"] == counts["marqo"] == 2


def test_analysis_recovery_never_repeats_vision_inference(control_case):
    _, service, counts, modes, *_ = control_case
    modes["analysis_failures"] = 1
    job_id = pair(control_case)
    assert retry(control_case, job_id, "ANALYSIS").status_code == 202
    service.wait_idle(10)
    assert service.get(job_id)["status"] == "REVIEW_READY"
    assert counts["marqo"] == 2


def test_full_queue_does_not_consume_analysis_attempt(control_case):
    _, service, _, modes, entered, release, _ = control_case
    modes["analysis_failures"] = 1
    job_id = pair(control_case)
    modes["block"] = True
    create(control_case, key="blocker")
    assert entered.wait(5)
    response = retry(control_case, job_id, "ANALYSIS")
    assert response.status_code == 429 and response.headers["retry-after"] == "1"
    assert analysis_attempt_count(service.get(job_id)) == 1
    release.set()
    service.wait_idle(10)
    assert retry(control_case, job_id, "ANALYSIS").status_code == 202
    service.wait_idle(10)
    assert analysis_attempt_count(service.get(job_id)) == 2


def test_cancel_during_inference_is_idempotent_and_late_results_are_discarded(control_case):
    client, service, _, modes, entered, release, _ = control_case
    modes["block"] = True
    job_id = create(control_case)
    assert entered.wait(5)
    url = f"/v1/clothing/jobs/{job_id}"
    assert client.delete(url, params={"expectedRevision": 1}).status_code == 409
    response = client.delete(url, params={"expectedRevision": 2})
    assert response.status_code == 204 and response.content == b""
    assert client.delete(url, params={"expectedRevision": 2}).status_code == 204
    state = client.get(url).json()
    assert state["status"] == "CANCELLED" and state["revision"] == 3
    release.set()
    service.wait_idle(10)
    assert client.get(url).json()["status"] == "CANCELLED"
    assert retry(control_case, job_id, "FRONT").status_code == 409
    assert service.health()["worker_errors"] == []


@pytest.mark.parametrize(
    "body",
    [
        {"stage": "FRONT", "expectedRevision": True},
        {"stage": "FRONT", "expectedRevision": "2"},
        {"stage": "SIDE", "expectedRevision": 2},
    ],
)
def test_retry_rejects_invalid_body(control_case, body):
    client, *_ = control_case
    job_id = create(control_case)
    assert client.post(f"/v1/clothing/jobs/{job_id}/retry", json=body).status_code == 422


def test_ready_and_missing_stages_are_not_retried(control_case):
    _, service, *_ = control_case
    job_id = create(control_case)
    service.wait_idle(10)
    assert retry(control_case, job_id, "FRONT").status_code == 409
    assert retry(control_case, job_id, "BACK").status_code == 409
    assert retry(control_case, job_id, "ANALYSIS").status_code == 409


def test_expired_controls_return_410(control_case):
    client, service, _, _, _, _, now = control_case
    job_id = pair(control_case)
    now[0] += service.ttl + 1
    base = f"/v1/clothing/jobs/{job_id}"
    assert client.delete(base, params={"expectedRevision": 3}).status_code == 410
    assert (
        client.patch(
            base + "/category", json={"category": "ALT_GIYIM", "expectedRevision": 3}
        ).status_code
        == 410
    )
    assert retry(control_case, job_id, "ANALYSIS").status_code == 410


@pytest.mark.parametrize(
    "method,suffix", [("patch", "/category"), ("post", "/retry"), ("delete", "")]
)
def test_controls_require_key_before_body_parsing(control_case, method, suffix):
    client, *_ = control_case
    response = client.request(
        method, "/v1/clothing/jobs/missing" + suffix, headers={"X-API-Key": "wrong"}
    )
    assert response.status_code == 401
