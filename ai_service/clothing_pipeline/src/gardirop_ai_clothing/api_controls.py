"""HTTP edits and bounded retries; no database or confirmation endpoint."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response
from pydantic import Field

from gardirop_ai_clothing.api_contracts import ApiCategory, ApiModel
from gardirop_ai_clothing.api_jobs import (
    Gateway,
    JobProgress,
    analysis_attempt_count,
    analysis_retry_binding,
    ensure_live,
    fail,
)
from gardirop_ai_clothing.schemas import DraftStatus, PhotoTaskStatus

router = APIRouter(prefix="/v1/clothing/jobs", tags=["Job controls"])


class ChangeCategory(ApiModel):
    category: ApiCategory
    expected_revision: int = Field(alias="expectedRevision", strict=True, ge=1)


class RetryStage(ApiModel):
    stage: Literal["FRONT", "BACK", "ANALYSIS"]
    expected_revision: int = Field(alias="expectedRevision", strict=True, ge=1)


@router.patch(
    "/{job_id}/category", response_model=JobProgress, operation_id="changeClothingCategory"
)
def change_category(job_id: str, body: ChangeCategory, response: Response, gateway: Gateway):
    service = gateway.service
    with service.repository.lock:
        before = service.get(job_id)
        ensure_live(before)
        state = service.change_category(
            job_id,
            body.category.to_internal(),
            expected_revision=body.expected_revision,
        )
        if state["revision"] != before["revision"]:
            # A new category is a new analysis context, even after switching back.
            state.pop("http_analysis_retries", None)
            service.repository.save(state)
        result = gateway.progress(state, replayed=before["revision"] != body.expected_revision)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/{job_id}/retry",
    response_model=JobProgress,
    status_code=202,
    operation_id="retryClothingStage",
)
def retry_stage(job_id: str, body: RetryStage, response: Response, gateway: Gateway):
    service = gateway.service
    with service.repository.lock:
        state = service.get(job_id)
        ensure_live(state)
        # Check before calling core retry_photo, which permits READY/PENDING replay.
        if state["revision"] != body.expected_revision:
            fail(409, "REVISION_CONFLICT", "Refresh the job before retrying.")
        if body.stage == "ANALYSIS":
            if state["status"] != DraftStatus.FAILED or not all(
                view in state["views"]
                and state["jobs"][state["views"][view]]["status"] == PhotoTaskStatus.READY
                for view in ("FRONT", "BACK")
            ):
                fail(
                    409,
                    "STAGE_NOT_FAILED",
                    "Both views must be READY and analysis must have failed.",
                )
            summary = gateway.progress(state)
            if summary.error is None or not summary.error.retryable:
                fail(
                    409,
                    "NOT_RETRYABLE",
                    "Analysis is not retryable or its attempt limit was reached.",
                )
            if analysis_attempt_count(state) >= service.max_attempts:
                fail(409, "NOT_RETRYABLE", "Analysis attempt limit was reached.")
            binding = analysis_retry_binding(state)
            history = state.get("http_analysis_retries", {})
            revisions = (
                list(history.get("from_revisions", [])) if history.get("binding") == binding else []
            )
            if body.expected_revision not in revisions:
                revisions.append(body.expected_revision)
            # Journal intent before retry's atomic state write. It counts only once
            # core increments the revision; a full queue does not consume an attempt.
            state["http_analysis_retries"] = {"binding": binding, "from_revisions": revisions}
            service.repository.save(state)
            service.retry_analysis(job_id, expected_revision=body.expected_revision)
            task_id = None
        else:
            task_id = state["views"].get(body.stage)
            task = state["jobs"].get(task_id)
            if task is None or task["status"] != PhotoTaskStatus.FAILED:
                fail(409, "STAGE_NOT_FAILED", "Only a failed current photograph can be retried.")
            retryable = {
                "PROCESS_RESTARTED",
                "QUEUE_TIMEOUT",
                "PROCESSING_TIMEOUT",
                "INFERENCE_ERROR",
                "PHOTO_FAILED",
                "WORKER_FAILED",
            }
            if (
                task["attempt"] >= service.max_attempts
                or (task.get("error") or {}).get("code") not in retryable
            ):
                fail(
                    409, "NOT_RETRYABLE", "Photo is not retryable or its attempt limit was reached."
                )
            service.retry_photo(job_id, task_id, expected_revision=body.expected_revision)
        result = gateway.progress(service.get(job_id), accepted=task_id)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.delete(
    "/{job_id}", status_code=204, response_class=Response, operation_id="cancelClothingJob"
)
def cancel_job(
    job_id: str,
    gateway: Gateway,
    expected_revision: Annotated[int, Query(alias="expectedRevision", ge=1)],
):
    service = gateway.service
    with service.repository.lock:
        state = service.get(job_id)
        if state["status"] != DraftStatus.CANCELLED:
            ensure_live(state)
            service.cancel(job_id, expected_revision=expected_revision)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
