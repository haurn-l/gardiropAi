"""Startup readiness uses warmed models; unit tests use synthetic runners only."""

import pytest
from fastapi.testclient import TestClient

from gardirop_ai_clothing.app import create_app
from gardirop_ai_clothing.config import Settings
from gardirop_ai_clothing.jobs import DraftService
from gardirop_ai_clothing.runtime_preparation import prepare_runtime
from gardirop_ai_clothing.storage import LocalDraftRepository

KEY = "unit-test-only-service-key-000000000000"


def test_model_free_contract_never_claims_ready():
    with TestClient(create_app()) as client:
        assert client.get("/health/live").status_code == 200
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "NOT_READY"
        assert response.json()["modelsWarmed"] is False
        assert response.headers["cache-control"] == "no-store"


def test_startup_warmup_is_idempotent_and_does_not_create_photo_jobs(tmp_path, analysis_factory):
    analysis, calls = analysis_factory()
    service = DraftService(LocalDraftRepository(tmp_path / "store"), analysis)
    settings = Settings()
    try:
        first = prepare_runtime(service, settings)
        before = calls.copy()
        assert prepare_runtime(service, settings) == first
        assert calls == before
        assert first["status"] == "READY" and first["device"] == "cpu"
        assert calls["seg_load"] == calls["marqo_load"] == calls["head_load"] == 1
        assert calls["segmentation"] == calls["marqo"] == 1
        assert not service.repository.ids()
    finally:
        service.close()


def test_http_publishes_ready_only_after_explicit_preparer(tmp_path, analysis_factory):
    analysis, _ = analysis_factory()
    services = []
    settings = Settings(api_draft_root=tmp_path / "api", draft_root=tmp_path / "demo")

    def factory(configured):
        assert configured.draft_storage_profile == "compact"
        service = DraftService(LocalDraftRepository(configured.draft_root, compact=True), analysis)
        services.append(service)
        return service

    app = create_app(
        processing_enabled=True,
        api_key=KEY,
        settings=settings,
        service_factory=factory,
        runtime_preparer=prepare_runtime,
    )
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["modelsWarmed"] is True
        assert len(response.json()["loadedModels"]) == 3
        assert client.get("/health/live").json()["photoProcessingAvailable"] is True
    assert not services[0].health()["worker_alive"]
    assert not (tmp_path / "demo").exists()


def test_failed_preparation_closes_worker_and_releases_store_owner(tmp_path, analysis_factory):
    analysis, _ = analysis_factory()
    services = []
    root = tmp_path / "api"

    def factory(configured):
        service = DraftService(LocalDraftRepository(configured.draft_root), analysis)
        services.append(service)
        return service

    def fail(service, configured):
        raise RuntimeError("synthetic warmup failure")

    app = create_app(
        processing_enabled=True,
        api_key=KEY,
        settings=Settings(api_draft_root=root),
        service_factory=factory,
        runtime_preparer=fail,
    )
    with pytest.raises(RuntimeError, match="warmup failure"), TestClient(app):
        pass
    assert not services[0].health()["worker_alive"]
    repo = LocalDraftRepository(root)
    repo.close()


def test_explicit_lazy_mode_is_not_reported_as_warmed(tmp_path, analysis_factory):
    analysis, _ = analysis_factory()

    def factory(configured):
        return DraftService(LocalDraftRepository(configured.draft_root), analysis)

    def forbidden(*args):
        raise AssertionError("Lazy control must not warm models.")

    app = create_app(
        processing_enabled=True,
        api_key=KEY,
        settings=Settings(api_draft_root=tmp_path / "api", api_preload_models=False),
        service_factory=factory,
        runtime_preparer=forbidden,
    )
    with TestClient(app) as client:
        assert client.get("/health/ready").status_code == 503
        assert client.get("/health/live").json()["photoProcessingAvailable"] is True
