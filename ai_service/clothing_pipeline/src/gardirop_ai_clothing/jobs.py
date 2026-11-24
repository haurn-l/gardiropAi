"""Bounded single-worker draft lifecycle, using the existing analysis core."""

import hashlib
import json
import time
from collections import deque
from dataclasses import asdict
from queue import Empty, Queue
from threading import Condition, Thread
from uuid import uuid4

from gardirop_ai_clothing.analysis import ClothingAnalysisService, create_analysis_service
from gardirop_ai_clothing.config import Settings
from gardirop_ai_clothing.contracts import MainCategory
from gardirop_ai_clothing.errors import (
    DraftConflictError,
    DraftNotFoundError,
    ImageProcessingError,
    JobQueueFullError,
)
from gardirop_ai_clothing.pipeline import ImagePreparationOptions
from gardirop_ai_clothing.schemas import (
    ClothingAnalysisResult,
    ClothingTags,
    DraftStatus,
    PhotoTaskStatus,
    ViewType,
)
from gardirop_ai_clothing.storage import LocalDraftRepository

CLOSED = {DraftStatus.CONFIRMED, DraftStatus.CANCELLED, DraftStatus.EXPIRED}
PENDING = {PhotoTaskStatus.QUEUED, PhotoTaskStatus.PROCESSING}


class DraftService:
    """Own one repository and one worker per application, not per request.

    Revision changes describe user edits. Worker status changes do not increment
    revision. In-flight inference cannot be preempted; late/cancelled results are
    discarded. Processing timeout is checked when inference returns.
    """

    def __init__(
        self,
        repository: LocalDraftRepository,
        analysis: ClothingAnalysisService,
        *,
        ttl_seconds=3600,
        terminal_retention_seconds=300,
        max_pending_jobs=8,
        queue_timeout_seconds=120,
        processing_timeout_seconds=120,
        max_attempts=3,
        clock=time.time,
    ):
        if (
            ttl_seconds <= 0
            or terminal_retention_seconds < 0
            or max_pending_jobs < 1
            or queue_timeout_seconds <= 0
            or processing_timeout_seconds <= 0
            or max_attempts < 1
        ):
            raise ValueError("Invalid draft lifecycle limits.")
        self.repository, self.analysis, self.clock = repository, analysis, clock
        self.ttl, self.retention = ttl_seconds, terminal_retention_seconds
        self.capacity, self.queue_timeout = max_pending_jobs, queue_timeout_seconds
        self.processing_timeout, self.max_attempts = processing_timeout_seconds, max_attempts
        self._queue = Queue()
        self._condition = Condition(repository.lock)
        self._pending = 0
        self._closing = False
        self.worker_errors = deque(maxlen=20)
        with repository.lock:
            self._recover()
        self._worker = Thread(target=self._run, name="gardropai-photo-worker", daemon=True)
        self._worker.start()

    def _live(self, draft_id):
        state = self.repository.get(draft_id)
        if state["status"] not in CLOSED and self.clock() >= state["expires_at"]:
            state.update(status=DraftStatus.EXPIRED, terminal_at=self.clock(), result_path=None)
            for job in state["jobs"].values():
                if job["status"] in PENDING:
                    job.update(status=PhotoTaskStatus.CANCELLED, error={"code": "DRAFT_EXPIRED"})
            self.repository.save(state)
        return state

    def _editable(self, state, expected_revision):
        if self._closing or state["status"] in CLOSED:
            raise DraftConflictError("Draft/service is closed.")
        if type(expected_revision) is not int or expected_revision != state["revision"]:
            raise DraftConflictError("Draft revision changed; refresh before editing.")

    def _touch(self, state):
        state.update(
            revision=state["revision"] + 1,
            expires_at=self.clock() + self.ttl,
            result_path=None,
            result_revision=None,
            result_view_jobs=None,
            error=None,
            last_edit=None,
        )

    def _same_edit(self, state, kind, payload, expected_revision):
        return type(expected_revision) is int and state.get("last_edit") == {
            "kind": kind,
            "payload": payload,
            "from_revision": expected_revision,
            "to_revision": state["revision"],
        }

    def _reserve(self):
        if self._closing:
            raise DraftConflictError("Service is closing.")
        if self._pending >= self.capacity:
            raise JobQueueFullError("Photo queue is full; retry later with the same request.")
        self._pending += 1

    def _release(self):
        self._pending -= 1
        self._condition.notify_all()

    def create_draft(self, category: MainCategory | str) -> dict:
        category = MainCategory(category)
        with self.repository.lock:
            if self._closing:
                raise DraftConflictError("Service is closing.")
            now = self.clock()
            state = {
                "schema_version": 1,
                "id": uuid4().hex,
                "revision": 1,
                "category": category.value,
                "status": DraftStatus.WAITING_VIEWS,
                "created_at": now,
                "expires_at": now + self.ttl,
                "terminal_at": None,
                "views": {},
                "jobs": {},
                "captures": {},
                "tag_overrides": {},
                "result_path": None,
                "result_revision": None,
                "result_view_jobs": None,
                "error": None,
                "confirmation": None,
            }
            self.repository.create(state)
            return state

    def get(self, draft_id) -> dict:
        with self.repository.lock:
            return self._live(draft_id)

    def submit_photo(
        self,
        draft_id,
        *,
        view_type,
        capture_id,
        image_bytes,
        expected_revision,
        options: ImagePreparationOptions | None = None,
    ) -> dict:
        view = ViewType(view_type)
        if not isinstance(capture_id, str) or not 1 <= len(capture_id.strip()) <= 128:
            raise ValueError("capture_id must contain 1..128 characters.")
        capture_id = capture_id.strip()
        if (
            not isinstance(image_bytes, bytes)
            or not image_bytes
            or len(image_bytes) > self.analysis.images.max_upload_bytes
        ):
            raise ImageProcessingError("Photo is empty or exceeds the configured byte limit.")
        options = options or self.analysis.images.default_options
        signature = hashlib.sha256(
            image_bytes
            + json.dumps({"view": view.value, "options": asdict(options)}, sort_keys=True).encode()
        ).hexdigest()
        with self.repository.lock:
            state = self._live(draft_id)
            existing = state["captures"].get(capture_id)
            if existing:
                job = state["jobs"][existing]
                if job["signature"] != signature:
                    raise DraftConflictError(
                        "capture_id was already used with different photo/options/view."
                    )
                return json.loads(json.dumps(job))
            self._editable(state, expected_revision)
            self._reserve()
            try:
                previous = state["jobs"].get(state["views"].get(view.value))
                if previous:
                    previous["status"] = PhotoTaskStatus.DISCARDED
                job_id = uuid4().hex
                folder = self.repository.draft_dir(draft_id) / "jobs" / job_id
                folder.mkdir(parents=True, mode=0o700)
                (folder / "input.bin").write_bytes(image_bytes)
                self._touch(state)
                job = {
                    "id": job_id,
                    "capture_id": capture_id,
                    "view_type": view.value,
                    "view_revision": previous["view_revision"] + 1 if previous else 1,
                    "submission_revision": state["revision"],
                    "signature": signature,
                    "status": PhotoTaskStatus.QUEUED,
                    "attempt": 1,
                    "queued_at": self.clock(),
                    "started_at": None,
                    "finished_at": None,
                    "error": None,
                    "view_path": None,
                    "options": asdict(options),
                }
                state["jobs"][job_id] = job
                state["views"][view.value] = job_id
                state["captures"][capture_id] = job_id
                state.update(status=DraftStatus.WAITING_VIEWS, tag_overrides={})
                self.repository.save(state)
                self._queue.put(("photo", draft_id, job_id, 1))
                return json.loads(json.dumps(job))
            except Exception:
                self._release()
                raise

    def retry_photo(self, draft_id, job_id, *, expected_revision) -> dict:
        with self.repository.lock:
            state = self._live(draft_id)
            job = state["jobs"].get(job_id)
            if job is None or state["views"].get(job["view_type"]) != job_id:
                raise DraftConflictError("Only the current photo job can be retried.")
            if state["status"] in CLOSED:
                raise DraftConflictError("Draft is closed.")
            if job["status"] in {*PENDING, PhotoTaskStatus.READY}:
                return job
            self._editable(state, expected_revision)
            if job["status"] != PhotoTaskStatus.FAILED or job["attempt"] >= self.max_attempts:
                raise DraftConflictError("Photo job is not retryable or attempt limit reached.")
            self._reserve()
            try:
                self._touch(state)
                job.update(
                    status=PhotoTaskStatus.QUEUED,
                    attempt=job["attempt"] + 1,
                    queued_at=self.clock(),
                    started_at=None,
                    finished_at=None,
                    error=None,
                )
                state["status"] = DraftStatus.WAITING_VIEWS
                self.repository.save(state)
                self._queue.put(("photo", draft_id, job_id, job["attempt"]))
                return job
            except Exception:
                self._release()
                raise

    def _ready(self, state):
        return all(
            v in state["views"]
            and state["jobs"][state["views"][v]]["status"] == PhotoTaskStatus.READY
            for v in ("FRONT", "BACK")
        )

    def change_category(self, draft_id, category, *, expected_revision) -> dict:
        category = MainCategory(category)
        with self.repository.lock:
            state = self._live(draft_id)
            if self._same_edit(state, "category", category.value, expected_revision):
                return state
            self._editable(state, expected_revision)
            if state["category"] == category.value:
                return state
            ready = self._ready(state)
            if ready:
                self._reserve()
            try:
                self._touch(state)
                state.update(
                    category=category.value,
                    status=DraftStatus.ANALYZING if ready else DraftStatus.WAITING_VIEWS,
                )
                state["tag_overrides"].pop("sub_category", None)
                state["last_edit"] = {
                    "kind": "category",
                    "payload": category.value,
                    "from_revision": expected_revision,
                    "to_revision": state["revision"],
                }
                if ready:
                    state["analysis_queued_at"] = self.clock()
                self.repository.save(state)
                if ready:
                    self._queue.put(("analysis", draft_id, None, state["revision"]))
                return state
            except Exception:
                if ready:
                    self._release()
                raise

    def retry_analysis(self, draft_id, *, expected_revision) -> dict:
        with self.repository.lock:
            state = self._live(draft_id)
            self._editable(state, expected_revision)
            if state["status"] in {DraftStatus.REVIEW_READY, DraftStatus.ANALYZING}:
                return state
            if not self._ready(state):
                raise DraftConflictError("Both current views must be READY.")
            self._reserve()
            try:
                self._touch(state)
                state["status"] = DraftStatus.ANALYZING
                state["analysis_queued_at"] = self.clock()
                self.repository.save(state)
                self._queue.put(("analysis", draft_id, None, state["revision"]))
                return state
            except Exception:
                self._release()
                raise

    def edit_tags(self, draft_id, patch: dict, *, expected_revision) -> dict:
        patch = ClothingTags.model_validate(patch).model_dump(mode="json", include=set(patch))
        with self.repository.lock:
            state = self._live(draft_id)
            if self._same_edit(state, "tags", patch, expected_revision):
                return state
            self._editable(state, expected_revision)
            if state["status"] != DraftStatus.REVIEW_READY:
                raise DraftConflictError("Tags can be edited only after both views are ready.")
            old = self.repository.load_result(state["result_path"])
            tags = ClothingTags.model_validate({**old.tags.model_dump(), **patch})
            # Full contract validation also checks parent/subcategory compatibility.
            updated = ClothingAnalysisResult.model_validate(
                {
                    **old.model_dump(),
                    "draft_revision": state["revision"] + 1,
                    "tags": tags,
                }
            )
            if tags == old.tags:
                return state
            state["revision"] += 1
            state["expires_at"] = self.clock() + self.ttl
            state["tag_overrides"].update(patch)
            state["result_path"] = self.repository.save_result(updated)
            state["result_revision"] = state["revision"]
            state["last_edit"] = {
                "kind": "tags",
                "payload": patch,
                "from_revision": expected_revision,
                "to_revision": state["revision"],
            }
            self.repository.save(state)
            return state

    def get_result(self, draft_id) -> ClothingAnalysisResult:
        with self.repository.lock:
            state = self._live(draft_id)
            if (
                state["status"] not in {DraftStatus.REVIEW_READY, DraftStatus.CONFIRMED}
                or state["result_revision"] != state["revision"]
            ):
                raise DraftConflictError("No current result is available for review.")
            return self.repository.load_result(state["result_path"])

    def confirm(self, draft_id, *, expected_revision) -> ClothingAnalysisResult:
        with self.repository.lock:
            state = self._live(draft_id)
            if type(expected_revision) is not int or state["revision"] != expected_revision:
                raise DraftConflictError("Confirmation revision changed; review again.")
            if state["status"] == DraftStatus.CONFIRMED:
                return self.repository.load_result(state["result_path"])
            self._editable(state, expected_revision)
            if (
                state["status"] != DraftStatus.REVIEW_READY
                or not self._ready(state)
                or state["result_revision"] != expected_revision
                or state["result_view_jobs"] != state["views"]
            ):
                raise DraftConflictError(
                    "Both current view versions must be reviewed before confirmation."
                )
            result = self.repository.load_result(state["result_path"])
            if (
                result.draft_revision != expected_revision
                or result.category != state["category"]
                or result.item_session_id != draft_id
                or result.front_image_ref
                != f"{state['jobs'][state['views']['FRONT']]['view_path']}/clean.webp"
                or result.back_image_ref
                != f"{state['jobs'][state['views']['BACK']]['view_path']}/clean.webp"
            ):
                raise DraftConflictError("Stored result does not match the current draft.")
            # Re-read and verify the current persisted image/feature files.
            for job_id in state["views"].values():
                self.repository.load_view(state["jobs"][job_id]["view_path"])
            state.update(
                status=DraftStatus.CONFIRMED,
                terminal_at=self.clock(),
                confirmation={
                    "revision": expected_revision,
                    "view_jobs": dict(state["views"]),
                    "result_path": state["result_path"],
                    "confirmed_at": self.clock(),
                },
            )
            self.repository.save(state)
            return result

    def cancel(self, draft_id, *, expected_revision) -> dict:
        with self.repository.lock:
            state = self._live(draft_id)
            if state["status"] in {DraftStatus.CANCELLED, DraftStatus.EXPIRED}:
                return state
            self._editable(state, expected_revision)
            self._touch(state)
            state.update(status=DraftStatus.CANCELLED, terminal_at=self.clock())
            for job in state["jobs"].values():
                if job["status"] in PENDING:
                    job.update(status=PhotoTaskStatus.CANCELLED, error={"code": "DRAFT_CANCELLED"})
            self.repository.save(state)
            return state

    def cleanup(self) -> list[str]:
        removed = []
        with self.repository.lock:
            for draft_id in self.repository.ids():
                state = self._live(draft_id)
                if (
                    state["status"] in {DraftStatus.CANCELLED, DraftStatus.EXPIRED}
                    and self.clock() - state["terminal_at"] >= self.retention
                ):
                    self.repository.remove(draft_id)
                    removed.append(draft_id)
        return removed

    def _recover(self):
        for draft_id in self.repository.ids():
            state = self._live(draft_id)
            if state["status"] in CLOSED:
                continue
            interrupted = state["status"] == DraftStatus.ANALYZING or (
                self._ready(state) and state["result_revision"] != state["revision"]
            )
            for job in state["jobs"].values():
                if job["status"] in PENDING:
                    job.update(status=PhotoTaskStatus.FAILED, error={"code": "PROCESS_RESTARTED"})
                    interrupted = True
            if interrupted:
                state.update(
                    status=DraftStatus.FAILED, result_path=None, error={"code": "PROCESS_RESTARTED"}
                )
                self.repository.save(state)

    def _photo_failure(self, draft_id, job_id, attempt, error):
        with self.repository.lock:
            state = self._live(draft_id)
            job = state["jobs"][job_id]
            if job["attempt"] != attempt or job["status"] not in PENDING:
                return
            if state["status"] in CLOSED or state["views"].get(job["view_type"]) != job_id:
                return
            job.update(status=PhotoTaskStatus.FAILED, finished_at=self.clock(), error=error)
            state.update(status=DraftStatus.FAILED, error=error)
            self.repository.save(state)

    def _process_photo(self, draft_id, job_id, attempt):
        with self.repository.lock:
            state = self._live(draft_id)
            job = state["jobs"][job_id]
            if (
                state["status"] in CLOSED
                or state["views"].get(job["view_type"]) != job_id
                or job["attempt"] != attempt
                or job["status"] != PhotoTaskStatus.QUEUED
            ):
                return
            if self.clock() - job["queued_at"] > self.queue_timeout:
                self._photo_failure(draft_id, job_id, attempt, {"code": "QUEUE_TIMEOUT"})
                return
            job.update(status=PhotoTaskStatus.PROCESSING, started_at=self.clock())
            self.repository.save(state)
            image_bytes = (
                self.repository.draft_dir(draft_id) / "jobs" / job_id / "input.bin"
            ).read_bytes()
            view, options = job["view_type"], ImagePreparationOptions(**job["options"])
            started = self.clock()
        try:
            analyzed = self.analysis.prepare_view(
                image_bytes, view_type=view, options=options, timeout_seconds=self.queue_timeout
            )
            if self.clock() - started > self.processing_timeout:
                raise TimeoutError("PROCESSING_TIMEOUT")
            with self.repository.lock:
                state = self._live(draft_id)
                job = state["jobs"][job_id]
                if (
                    state["status"] in CLOSED
                    or state["views"].get(view) != job_id
                    or job["attempt"] != attempt
                    or job["status"] != PhotoTaskStatus.PROCESSING
                ):
                    return
                path = self.repository.save_view(draft_id, job_id, attempt, analyzed)
                job.update(
                    status=PhotoTaskStatus.READY,
                    view_path=path,
                    finished_at=self.clock(),
                    error=None,
                )
                failed = any(
                    state["jobs"][j]["status"] == PhotoTaskStatus.FAILED
                    for j in state["views"].values()
                )
                state["status"] = DraftStatus.FAILED if failed else DraftStatus.WAITING_VIEWS
                self.repository.save(state)
        except DraftNotFoundError:
            return  # TTL cleanup removed the draft while inference was running.
        except Exception as exc:
            self._photo_failure(
                draft_id,
                job_id,
                attempt,
                {
                    "code": str(exc)
                    if isinstance(exc, TimeoutError)
                    else getattr(exc, "code", "PHOTO_FAILED"),
                    "message": str(exc)[:500],
                },
            )
            return
        self._analyze(draft_id)

    def _analyze(self, draft_id, expected_revision=None):
        with self.repository.lock:
            state = self._live(draft_id)
            if (
                state["status"] in CLOSED
                or not self._ready(state)
                or (expected_revision is not None and state["revision"] != expected_revision)
            ):
                return
            if (
                state["status"] == DraftStatus.REVIEW_READY
                and state["result_revision"] == state["revision"]
            ):
                return
            if (
                expected_revision is not None
                and self.clock() - state.get("analysis_queued_at", self.clock())
                > self.queue_timeout
            ):
                state.update(status=DraftStatus.FAILED, error={"code": "QUEUE_TIMEOUT"})
                self.repository.save(state)
                return
            revision, bindings, category = (
                state["revision"],
                dict(state["views"]),
                state["category"],
            )
            state.update(status=DraftStatus.ANALYZING, error=None)
            self.repository.save(state)
            paths = {v: state["jobs"][j]["view_path"] for v, j in bindings.items()}
            overrides = state["tag_overrides"].copy()
        try:
            with self.repository.lock:
                front, back = (
                    self.repository.load_view(paths["FRONT"]),
                    self.repository.load_view(paths["BACK"]),
                )
            pair = self.analysis.finish_pair(front=front, back=back, main_category=category)
            tags = ClothingTags.model_validate({**pair.tags.model_dump(), **overrides})
            result = ClothingAnalysisResult(
                item_session_id=draft_id,
                draft_revision=revision,
                category=category,
                front_image_ref=f"{paths['FRONT']}/clean.webp",
                back_image_ref=f"{paths['BACK']}/clean.webp",
                tags=tags,
                model_diagnostics=pair.diagnostics,
                embedding_model="Marqo/marqo-fashionSigLIP",
                versions=pair.versions,
                embedding=tuple(float(x) for x in pair.embedding),
            )
            with self.repository.lock:
                state = self._live(draft_id)
                if (
                    state["status"] in CLOSED
                    or state["revision"] != revision
                    or state["views"] != bindings
                ):
                    return
                state.update(
                    status=DraftStatus.REVIEW_READY,
                    result_path=self.repository.save_result(result),
                    result_revision=revision,
                    result_view_jobs=bindings,
                    error=None,
                )
                self.repository.save(state)
        except DraftNotFoundError:
            return
        except Exception as exc:
            with self.repository.lock:
                state = self._live(draft_id)
                if (
                    state["status"] not in CLOSED
                    and state["revision"] == revision
                    and state["views"] == bindings
                ):
                    state.update(
                        status=DraftStatus.FAILED,
                        error={"code": "PAIR_FAILED", "message": str(exc)[:500]},
                    )
                    self.repository.save(state)

    def _run(self):
        next_cleanup = time.monotonic() + 30
        while True:
            if time.monotonic() >= next_cleanup:
                try:
                    self.cleanup()
                except Exception as exc:
                    self.worker_errors.append(str(exc)[:500])
                next_cleanup = time.monotonic() + 30
            try:
                task = self._queue.get(timeout=1)
            except Empty:
                continue
            if task is None:
                self._queue.task_done()
                return
            kind, draft_id, job_id, token = task
            try:
                if kind == "photo":
                    self._process_photo(draft_id, job_id, token)
                else:
                    self._analyze(draft_id, token)
            except DraftNotFoundError:
                pass
            except Exception as exc:
                self.worker_errors.append(str(exc)[:500])
                try:
                    with self.repository.lock:
                        state = self._live(draft_id)
                        current = (kind == "analysis" and state["revision"] == token) or (
                            kind == "photo"
                            and job_id in state["views"].values()
                            and state["jobs"][job_id]["attempt"] == token
                            and state["jobs"][job_id]["status"] in PENDING
                        )
                        if state["status"] not in CLOSED and current:
                            state.update(status=DraftStatus.FAILED, error={"code": "WORKER_FAILED"})
                            if job_id and state["jobs"][job_id]["status"] in PENDING:
                                state["jobs"][job_id].update(
                                    status=PhotoTaskStatus.FAILED, error={"code": "WORKER_FAILED"}
                                )
                            self.repository.save(state)
                except Exception:
                    pass  # Exposed by health(); unreadable storage is never reported READY.
            finally:
                with self._condition:
                    self._release()
                self._queue.task_done()

    def health(self):
        with self.repository.lock:
            return {
                "pending_jobs": self._pending,
                "worker_alive": self._worker.is_alive(),
                "worker_errors": list(self.worker_errors),
            }

    def wait_idle(self, timeout=30):
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Jobs are still running; this does not cancel inference.")
                self._condition.wait(remaining)

    def close(self, timeout=30):
        with self.repository.lock:
            if not self._closing:
                self._closing = True
                self._queue.put(None)
        self._worker.join(timeout)
        if self._worker.is_alive():
            raise TimeoutError("Worker is still running; repository ownership was retained.")
        self.repository.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def create_draft_service(settings: Settings) -> DraftService:
    analysis = create_analysis_service(settings)
    repository = LocalDraftRepository(settings.draft_root)
    try:
        return DraftService(
            repository,
            analysis,
            ttl_seconds=settings.draft_ttl_seconds,
            terminal_retention_seconds=settings.draft_terminal_retention_seconds,
            max_pending_jobs=settings.draft_max_pending_jobs,
            queue_timeout_seconds=settings.draft_queue_timeout_seconds,
            processing_timeout_seconds=settings.draft_processing_timeout_seconds,
            max_attempts=settings.draft_max_attempts,
        )
    except Exception:
        repository.close()
        raise
