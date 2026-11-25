"""HTTP upload/status adapter over the existing single-worker clothing core."""

import hashlib
import io
import json
import warnings
from dataclasses import replace
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from PIL import Image
from pydantic import Field

from gardirop_ai_clothing.api_contracts import ApiCategory, ApiModel
from gardirop_ai_clothing.errors import DraftConflictError, ImageProcessingError, JobQueueFullError
from gardirop_ai_clothing.image.io import SUPPORTED_FORMATS, decode_uploaded_image
from gardirop_ai_clothing.jobs import DraftService
from gardirop_ai_clothing.schemas import DraftStatus, PhotoTaskStatus, ViewType


def fail(status: int, code: str, message: str) -> None:
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


class ProcessingError(ApiModel):
    code: str
    stage: Literal["FRONT", "BACK", "ANALYSIS"]
    message: str
    retryable: bool


class ViewProgress(ApiModel):
    photo_task_id: str = Field(alias="photoTaskId")
    capture_id: str = Field(alias="captureId")
    status: PhotoTaskStatus
    attempt: int


class JobProgress(ApiModel):
    job_id: str = Field(alias="jobId")
    revision: int
    category: ApiCategory
    status: Literal["WAITING_VIEWS", "PROCESSING", "READY", "FAILED", "CANCELLED"]
    expires_at: str = Field(alias="expiresAt")
    views: dict[ViewType, ViewProgress]
    result_revision: int | None = Field(alias="resultRevision")
    result_url: str | None = Field(default=None, alias="resultUrl")
    error: ProcessingError | None
    accepted_photo_task_id: str | None = Field(default=None, alias="acceptedPhotoTaskId")
    replayed: bool = False


def ensure_live(state: dict, *, allow_cancelled: bool = False) -> None:
    if state["status"] == DraftStatus.EXPIRED:
        fail(410, "JOB_EXPIRED", "Temporary job has expired; upload again with a new key.")
    if state["status"] == DraftStatus.CONFIRMED or (
        state["status"] == DraftStatus.CANCELLED and not allow_cancelled
    ):
        fail(409, "JOB_CLOSED", "Job is closed.")


def analysis_retry_binding(state: dict) -> str:
    payload = {"category": state["category"], "views": state["views"]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def analysis_attempt_count(state: dict) -> int:
    record = state.get("http_analysis_retries", {})
    if record.get("binding") != analysis_retry_binding(state):
        return 1
    return 1 + len(
        {
            value
            for value in record.get("from_revisions", [])
            if type(value) is int and value < state["revision"]
        }
    )


class HttpJobs:
    """One adapter per worker. Idempotency records live inside its temporary store.

    All creation/replay decisions use the repository RLock also held by the core.
    A successful replay never submits another task, including after a restart.
    """

    def __init__(self, service: DraftService):
        self.service = service

    def progress(self, state: dict, *, accepted=None, replayed=False) -> JobProgress:
        ensure_live(state, allow_cancelled=True)
        statuses = [state["jobs"][job]["status"] for job in state["views"].values()]
        native = state["status"]
        status = {
            DraftStatus.WAITING_VIEWS: "WAITING_VIEWS",
            DraftStatus.ANALYZING: "PROCESSING",
            DraftStatus.REVIEW_READY: "READY",
            DraftStatus.FAILED: "FAILED",
            DraftStatus.CANCELLED: "CANCELLED",
        }[native]
        if native == DraftStatus.WAITING_VIEWS and any(
            value in {PhotoTaskStatus.QUEUED, PhotoTaskStatus.PROCESSING} for value in statuses
        ):
            status = "PROCESSING"
        error = None
        if native == DraftStatus.FAILED:
            stage, cause, attempt = (
                "ANALYSIS",
                state.get("error") or {},
                analysis_attempt_count(state),
            )
            for view, task in state["views"].items():
                job = state["jobs"][task]
                if job["status"] == PhotoTaskStatus.FAILED:
                    stage, cause, attempt = view, job.get("error") or {}, job["attempt"]
                    break
            code = cause.get("code", "PROCESSING_FAILED")
            allowed = {
                "PROCESS_RESTARTED",
                "QUEUE_TIMEOUT",
                "PROCESSING_TIMEOUT",
                "INFERENCE_ERROR",
                "IMAGE_PROCESSING_ERROR",
                "MODEL_ARTIFACT_ERROR",
                "CONFIGURATION_ERROR",
                "PAIR_FAILED",
                "PHOTO_FAILED",
                "WORKER_FAILED",
            }
            if code not in allowed:
                code = "PROCESSING_FAILED"
            error = ProcessingError(
                code=code,
                stage=stage,
                message="Processing failed. Refresh the job before deciding whether to retry.",
                retryable=attempt < self.service.max_attempts
                and code
                in {
                    "PROCESS_RESTARTED",
                    "QUEUE_TIMEOUT",
                    "PROCESSING_TIMEOUT",
                    "INFERENCE_ERROR",
                    "PAIR_FAILED",
                    "PHOTO_FAILED",
                    "WORKER_FAILED",
                },
            )
        return JobProgress(
            job_id=state["id"],
            revision=state["revision"],
            category=ApiCategory.from_internal(state["category"]),
            status=status,
            expires_at=datetime.fromtimestamp(state["expires_at"], tz=UTC).isoformat(),
            views={
                ViewType(view): ViewProgress(
                    photo_task_id=task,
                    capture_id=state["jobs"][task]["capture_id"],
                    status=state["jobs"][task]["status"],
                    attempt=state["jobs"][task]["attempt"],
                )
                for view, task in state["views"].items()
            },
            result_revision=state["result_revision"],
            result_url=(
                f"/v1/clothing/jobs/{state['id']}/results/{state['revision']}"
                if native == DraftStatus.REVIEW_READY
                and state["result_revision"] == state["revision"]
                else None
            ),
            error=error,
            accepted_photo_task_id=accepted,
            replayed=replayed,
        )

    def upload_bytes(self, upload: UploadFile) -> bytes:
        """Validate before creating a job; the worker still owns preprocessing."""
        limit = self.service.analysis.images.max_upload_bytes
        try:
            data = upload.file.read(limit + 1)
        finally:
            upload.file.close()
        if len(data) > limit:
            fail(413, "IMAGE_TOO_LARGE", "Image exceeds the configured byte limit.")
        if not data:
            fail(422, "EMPTY_IMAGE", "Image must contain non-empty bytes.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    if image.format not in SUPPORTED_FORMATS:
                        fail(415, "UNSUPPORTED_IMAGE", "Use JPEG, PNG or WebP.")
        except (OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
            fail(422, "INVALID_IMAGE", "Image could not be decoded safely.")
        # Also checks pixel limits, frames, ICC and truncated pixel data.
        try:
            decoded = decode_uploaded_image(
                data,
                max_upload_bytes=limit,
                max_pixels=self.service.analysis.images.max_pixels,
            )
            decoded.close()
        except ImageProcessingError:
            fail(422, "INVALID_IMAGE", "Image failed size, frame or decoding validation.")
        return data

    def options(self, rotation: int):
        if rotation not in {-90, 0, 90, 180}:
            fail(422, "INVALID_ROTATION", "manualRotation must be -90, 0, 90 or 180.")
        return replace(
            self.service.analysis.images.default_options, manual_rotation=float(rotation)
        )

    def create(self, key: str, category: ApiCategory, capture: str, data: bytes, rotation: int):
        options = self.options(rotation)
        key = key.strip()
        capture = capture.strip()
        if not key or not capture:
            fail(422, "EMPTY_IDENTIFIER", "Idempotency-Key and captureId cannot be blank.")
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        signature = hashlib.sha256(
            json.dumps(
                {
                    "category": category.value,
                    "captureId": capture,
                    "rotation": rotation,
                    "imageSha256": hashlib.sha256(data).hexdigest(),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        service = self.service
        with service.repository.lock:
            found = None
            for draft_id in service.repository.ids():
                state = service.get(draft_id)
                record = state.get("http_create", {})
                if record.get("key_hash") == key_hash:
                    if record["signature"] != signature:
                        raise DraftConflictError("Idempotency key was used with different input.")
                    ensure_live(state)
                    found = state
                    break
            replayed = found is not None
            if found is None:
                # Reject a full queue before creating a temporary job folder.
                if service.health()["pending_jobs"] >= service.capacity:
                    raise JobQueueFullError("Photo queue is full.")
                found = service.create_draft(category.to_internal())
                found["http_create"] = {"key_hash": key_hash, "signature": signature}
                service.repository.save(found)
            task = found["captures"].get(capture)
            if task is None:
                # A restart between durable creation and submission can resume here.
                job = service.submit_photo(
                    found["id"],
                    view_type=ViewType.FRONT,
                    capture_id=capture,
                    image_bytes=data,
                    expected_revision=found["revision"],
                    options=options,
                )
                task = job["id"]
            return self.progress(service.get(found["id"]), accepted=task, replayed=replayed)

    def put(
        self,
        draft_id: str,
        view: ViewType,
        capture: str,
        data: bytes,
        expected_revision: int,
        rotation: int,
    ):
        options = self.options(rotation)
        capture = capture.strip()
        if not capture:
            fail(422, "EMPTY_IDENTIFIER", "captureId cannot be blank.")
        with self.service.repository.lock:
            state = self.service.get(draft_id)
            ensure_live(state)
            replayed = capture in state["captures"]
            job = self.service.submit_photo(
                draft_id,
                view_type=view,
                capture_id=capture,
                image_bytes=data,
                expected_revision=expected_revision,
                options=options,
            )
            return self.progress(self.service.get(draft_id), accepted=job["id"], replayed=replayed)


def get_http_jobs(request: Request) -> HttpJobs:
    gateway = getattr(request.app.state, "http_jobs", None)
    if gateway is None or not gateway.service.health()["worker_alive"]:
        fail(503, "PROCESSING_UNAVAILABLE", "Photo worker is not available.")
    return gateway


router = APIRouter(prefix="/v1/clothing/jobs", tags=["Photo jobs"])
Gateway = Annotated[HttpJobs, Depends(get_http_jobs)]
Capture = Annotated[str, Form(alias="captureId", min_length=1, max_length=128)]
Rotation = Annotated[int, Form(alias="manualRotation")]


@router.post("", response_model=JobProgress, status_code=202, operation_id="createClothingJob")
def create_job(
    response: Response,
    gateway: Gateway,
    image: Annotated[UploadFile, File(description="Front photograph: JPEG, PNG or WebP.")],
    category: Annotated[ApiCategory, Form()],
    capture_id: Capture,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    manual_rotation: Rotation = 0,
) -> JobProgress:
    result = gateway.create(
        idempotency_key,
        category,
        capture_id,
        gateway.upload_bytes(image),
        manual_rotation,
    )
    response.status_code = 200 if result.replayed else 202
    response.headers["Location"] = f"/v1/clothing/jobs/{result.job_id}"
    response.headers["Cache-Control"] = "no-store"
    return result


@router.put(
    "/{job_id}/views/{view}",
    response_model=JobProgress,
    status_code=202,
    operation_id="submitClothingView",
)
def submit_view(
    job_id: str,
    view: ViewType,
    response: Response,
    gateway: Gateway,
    image: Annotated[UploadFile, File()],
    capture_id: Capture,
    expected_revision: Annotated[int, Form(alias="expectedRevision", ge=1)],
    manual_rotation: Rotation = 0,
) -> JobProgress:
    result = gateway.put(
        job_id,
        view,
        capture_id,
        gateway.upload_bytes(image),
        expected_revision,
        manual_rotation,
    )
    response.status_code = 200 if result.replayed else 202
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/{job_id}", response_model=JobProgress, operation_id="getClothingJob")
def job_status(job_id: str, response: Response, gateway: Gateway) -> JobProgress:
    with gateway.service.repository.lock:
        result = gateway.progress(gateway.service.get(job_id))
    response.headers["Cache-Control"] = "no-store"
    return result
