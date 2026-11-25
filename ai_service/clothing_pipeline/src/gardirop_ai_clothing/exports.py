"""Verified, portable local export of one immutable confirmed draft."""

import hashlib
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

import numpy as np

from gardirop_ai_clothing.embeddings.fusion import fuse_views
from gardirop_ai_clothing.errors import DraftConflictError, LocalStorageError
from gardirop_ai_clothing.image.io import WHITE_OUTPUT_PROFILE
from gardirop_ai_clothing.jobs import DraftService
from gardirop_ai_clothing.schemas import ClothingAnalysisResult, DraftStatus

EXPORT_FILES = {"front.webp", "back.webp", "embedding.npz", "result.json", "manifest.json"}


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()


def _verify_archive(path: Path, payload: dict[str, bytes], manifest: dict):
    try:
        with zipfile.ZipFile(path) as archive:
            if (
                len(archive.namelist()) != 5
                or set(archive.namelist()) != EXPORT_FILES
                or archive.testzip() is not None
            ):
                raise LocalStorageError("Export ZIP member/CRC mismatch.")
            if json.loads(archive.read("manifest.json")) != manifest:
                raise LocalStorageError("Export manifest differs from the confirmed snapshot.")
            for name, expected in payload.items():
                if archive.read(name) != expected:
                    raise LocalStorageError(
                        f"Export payload differs from the confirmed snapshot: {name}"
                    )
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        raise LocalStorageError("Confirmed export ZIP is unreadable or corrupt.") from exc


def export_confirmed_draft(
    service: DraftService,
    draft_id: str,
    export_dir: str | Path,
    *,
    expected_revision: int,
) -> Path:
    """Same confirmed revision yields one verified ZIP; no DB or cloud calls."""
    repo = service.repository
    with repo.lock:
        state = service.get(draft_id)
        if (
            type(expected_revision) is not int
            or state["revision"] != expected_revision
            or state["status"] != DraftStatus.CONFIRMED
            or state["result_revision"] != expected_revision
            or state["confirmation"]["view_jobs"] != state["views"]
        ):
            raise DraftConflictError("Only the current confirmed draft can be exported.")
        result = service.get_result(draft_id)
        views = {
            v: repo.load_view(state["jobs"][j]["view_path"]) for v, j in state["views"].items()
        }
        front, back = views["FRONT"], views["BACK"]
        fused = fuse_views(front=front.embedding, back=back.embedding)
        if not np.allclose(fused, result.embedding, atol=1e-7, rtol=0):
            raise LocalStorageError(
                "Confirmed embedding does not match its persisted FRONT/BACK views."
            )
        if front.view_type != "FRONT" or back.view_type != "BACK":
            raise LocalStorageError("Persisted view ordering mismatch.")
        for view, reference in (("FRONT", result.front_image_ref), ("BACK", result.back_image_ref)):
            job = state["jobs"][state["views"][view]]
            if (
                reference != f"{job['view_path']}/clean.webp"
                or views[view].embedding_revision != result.versions.embedding_revision
            ):
                raise LocalStorageError("Confirmed image/producer binding mismatch.")
        portable = {
            **repo.read_json(state["result_path"]),
            "front_image_ref": "front.webp",
            "back_image_ref": "back.webp",
        }
        ClothingAnalysisResult.model_validate(portable)
        arrays = io.BytesIO()
        np.savez_compressed(
            arrays,
            embedding=np.asarray(result.embedding, dtype=np.float32),
            front=front.embedding,
            back=back.embedding,
            view_order=np.array(["FRONT", "BACK"]),
            encoder_revision=np.array(result.versions.embedding_revision),
            classifier_sha256=np.array(result.versions.classifier_artifact_sha256),
        )
        payload = {
            "front.webp": front.prepared.delivery_webp,
            "back.webp": back.prepared.delivery_webp,
            "embedding.npz": arrays.getvalue(),
            "result.json": _json_bytes(portable),
        }
        manifest = {
            "schema_version": 1,
            "scope": "local_confirmed_clothing_export",
            "backend_persisted": False,
            "draft_id": draft_id,
            "draft_revision": expected_revision,
            "confirmed_at": state["confirmation"]["confirmed_at"],
            "view_jobs": state["views"],
            "user_tag_overrides": state["tag_overrides"],
            "files_sha256": {
                name: hashlib.sha256(data).hexdigest() for name, data in payload.items()
            },
        }
        if front.prepared.white_webp is not None or back.prepared.white_webp is not None:
            manifest["image_output"] = {
                view: dict(WHITE_OUTPUT_PROFILE)
                if data.prepared.white_webp is not None
                else {"profile": data.prepared.delivery_profile}
                for view, data in views.items()
            }
        directory = Path(export_dir).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination = directory / f"{draft_id}_r{expected_revision}.zip"
        if destination.exists():
            _verify_archive(destination, payload, manifest)
            return destination
        fd, temporary = tempfile.mkstemp(prefix=".export-", suffix=".zip", dir=directory)
        os.close(fd)
        temporary = Path(temporary)
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, data in payload.items():
                    archive.writestr(name, data)
                archive.writestr("manifest.json", _json_bytes(manifest))
            _verify_archive(temporary, payload, manifest)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination
