"""Revision-bound downloads from the existing temporary clothing job store."""

import hashlib
import io
from contextlib import contextmanager
from typing import Annotated, Literal

import numpy as np
from fastapi import APIRouter, Path, Response
from PIL import Image
from pydantic import Field, FiniteFloat, JsonValue, ValidationError

from gardirop_ai_clothing.api_contracts import ApiCategory, ApiModel
from gardirop_ai_clothing.api_jobs import Gateway, ensure_live, fail
from gardirop_ai_clothing.errors import LocalStorageError
from gardirop_ai_clothing.image.io import WHITE_OUTPUT_PROFILE
from gardirop_ai_clothing.schemas import DraftStatus, ViewType


class SuggestedTags(ApiModel):
    sub_category: str | None = Field(alias="subCategory")
    color: str | None
    season: str | None
    has_print: bool | None = Field(alias="hasPrint")


class ProducerVersions(ApiModel):
    taxonomy_version: str = Field(alias="taxonomyVersion")
    preprocessing_version: str = Field(alias="preprocessingVersion")
    embedding_revision: str = Field(alias="embeddingRevision")
    classifier_artifact_sha256: str = Field(alias="classifierArtifactSha256")
    fusion_method: str = Field(alias="fusionMethod")


class ImageDownload(ApiModel):
    url: str
    content_type: Literal["image/webp"] = Field(default="image/webp", alias="contentType")
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    byte_length: int = Field(alias="byteLength", ge=1)
    sha256: str
    background: Literal["#FFFFFF"] = "#FFFFFF"
    mode: Literal["RGB"] = "RGB"
    lossless: Literal[True] = True


class EmbeddingDownload(ApiModel):
    url: str
    dimension: Literal[1536] = 1536
    dtype: Literal["float32"] = "float32"
    view_order: tuple[Literal["FRONT"], Literal["BACK"]] = Field(
        default=("FRONT", "BACK"), alias="viewOrder"
    )


class ResultDownload(ApiModel):
    job_id: str = Field(alias="jobId")
    revision: int
    category: ApiCategory
    tags: SuggestedTags
    versions: ProducerVersions
    images: dict[ViewType, ImageDownload]
    embedding: EmbeddingDownload
    model_diagnostics: dict[str, JsonValue] = Field(alias="modelDiagnostics")


class EmbeddingValues(ApiModel):
    job_id: str = Field(alias="jobId")
    revision: int
    dimension: Literal[1536] = 1536
    dtype: Literal["float32"] = "float32"
    model: str
    encoder_revision: str = Field(alias="encoderRevision")
    fusion_method: str = Field(alias="fusionMethod")
    view_order: tuple[Literal["FRONT"], Literal["BACK"]] = Field(
        default=("FRONT", "BACK"), alias="viewOrder"
    )
    norm: FiniteFloat
    values: tuple[FiniteFloat, ...] = Field(min_length=1536, max_length=1536)


@contextmanager
def current_snapshot(gateway, job_id, revision):
    """Hold the same lock used by edits and TTL cleanup until bytes are copied.

    Superseded revisions return 409 even when their old files still exist.
    Downloads never run the encoder or classifier and never extend the TTL.
    """
    service = gateway.service
    with service.repository.lock:
        state = service.get(job_id)
        ensure_live(state)
        if (
            state["revision"] != revision
            or state["result_revision"] != revision
            or state["status"] != DraftStatus.REVIEW_READY
        ):
            fail(409, "RESULT_NOT_CURRENT", "Poll the job and request its current READY revision.")
        try:
            result = service.get_result(job_id)
        except ValidationError as exc:
            raise LocalStorageError("Stored result contract is invalid.") from exc
        if (
            result.item_session_id != job_id
            or result.draft_revision != revision
            or result.category != state["category"]
            or state["result_view_jobs"] != state["views"]
        ):
            raise LocalStorageError("Stored result bindings do not match the current job.")
        for view, reference in (
            (ViewType.FRONT, result.front_image_ref),
            (ViewType.BACK, result.back_image_ref),
        ):
            task_id = state["views"][view]
            task = state["jobs"][task_id]
            expected = f"drafts/{job_id}/jobs/{task_id}/view-{task['attempt']}"
            if task["view_path"] != expected or reference != f"{expected}/clean.webp":
                raise LocalStorageError("Stored image binding mismatch.")
        yield state, result


def image_payload(gateway, state, view):
    task = state["jobs"][state["views"][view]]
    directory = task["view_path"]
    record = gateway.service.repository.read_json(f"{directory}/view.json")
    try:
        if record.get("image_output") != WHITE_OUTPUT_PROFILE or record["view_type"] != view:
            raise LocalStorageError("Stored view has no matching white RGB output profile.")
        payload = gateway.service.repository.path(f"{directory}/clean.webp").read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != record["files"]["clean.webp"]:
            raise LocalStorageError("Stored image checksum mismatch.")
        with Image.open(io.BytesIO(payload)) as image:
            if image.format != "WEBP" or image.mode != "RGB":
                raise LocalStorageError("Expected RGB WebP output.")
            size = image.size
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise LocalStorageError("Cannot read stored image output.") from exc
    return payload, digest, size


def download_headers(revision):
    return {
        "Cache-Control": "no-store",
        "X-Result-Revision": str(revision),
        "X-Content-Type-Options": "nosniff",
    }


router = APIRouter(prefix="/v1/clothing/jobs", tags=["Clothing results"])
Revision = Annotated[int, Path(ge=1)]


@router.get(
    "/{job_id}/results/{revision}", response_model=ResultDownload, operation_id="getClothingResult"
)
def get_result(job_id: str, revision: Revision, response: Response, gateway: Gateway):
    with current_snapshot(gateway, job_id, revision) as (state, result):
        base = f"/v1/clothing/jobs/{job_id}/results/{revision}"
        images = {}
        for view in ViewType:
            payload, digest, (width, height) = image_payload(gateway, state, view)
            images[view] = ImageDownload(
                url=f"{base}/images/{view.value}",
                width=width,
                height=height,
                byte_length=len(payload),
                sha256=digest,
            )
        version = result.versions
        data = ResultDownload(
            job_id=job_id,
            revision=revision,
            category=ApiCategory.from_internal(result.category),
            tags=SuggestedTags(
                sub_category=result.tags.sub_category,
                color=result.tags.color,
                season=result.tags.season,
                has_print=result.tags.has_print,
            ),
            versions=ProducerVersions(
                taxonomy_version=version.taxonomy_version,
                preprocessing_version=version.preprocessing_version,
                embedding_revision=version.embedding_revision,
                classifier_artifact_sha256=version.classifier_artifact_sha256,
                fusion_method=version.fusion_method,
            ),
            images=images,
            embedding=EmbeddingDownload(url=f"{base}/embedding"),
            model_diagnostics={
                key: value
                for key, value in result.model_diagnostics.items()
                if key
                in {"image_output", "segmentation", "classification", "attributes", "embedding"}
            },
        )
    response.headers.update(download_headers(revision))
    return data


@router.get(
    "/{job_id}/results/{revision}/embedding",
    response_model=EmbeddingValues,
    operation_id="getClothingEmbedding",
)
def get_embedding(job_id: str, revision: Revision, response: Response, gateway: Gateway):
    with current_snapshot(gateway, job_id, revision) as (_, result):
        vector = np.asarray(result.embedding, dtype=np.float32)
        data = EmbeddingValues(
            job_id=job_id,
            revision=revision,
            model=result.embedding_model,
            encoder_revision=result.versions.embedding_revision,
            fusion_method=result.versions.fusion_method,
            norm=float(np.linalg.norm(vector.astype(np.float64))),
            values=tuple(float(value) for value in vector),
        )
    response.headers.update(download_headers(revision))
    return data


@router.get(
    "/{job_id}/results/{revision}/images/{view}",
    response_class=Response,
    responses={
        200: {
            "content": {
                "image/webp": {
                    "schema": {
                        "type": "string",
                        "format": "binary",
                    }
                }
            }
        }
    },
    operation_id="getClothingImage",
)
def get_image(job_id: str, revision: Revision, view: ViewType, gateway: Gateway):
    with current_snapshot(gateway, job_id, revision) as (state, _):
        payload, digest, _ = image_payload(gateway, state, view)
    # Bytes are detached before unlocking: edits/cleanup cannot break this response.
    headers = download_headers(revision)
    headers.update(
        {
            "ETag": f'"{digest}"',
            "Content-Disposition": f'inline; filename="{job_id}-r{revision}-{view.value}.webp"',
        }
    )
    return Response(content=payload, media_type="image/webp", headers=headers)
