"""Lazy model loading and GPU execution coordination."""

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from threading import BoundedSemaphore, RLock

from gardirop_ai_clothing.errors import (
    ConfigurationError,
    InferenceError,
    ModelArtifactError,
)

ModelLoader = Callable[[], object]


class ModelManager:
    """
    Coordinate model loading and GPU execution.

    Models are loaded only on first access and cached.

    Loader functions must be registered only after their
    checkpoint artifacts have been verified.

    GPU execution is limited through a semaphore.
    """

    def __init__(
        self,
        loaders: Mapping[str, ModelLoader],
        *,
        max_concurrent_gpu_jobs: int = 1,
    ) -> None:
        if (
            isinstance(max_concurrent_gpu_jobs, bool)
            or not isinstance(max_concurrent_gpu_jobs, int)
            or max_concurrent_gpu_jobs < 1
        ):
            raise ConfigurationError("max_concurrent_gpu_jobs must be a positive integer.")

        if any(
            not isinstance(name, str) or not name.strip() or not callable(loader)
            for name, loader in loaders.items()
        ):
            raise ConfigurationError(
                "Model loaders must have valid names and callable loader functions."
            )

        self._loaders = dict(loaders)
        self._models: dict[str, object] = {}

        # Prevent concurrent duplicate initialization.
        self._load_lock = RLock()

        # Limit simultaneous GPU operations.
        self._gpu_semaphore = BoundedSemaphore(max_concurrent_gpu_jobs)

    @property
    def registered_models(self) -> tuple[str, ...]:
        """Return names of available model loaders."""
        return tuple(sorted(self._loaders))

    @property
    def loaded_models(self) -> tuple[str, ...]:
        """Return names of models already in memory."""
        with self._load_lock:
            return tuple(sorted(self._models))

    def get_model(self, name: str) -> object:
        """
        Load a registered model once and reuse it.

        A failed load is not cached, allowing a later retry.
        """
        with self._load_lock:
            if name not in self._loaders:
                raise ModelArtifactError(f"Model is not registered: {name}")

            if name in self._models:
                return self._models[name]

            try:
                model = self._loaders[name]()
            except Exception as exc:
                raise ModelArtifactError(f"Failed to load model: {name}") from exc

            if model is None:
                raise ModelArtifactError(f"Model loader returned None: {name}")

            self._models[name] = model
            return model

    @contextmanager
    def gpu_slot(
        self,
        *,
        timeout_seconds: float | None = None,
    ) -> Iterator[None]:
        """
        Reserve one inference execution slot.

        The slot is released even if inference raises an error.

        This is a synchronous context manager. Async API code
        must execute blocking inference in an appropriate
        worker thread rather than blocking the event loop.
        """
        if timeout_seconds is not None and timeout_seconds < 0:
            raise ConfigurationError("GPU slot timeout cannot be negative.")

        acquired = self._gpu_semaphore.acquire(timeout=timeout_seconds)

        if not acquired:
            raise InferenceError("No GPU execution slot is available.")

        try:
            yield
        finally:
            self._gpu_semaphore.release()
