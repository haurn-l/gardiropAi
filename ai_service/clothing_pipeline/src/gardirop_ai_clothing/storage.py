"""Atomic local draft files. One process owns a repository at a time (Linux)."""

import fcntl
import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, fields
from pathlib import Path
from threading import RLock
from uuid import uuid4

import numpy as np
from PIL import Image

from gardirop_ai_clothing.analysis import AnalyzedView
from gardirop_ai_clothing.errors import DraftNotFoundError, LocalStorageError
from gardirop_ai_clothing.image.io import WHITE_OUTPUT_PROFILE, encode_transparent_webp
from gardirop_ai_clothing.pipeline import ImagePreparationOptions, PreparedGarmentImage
from gardirop_ai_clothing.schemas import ClothingAnalysisResult, ViewType


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LocalDraftRepository:
    """Call from the service under lock; returned state dictionaries are detached."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = RLock()
        self._owner = (self.root / ".owner.lock").open("a+b")
        try:
            fcntl.flock(self._owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._owner.close()
            raise LocalStorageError(
                "Draft repository is already owned by another service."
            ) from exc
        (self.root / "drafts").mkdir(exist_ok=True, mode=0o700)

    def close(self):
        if not self._owner.closed:
            fcntl.flock(self._owner, fcntl.LOCK_UN)
            self._owner.close()

    def path(self, relative: str) -> Path:
        if self._owner.closed:
            raise LocalStorageError("Draft repository is closed.")
        candidate = (self.root / relative).resolve()
        if not candidate.is_relative_to(self.root):
            raise LocalStorageError("Storage path escapes the draft repository.")
        return candidate

    def draft_dir(self, draft_id: str) -> Path:
        if not isinstance(draft_id, str) or not re.fullmatch(r"[0-9a-f]{32}", draft_id):
            raise DraftNotFoundError("Invalid draft ID.")
        return self.path(f"drafts/{draft_id}")

    def write_json(self, relative: str, data: dict):
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(prefix=".write-", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, allow_nan=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def read_json(self, relative: str) -> dict:
        try:
            return json.loads(self.path(relative).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise LocalStorageError(f"Cannot read local record: {relative}") from exc

    def create(self, state: dict):
        self.draft_dir(state["id"]).mkdir(mode=0o700)
        self.save(state)

    def save(self, state: dict):
        self.write_json(f"drafts/{state['id']}/state.json", state)

    def get(self, draft_id: str) -> dict:
        folder = self.draft_dir(draft_id)
        if not (folder / "state.json").is_file():
            raise DraftNotFoundError("Draft does not exist or was cleaned up.")
        return self.read_json(f"drafts/{draft_id}/state.json")

    def ids(self) -> list[str]:
        if self._owner.closed:
            raise LocalStorageError("Draft repository is closed.")
        return sorted(p.parent.name for p in (self.root / "drafts").glob("*/state.json"))

    def remove(self, draft_id: str):
        shutil.rmtree(self.draft_dir(draft_id))

    def save_view(self, draft_id: str, job_id: str, attempt: int, view: AnalyzedView) -> str:
        if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise LocalStorageError("Invalid photo job ID.")
        if type(attempt) is not int or attempt < 1:
            raise LocalStorageError("Invalid photo attempt.")
        base = self.draft_dir(draft_id) / "jobs" / job_id
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination = base / f"view-{attempt}"
        temporary = base / f".view-{uuid4().hex}"
        temporary.mkdir(mode=0o700)
        try:
            prepared = view.prepared
            for name, image in (
                ("cutout", prepared.original_cutout),
                ("aligned", prepared.aligned_rgba),
                ("white", prepared.white_rgb),
            ):
                image.save(temporary / f"{name}.png")
            (temporary / "clean.webp").write_bytes(prepared.delivery_webp)
            np.savez_compressed(
                temporary / "arrays.npz",
                embedding=view.embedding,
                raw_alpha=prepared.raw_alpha,
                final_alpha=prepared.final_alpha,
            )
            excluded = {
                "raw_alpha",
                "final_alpha",
                "original_cutout",
                "aligned_rgba",
                "white_rgb",
                "transparent_webp",
                "white_webp",
            }
            record = {
                "view_type": view.view_type.value,
                "options": asdict(view.options),
                "preprocessing_version": view.preprocessing_version,
                "embedding_revision": view.embedding_revision,
                "segmentation_revision": view.segmentation_revision,
                "image": {
                    f.name: getattr(prepared, f.name)
                    for f in fields(prepared)
                    if f.name not in excluded
                },
                "files": {p.name: sha256(p) for p in temporary.iterdir()},
            }
            if prepared.white_webp is not None:
                record["image_output"] = dict(WHITE_OUTPUT_PROFILE)
            (temporary / "view.json").write_text(
                json.dumps(record, ensure_ascii=False, allow_nan=False), encoding="utf-8"
            )
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return str(destination.relative_to(self.root))

    def load_view(self, relative: str) -> AnalyzedView:
        folder = self.path(relative)
        record = self.read_json(f"{relative}/view.json")
        expected_files = {"cutout.png", "aligned.png", "white.png", "clean.webp", "arrays.npz"}
        if set(record["files"]) != expected_files:
            raise LocalStorageError("Stored view file set mismatch.")
        for name, expected in record["files"].items():
            if sha256(folder / name) != expected:
                raise LocalStorageError("Stored view SHA256 mismatch.")
        output_profile = record.get("image_output")
        if output_profile is not None and output_profile != WHITE_OUTPUT_PROFILE:
            raise LocalStorageError("Unsupported stored image output profile.")
        payload = (folder / "clean.webp").read_bytes()
        images = {}
        for name, mode in (("cutout", "RGBA"), ("aligned", "RGBA"), ("white", "RGB")):
            with Image.open(folder / f"{name}.png") as source:
                images[name] = source.convert(mode)
        with np.load(folder / "arrays.npz", allow_pickle=False) as data:
            embedding = data["embedding"].copy()
            raw, final = data["raw_alpha"].copy(), data["final_alpha"].copy()
        embedding.setflags(write=False)
        info = record["image"]
        info["source_size"] = tuple(info["source_size"])
        prepared = PreparedGarmentImage(
            **info,
            raw_alpha=raw,
            final_alpha=final,
            original_cutout=images["cutout"],
            aligned_rgba=images["aligned"],
            white_rgb=images["white"],
            transparent_webp=encode_transparent_webp(images["aligned"])
            if output_profile
            else payload,
            white_webp=payload if output_profile else None,
        )
        return AnalyzedView(
            view_type=ViewType(record["view_type"]),
            prepared=prepared,
            embedding=embedding,
            options=ImagePreparationOptions(**record["options"]),
            preprocessing_version=record["preprocessing_version"],
            embedding_revision=record["embedding_revision"],
            segmentation_revision=record["segmentation_revision"],
        )

    def save_result(self, result: ClothingAnalysisResult) -> str:
        self.draft_dir(result.item_session_id)
        relative = f"drafts/{result.item_session_id}/results/r{result.draft_revision}.json"
        self.write_json(relative, result.model_dump(mode="json"))
        return relative

    def load_result(self, relative: str) -> ClothingAnalysisResult:
        return ClothingAnalysisResult.model_validate(self.read_json(relative))
