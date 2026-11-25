"""Local HTTP service. The lifespan owns exactly one clothing worker."""

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from gardirop_ai_clothing.api_auth import (
    ApiKeyMiddleware,
    load_api_key,
    require_api_key,
    validate_key,
)
from gardirop_ai_clothing.api_contracts import (
    HealthResponse,
    ReadinessResponse,
    TaxonomyResponse,
    build_taxonomy,
)
from gardirop_ai_clothing.api_controls import router as controls_router
from gardirop_ai_clothing.api_jobs import HttpJobs, router
from gardirop_ai_clothing.api_results import router as results_router
from gardirop_ai_clothing.config import Settings, get_settings
from gardirop_ai_clothing.errors import (
    ClothingPipelineError,
    DraftConflictError,
    DraftNotFoundError,
    JobQueueFullError,
)

logger = logging.getLogger(__name__)


def create_app(
    *,
    processing_enabled: bool = False,
    api_key: str | None = None,
    service_factory: Callable | None = None,
    settings: Settings | None = None,
    runtime_preparer: Callable | None = None,
) -> FastAPI:
    """The default is a model-free contract probe; uvicorn's app enables processing.

    A factory can inject the real core with synthetic runners into HTTP tests.
    The Gradio repository is never opened by this app.
    """

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        service = None
        application.state.http_jobs = None
        application.state.api_secret = validate_key(api_key) if api_key is not None else None
        try:
            if processing_enabled:
                from gardirop_ai_clothing.jobs import create_draft_service

                configured = settings or get_settings()
                if application.state.api_secret is None:
                    application.state.api_secret = load_api_key(configured)
                api_settings = configured.model_copy(
                    update={
                        "draft_root": configured.api_draft_root,
                        "draft_storage_profile": "compact"
                        if configured.api_compact_storage
                        else "full",
                    }
                )
                factory = service_factory or create_draft_service
                service = await run_in_threadpool(factory, api_settings)
                if configured.api_preload_models and (
                    service_factory is None or runtime_preparer is not None
                ):
                    from gardirop_ai_clothing.runtime_preparation import prepare_runtime

                    logger.warning("Preparing clothing models and warmup before HTTP startup...")
                    report = await run_in_threadpool(
                        runtime_preparer or prepare_runtime, service, api_settings
                    )
                    logger.warning("Clothing runtime prepared: %s", report)
                application.state.http_jobs = HttpJobs(service)
            yield
        finally:
            application.state.http_jobs = None
            application.state.api_secret = None
            if service is not None:
                await run_in_threadpool(service.close)

    application = FastAPI(
        title="GardropAI Clothing AI",
        version="0.4.0",
        lifespan=lifespan,
        description=(
            "Local photo jobs: upload FRONT, then BACK, and poll status. "
            "Production startup loads and warms neural models before accepting requests. "
            "Download current revision metadata, white WebP images and float32 embeddings."
        ),
    )

    application.state.api_auth_required = processing_enabled or api_key is not None
    application.state.api_secret = None
    application.add_middleware(ApiKeyMiddleware, application=application)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        detail = (
            exc.detail
            if isinstance(exc.detail, dict)
            else {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
            }
        )
        return JSONResponse(
            status_code=exc.status_code, content={"error": detail}, headers=exc.headers
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Raw input may include image bytes: do not echo it into error responses.
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Check required fields and their allowed values.",
                    "fields": [
                        ".".join(str(part) for part in item["loc"]) for item in exc.errors()
                    ],
                }
            },
        )

    @application.exception_handler(ClothingPipelineError)
    async def pipeline_error(request: Request, exc: ClothingPipelineError):
        if isinstance(exc, DraftNotFoundError):
            status, code, message = 404, "JOB_NOT_FOUND", "Temporary job was not found."
        elif isinstance(exc, DraftConflictError):
            status, code, message = (
                409,
                "JOB_CONFLICT",
                "Request conflicts with current job or capture.",
            )
        elif isinstance(exc, JobQueueFullError):
            status, code, message = (
                429,
                "QUEUE_FULL",
                "Photo queue is full; retry with the same key.",
            )
        else:
            logger.exception("Local clothing service failure")
            status, code, message = (
                503,
                "SERVICE_UNAVAILABLE",
                "Local clothing service is unavailable.",
            )
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "message": message}},
            headers={"Retry-After": "1"} if status == 429 else None,
        )

    @application.get(
        "/health/live", response_model=HealthResponse, operation_id="getLiveness", tags=["Health"]
    )
    def live(request: Request) -> HealthResponse:
        gateway = getattr(request.app.state, "http_jobs", None)
        connected = gateway is not None and gateway.service.health()["worker_alive"]
        # Queue availability is not a GPU warmup or model-readiness assertion.
        return HealthResponse(photo_processing_available=connected)

    @application.get(
        "/health/ready",
        response_model=ReadinessResponse,
        responses={503: {"model": ReadinessResponse}},
        operation_id="getReadiness",
        tags=["Health"],
    )
    def ready(request: Request):
        gateway = getattr(request.app.state, "http_jobs", None)
        service = gateway.service if gateway is not None else None
        preparation = getattr(service, "runtime_preparation", {}) or {}
        warmed = preparation.get("status") == "READY"
        connected = service is not None and service.health()["worker_alive"]
        ready_now = warmed and connected
        response = ReadinessResponse(
            status="READY" if ready_now else "NOT_READY",
            models_warmed=warmed,
            loaded_models=tuple(preparation.get("loadedModels", ())),
            startup_preparation_seconds=preparation.get("startupPreparationSeconds"),
            device=preparation.get("device"),
            segmentation_backend=preparation.get("segmentationBackend"),
        )
        return JSONResponse(
            status_code=200 if ready_now else 503,
            content=response.model_dump(by_alias=True),
            headers={"Cache-Control": "no-store"},
        )

    @application.get(
        "/v1/clothing/taxonomy",
        response_model=TaxonomyResponse,
        operation_id="getClothingTaxonomy",
        dependencies=[Depends(require_api_key)],
        tags=["Clothing"],
    )
    def taxonomy() -> TaxonomyResponse:
        return build_taxonomy()

    application.include_router(router, dependencies=[Depends(require_api_key)])
    application.include_router(results_router, dependencies=[Depends(require_api_key)])
    application.include_router(controls_router, dependencies=[Depends(require_api_key)])
    return application


app = create_app(processing_enabled=True)
