"""Unit tests for lazy model loading and GPU coordination."""

import pytest

from gardirop_ai_clothing.errors import (
    ConfigurationError,
    InferenceError,
    ModelArtifactError,
)
from gardirop_ai_clothing.model_manager import ModelManager


def test_lazy_loading_and_cache():
    loaded = []

    def load_model():
        loaded.append("called")
        return object()

    manager = ModelManager({"test_model": load_model})

    assert manager.loaded_models == ()
    assert manager.registered_models == ("test_model",)
    assert loaded == []

    first = manager.get_model("test_model")
    second = manager.get_model("test_model")

    assert first is second
    assert loaded == ["called"]
    assert manager.loaded_models == ("test_model",)


def test_unknown_model_is_rejected():
    manager = ModelManager({})

    with pytest.raises(
        ModelArtifactError,
        match="not registered",
    ):
        manager.get_model("unknown")


def test_failed_loading_is_not_cached():
    calls = []

    def broken_loader():
        calls.append(1)
        raise RuntimeError("Simulated loading error")

    manager = ModelManager({"broken": broken_loader})

    for _ in range(2):
        with pytest.raises(
            ModelArtifactError,
            match="Failed to load",
        ):
            manager.get_model("broken")

    assert len(calls) == 2
    assert manager.loaded_models == ()


def test_none_model_is_rejected():
    manager = ModelManager({"empty": lambda: None})

    with pytest.raises(
        ModelArtifactError,
        match="returned None",
    ):
        manager.get_model("empty")


def test_gpu_slot_prevents_overlapping_jobs():
    manager = ModelManager(
        {},
        max_concurrent_gpu_jobs=1,
    )

    with manager.gpu_slot():
        with pytest.raises(
            InferenceError,
            match="No GPU execution slot",
        ):
            with manager.gpu_slot(timeout_seconds=0):
                pass


def test_gpu_slot_released_after_exception():
    manager = ModelManager(
        {},
        max_concurrent_gpu_jobs=1,
    )

    with pytest.raises(ValueError):
        with manager.gpu_slot():
            raise ValueError("Simulated inference error")

    # The previous failure must not keep the slot locked.
    with manager.gpu_slot(timeout_seconds=0):
        pass


@pytest.mark.parametrize(
    "invalid_limit",
    [0, -1, True, 1.5],
)
def test_invalid_gpu_job_limits(invalid_limit):
    with pytest.raises(ConfigurationError):
        ModelManager(
            {},
            max_concurrent_gpu_jobs=invalid_limit,
        )


def test_invalid_loader_is_rejected():
    with pytest.raises(ConfigurationError):
        ModelManager({"broken": None})


def test_gpu_slot_rejects_negative_timeout():
    manager = ModelManager({})

    with pytest.raises(ConfigurationError):
        with manager.gpu_slot(timeout_seconds=-1):
            pass
