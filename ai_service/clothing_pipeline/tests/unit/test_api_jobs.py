"""Exercise the actual queue and HTTP adapter with synthetic neural runners."""

import io
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from gardirop_ai_clothing.app import create_app
from gardirop_ai_clothing.config import Settings
from gardirop_ai_clothing.jobs import DraftService
from gardirop_ai_clothing.storage import LocalDraftRepository


def image_bytes(color="red", fmt="PNG"):
    output = io.BytesIO()
    Image.new("RGB", (40, 60), color).save(output, format=fmt)
    return output.getvalue()


@pytest.fixture
def api_factory(tmp_path, analysis_factory):
    releases = []
    clients = []

    def make(
        *,
        root=None,
        blocked=False,
        capacity=8,
        fail_photo=False,
        upload_limit=20 * 1024 * 1024,
        clock=None,
    ):
        root = root or tmp_path / str(len(clients))
        settings = Settings(api_draft_root=root, draft_root=tmp_path / "demo_untouched")
        analysis, counts = analysis_factory(max_upload_bytes=upload_limit)
        entered, release = Event(), Event()
        if blocked:
            releases.append(release)
            original = analysis.prepare_view

            def prepare(*args, **kwargs):
                entered.set()
                assert release.wait(10)
                return original(*args, **kwargs)

            analysis.prepare_view = prepare
        if fail_photo:

            def fail(*args, **kwargs):
                raise RuntimeError("private path /home/enes/secret/model.bin")

            analysis.prepare_view = fail
        services = []

        def factory(configured):
            assert configured.draft_root == root
            assert configured.draft_root != settings.draft_root
            kwargs = {"clock": clock} if clock else {}
            service = DraftService(
                LocalDraftRepository(configured.draft_root),
                analysis,
                max_pending_jobs=capacity,
                **kwargs,
            )
            services.append(service)
            return service

        app = create_app(
            processing_enabled=True,
            service_factory=factory,
            settings=settings,
            api_key="unit-test-only-service-key-000000000000",
        )
        client = TestClient(app, headers={"X-API-Key": "unit-test-only-service-key-000000000000"})
        client.__enter__()
        clients.append(client)
        return client, services[0], counts, entered, release

    yield make
    for release in releases:
        release.set()
    for client in reversed(clients):
        client.__exit__(None, None, None)


def create(
    client, *, key="create-1", capture="front-1", data=None, category="UST_GIYIM", rotation=0
):
    return client.post(
        "/v1/clothing/jobs",
        headers={"Idempotency-Key": key},
        data={"category": category, "captureId": capture, "manualRotation": str(rotation)},
        files={"image": ("front.png", image_bytes() if data is None else data, "image/png")},
    )


def put(client, job_id, revision, *, view="BACK", capture="back-1", data=None):
    return client.put(
        f"/v1/clothing/jobs/{job_id}/views/{view}",
        data={"captureId": capture, "expectedRevision": str(revision)},
        files={"image": ("view.png", image_bytes("blue") if data is None else data, "image/png")},
    )


def test_front_begins_before_back_and_polling_does_not_change_revision(api_factory):
    client, service, counts, entered, release = api_factory(blocked=True)
    response = create(client)
    assert response.status_code == 202, response.text
    created = response.json()
    assert entered.wait(5)
    assert created["revision"] == 2 and set(created["views"]) == {"FRONT"}
    location = response.headers["location"]
    snapshot = client.get(location).json()
    assert snapshot["status"] == "PROCESSING"
    assert snapshot["revision"] == client.get(location).json()["revision"] == 2
    assert snapshot["resultRevision"] is None
    assert snapshot["category"] == "UST_GIYIM"
    assert "expiresAt" in snapshot
    assert "input.bin" not in response.text and "signature" not in response.text
    release.set()
    service.wait_idle(10)
    assert counts["segmentation"] == counts["marqo"] == 1
    assert client.get(location).json()["status"] == "WAITING_VIEWS"


def test_two_view_job_reaches_ready_and_produces_real_core_embedding(api_factory):
    client, service, counts, _, _ = api_factory()
    first = create(client).json()
    response = put(client, first["jobId"], first["revision"])
    assert response.status_code == 202, response.text
    service.wait_idle(10)
    final = client.get(f"/v1/clothing/jobs/{first['jobId']}").json()
    assert final["status"] == "READY" and final["resultRevision"] == final["revision"] == 3
    assert final["views"]["FRONT"]["status"] == final["views"]["BACK"]["status"] == "READY"
    assert len(service.get_result(first["jobId"]).embedding) == 1536
    assert counts["marqo"] == counts["segmentation"] == 2
    assert "embedding" not in final and "result_path" not in final


def test_duplicate_creation_and_capture_do_not_repeat_inference(api_factory):
    client, service, counts, _, _ = api_factory()
    first = create(client).json()
    duplicate = create(client)
    assert duplicate.status_code == 200
    assert duplicate.json()["jobId"] == first["jobId"]
    assert duplicate.json()["acceptedPhotoTaskId"] == first["acceptedPhotoTaskId"]
    assert duplicate.json()["replayed"] is True
    back = put(client, first["jobId"], 2)
    assert back.status_code == 202
    repeated = put(client, first["jobId"], 2)
    assert repeated.status_code == 200 and repeated.json()["revision"] == 3
    service.wait_idle(10)
    assert counts["marqo"] == 2


def test_duplicate_concurrent_creation_is_one_task(api_factory):
    client, service, counts, _, _ = api_factory()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: create(client), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 202]
    assert len({response.json()["jobId"] for response in responses}) == 1
    service.wait_idle(10)
    assert counts["marqo"] == 1


def test_idempotency_record_survives_worker_restart(api_factory, tmp_path):
    root = tmp_path / "restart"
    first_client, service, _, _, _ = api_factory(root=root)
    created = create(first_client).json()
    service.wait_idle(10)
    service.close()
    second_client, second, counts, _, _ = api_factory(root=root)
    replay = create(second_client)
    assert replay.status_code == 200 and replay.json()["jobId"] == created["jobId"]
    second.wait_idle(10)
    assert counts["marqo"] == counts["segmentation"] == 0


def test_reused_create_key_with_different_input_is_conflict(api_factory):
    client, _, _, _, _ = api_factory()
    create(client)
    response = create(client, data=image_bytes("green"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "JOB_CONFLICT"


def test_stale_revision_and_conflicting_capture_are_rejected(api_factory):
    client, _, _, _, _ = api_factory()
    first = create(client).json()
    assert put(client, first["jobId"], 1).status_code == 409
    assert put(client, first["jobId"], 2, view="FRONT", capture="front-1").status_code == 409


def test_queue_full_returns_429_without_creating_an_orphan(api_factory):
    client, service, _, entered, _ = api_factory(blocked=True, capacity=1)
    create(client)
    assert entered.wait(5)
    response = create(client, key="different", capture="other")
    assert response.status_code == 429 and response.headers["retry-after"] == "1"
    assert len(service.repository.ids()) == 1


@pytest.mark.parametrize(
    ("data", "status"), [(b"", 422), (b"not an image", 422), (image_bytes(fmt="GIF"), 415)]
)
def test_invalid_images_do_not_create_jobs(api_factory, data, status):
    client, service, counts, _, _ = api_factory()
    response = create(client, data=data)
    assert response.status_code == status
    assert service.repository.ids() == [] and counts["marqo"] == 0


def test_image_byte_limit_is_checked_before_queueing(api_factory):
    client, service, _, _, _ = api_factory(upload_limit=1024)
    assert create(client, data=b"x" * 1025).status_code == 413
    assert service.repository.ids() == []


@pytest.mark.parametrize("category", ["AYAKKABI", "AKSESUAR", "üst"])
def test_invalid_main_category_is_422_and_never_creates_jobs(api_factory, category):
    client, service, _, _, _ = api_factory()
    assert create(client, category=category).status_code == 422
    assert service.repository.ids() == []


@pytest.mark.parametrize("rotation", [-180, 45, 360])
def test_unsupported_rotation_is_422(api_factory, rotation):
    client, service, _, _, _ = api_factory()
    assert create(client, rotation=rotation).status_code == 422
    assert service.repository.ids() == []


def test_manual_rotation_reaches_the_native_photo_options(api_factory):
    client, service, _, _, _ = api_factory()
    data = create(client, rotation=90).json()
    state = service.get(data["jobId"])
    assert state["jobs"][data["acceptedPhotoTaskId"]]["options"]["manual_rotation"] == 90


def test_missing_and_unknown_job_return_structured_422_and_404(api_factory):
    client, _, _, _, _ = api_factory()
    assert client.post("/v1/clothing/jobs").status_code == 422
    response = client.get("/v1/clothing/jobs/not-a-job")
    assert response.status_code == 404 and response.json()["error"]["code"] == "JOB_NOT_FOUND"


def test_async_failure_does_not_leak_internal_paths(api_factory):
    client, service, _, _, _ = api_factory(fail_photo=True)
    first = create(client).json()
    service.wait_idle(10)
    response = client.get(f"/v1/clothing/jobs/{first['jobId']}")
    assert response.status_code == 200 and response.json()["status"] == "FAILED"
    assert response.json()["error"]["stage"] == "FRONT"
    assert "/home/enes" not in response.text and "model.bin" not in response.text


def test_expired_job_returns_410_and_replay_does_not_restart_it(api_factory):
    now = [1000.0]
    client, service, counts, _, _ = api_factory(clock=lambda: now[0])
    first = create(client).json()
    service.wait_idle(10)
    now[0] += service.ttl + 1
    response = client.get(f"/v1/clothing/jobs/{first['jobId']}")
    assert response.status_code == 410
    assert create(client).status_code == 410 and counts["marqo"] == 1


def test_photo_retake_reuses_the_other_view(api_factory):
    client, service, counts, _, _ = api_factory()
    first = create(client).json()
    put(client, first["jobId"], 2)
    service.wait_idle(10)
    response = put(
        client, first["jobId"], 3, view="FRONT", capture="front-retake", data=image_bytes("green")
    )
    assert response.status_code == 202
    service.wait_idle(10)
    assert counts["marqo"] == counts["segmentation"] == 3
    final = client.get(f"/v1/clothing/jobs/{first['jobId']}").json()
    assert final["status"] == "READY" and final["revision"] == 4


def test_service_connection_is_reported_without_a_neural_forward(api_factory):
    client, _, counts, _, _ = api_factory()
    assert client.get("/health/live").json()["photoProcessingAvailable"] is True
    assert counts["seg_load"] == counts["marqo_load"] == counts["marqo"] == 0


def test_contract_only_app_refuses_photo_work():
    with TestClient(create_app()) as client:
        assert create(client).status_code == 503
