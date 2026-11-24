"""Revision, image integrity and embedding checks over the actual HTTP adapter."""

import hashlib
import io
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from gardirop_ai_clothing.api_jobs import HttpJobs
from gardirop_ai_clothing.api_results import get_image
from gardirop_ai_clothing.app import create_app
from gardirop_ai_clothing.config import Settings
from gardirop_ai_clothing.jobs import DraftService
from gardirop_ai_clothing.schemas import ViewType
from gardirop_ai_clothing.storage import LocalDraftRepository


def photo(color="red"):
    stream = io.BytesIO()
    Image.new("RGB", (40, 60), color).save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture
def download_case(tmp_path, analysis_factory):
    analysis, counts = analysis_factory()
    now = [1000.0]
    service = DraftService(
        LocalDraftRepository(tmp_path / "store"),
        analysis,
        clock=lambda: now[0],
        terminal_retention_seconds=0,
    )
    settings = Settings(api_draft_root=tmp_path / "store")
    app = create_app(
        processing_enabled=True,
        service_factory=lambda _: service,
        settings=settings,
        api_key="unit-test-only-service-key-000000000000",
    )
    with TestClient(
        app, headers={"X-API-Key": "unit-test-only-service-key-000000000000"}
    ) as client:
        yield client, service, counts, now


def ready(case, *, front_only=False):
    client, service, _, _ = case
    created = client.post(
        "/v1/clothing/jobs",
        headers={"Idempotency-Key": "download-case"},
        data={"category": "UST_GIYIM", "captureId": "front"},
        files={"image": ("front.png", photo(), "image/png")},
    )
    assert created.status_code == 202, created.text
    job_id = created.json()["jobId"]
    if not front_only:
        response = client.put(
            f"/v1/clothing/jobs/{job_id}/views/BACK",
            data={"captureId": "back", "expectedRevision": "2"},
            files={"image": ("back.png", photo("blue"), "image/png")},
        )
        assert response.status_code == 202, response.text
    service.wait_idle(10)
    state = client.get(f"/v1/clothing/jobs/{job_id}").json()
    return job_id, state["revision"]


def paths(job_id, revision):
    base = f"/v1/clothing/jobs/{job_id}/results/{revision}"
    return (base, f"{base}/embedding", f"{base}/images/FRONT", f"{base}/images/BACK")


def test_ready_status_points_to_revision_bound_result(download_case):
    client, _, _, _ = download_case
    job_id, revision = ready(download_case)
    response = client.get(f"/v1/clothing/jobs/{job_id}")
    assert response.json()["resultUrl"] == paths(job_id, revision)[0]


def test_result_contains_tags_sources_versions_and_download_descriptors(download_case):
    client, service, _, _ = download_case
    job_id, revision = ready(download_case)
    response = client.get(paths(job_id, revision)[0])
    assert response.status_code == 200, response.text
    result = response.json()
    native = service.get_result(job_id)
    assert result["jobId"] == job_id and result["revision"] == revision
    assert result["category"] == "UST_GIYIM"
    assert result["tags"] == {
        "subCategory": "Gömlek",
        "color": None,
        "season": None,
        "hasPrint": None,
    }
    assert result["versions"]["taxonomyVersion"] == "clothing20-v1"
    assert (
        result["versions"]["classifierArtifactSha256"] == native.versions.classifier_artifact_sha256
    )
    assert result["versions"]["embeddingRevision"] == native.versions.embedding_revision
    assert result["versions"]["fusionMethod"] == native.versions.fusion_method
    assert (
        result["modelDiagnostics"]["classification"]["score_kind"]
        == "linear_margin_not_probability"
    )
    assert result["modelDiagnostics"]["attributes"]["status"] == "not_configured"
    assert result["embedding"]["dimension"] == 1536
    assert result["embedding"]["viewOrder"] == ["FRONT", "BACK"]
    assert "values" not in result["embedding"] and set(result["images"]) == {"FRONT", "BACK"}
    assert "front_image_ref" not in response.text and "input.bin" not in response.text
    assert "/home/" not in response.text and "drafts/" not in response.text
    assert "userRating" not in result["tags"]


@pytest.mark.parametrize("view", ["FRONT", "BACK"])
def test_image_is_rgb_white_webp_and_matches_reported_digest(download_case, view):
    client, _, _, _ = download_case
    job_id, revision = ready(download_case)
    result = client.get(paths(job_id, revision)[0]).json()
    description = result["images"][view]
    response = client.get(description["url"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["x-result-revision"] == str(revision)
    assert response.headers["cache-control"] == "no-store"
    digest = hashlib.sha256(response.content).hexdigest()
    assert digest == description["sha256"]
    assert response.headers["etag"] == f'"{digest}"'
    assert len(response.content) == description["byteLength"]
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.format == "WEBP" and image.mode == "RGB"
        assert list(image.size) == [description["width"], description["height"]]
        assert (
            image.getpixel((0, 0))
            == image.getpixel((image.width - 1, image.height - 1))
            == (255, 255, 255)
        )
    assert description["lossless"] is True and description["background"] == "#FFFFFF"


def test_embedding_preserves_front_back_values_and_unit_norm(download_case):
    client, service, _, _ = download_case
    job_id, revision = ready(download_case)
    response = client.get(paths(job_id, revision)[1])
    assert response.status_code == 200, response.text
    data = response.json()
    vector = np.asarray(data["values"], dtype=np.float32)
    assert data["dimension"] == vector.size == 1536 and data["dtype"] == "float32"
    assert data["viewOrder"] == ["FRONT", "BACK"]
    assert data["jobId"] == job_id and data["revision"] == revision
    assert abs(data["norm"] - 1) < 1e-3
    assert abs(np.linalg.norm(vector[:768]) - 1 / np.sqrt(2)) < 1e-3
    assert abs(np.linalg.norm(vector[768:]) - 1 / np.sqrt(2)) < 1e-3
    np.testing.assert_array_equal(
        vector, np.asarray(service.get_result(job_id).embedding, dtype=np.float32)
    )


def test_repeated_downloads_never_recompute_or_extend_expiration(download_case):
    client, service, counts, _ = download_case
    job_id, revision = ready(download_case)
    before_counts, expires = dict(counts), service.get(job_id)["expires_at"]
    for _ in range(2):
        for path in paths(job_id, revision):
            assert client.get(path).status_code == 200
    assert counts == before_counts and counts["marqo"] == counts["segmentation"] == 2
    assert service.get(job_id)["expires_at"] == expires


def test_unfinished_job_has_no_downloadable_result(download_case):
    client, _, _, _ = download_case
    job_id, revision = ready(download_case, front_only=True)
    state = client.get(f"/v1/clothing/jobs/{job_id}").json()
    assert state["resultUrl"] is None
    for path in paths(job_id, revision):
        response = client.get(path)
        assert (
            response.status_code == 409 and response.json()["error"]["code"] == "RESULT_NOT_CURRENT"
        )


def test_retake_invalidates_old_download_urls_and_preserves_other_view(download_case):
    client, service, counts, _ = download_case
    job_id, revision = ready(download_case)
    old_result = service.get_result(job_id)
    replaced = client.put(
        f"/v1/clothing/jobs/{job_id}/views/FRONT",
        data={"captureId": "retake", "expectedRevision": str(revision)},
        files={"image": ("retake.png", photo("green"), "image/png")},
    )
    assert replaced.status_code == 202
    service.wait_idle(10)
    for path in paths(job_id, revision):
        assert client.get(path).status_code == 409
    for path in paths(job_id, revision + 1):
        assert client.get(path).status_code == 200
    assert counts["marqo"] == 3
    assert service.get_result(job_id).back_image_ref == old_result.back_image_ref


@pytest.mark.parametrize("suffix", ["", "/embedding", "/images/FRONT"])
def test_unknown_job_is_404(download_case, suffix):
    client, _, _, _ = download_case
    assert client.get(f"/v1/clothing/jobs/unknown/results/3{suffix}").status_code == 404


@pytest.mark.parametrize("closed", ["expired", "cancelled"])
def test_expired_or_cancelled_results_cannot_be_downloaded(download_case, closed):
    client, service, _, now = download_case
    job_id, revision = ready(download_case)
    if closed == "expired":
        now[0] += service.ttl + 1
        expected = 410
    else:
        service.cancel(job_id, expected_revision=revision)
        expected = 409
    for path in paths(job_id, revision):
        assert client.get(path).status_code == expected


def test_corrupted_image_is_not_delivered(download_case):
    client, service, _, _ = download_case
    job_id, revision = ready(download_case)
    native = service.get_result(job_id)
    service.repository.path(native.front_image_ref).write_bytes(b"corrupt")
    for path in (paths(job_id, revision)[0], paths(job_id, revision)[2]):
        response = client.get(path)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert "clean.webp" not in response.text


def test_invalid_stored_embedding_is_not_delivered_as_a_valid_result(download_case):
    client, service, _, _ = download_case
    job_id, revision = ready(download_case)
    state = service.get(job_id)
    target = service.repository.path(state["result_path"])
    stored = json.loads(target.read_text())
    stored["embedding"] = [0.0] * 1536
    target.write_text(json.dumps(stored))
    response = client.get(paths(job_id, revision)[1])
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


def test_image_response_bytes_survive_cleanup_before_asgi_sends_them(download_case):
    _, service, _, _ = download_case
    job_id, revision = ready(download_case)
    response = get_image(job_id, revision, ViewType.FRONT, HttpJobs(service))
    service.cancel(job_id, expected_revision=revision)
    assert service.cleanup() == [job_id]
    with Image.open(io.BytesIO(response.body)) as image:
        assert image.mode == "RGB"


def test_invalid_revision_and_view_are_rejected(download_case):
    client, _, _, _ = download_case
    job_id, _ = ready(download_case)
    assert client.get(f"/v1/clothing/jobs/{job_id}/results/0").status_code == 422
    assert client.get(f"/v1/clothing/jobs/{job_id}/results/3/images/SIDE").status_code == 422


def test_openapi_documents_binary_images(download_case):
    client, _, _, _ = download_case
    schema = client.get("/openapi.json").json()
    route = schema["paths"]["/v1/clothing/jobs/{job_id}/results/{revision}/images/{view}"]["get"]
    assert "image/webp" in route["responses"]["200"]["content"]
