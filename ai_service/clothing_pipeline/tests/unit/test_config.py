"""Unit tests for application configuration."""

import pytest
from pydantic import ValidationError

from gardirop_ai_clothing.config import (
    PROJECT_ROOT,
    Settings,
    get_settings,
)


def test_project_root_and_manifest_path():
    settings = Settings(_env_file=None)

    assert (PROJECT_ROOT / "pyproject.toml").is_file()
    assert settings.model_manifest_path == (PROJECT_ROOT / "configs" / "model_manifest.yaml")
    assert settings.model_manifest_path.is_file()
    assert settings.output_dir == PROJECT_ROOT / "outputs"


def test_default_settings(monkeypatch):
    monkeypatch.delenv("GARDROPAI_PORT", raising=False)
    monkeypatch.delenv(
        "GARDROPAI_MAX_CONCURRENT_GPU_JOBS",
        raising=False,
    )

    settings = Settings(_env_file=None)

    assert settings.port == 8001
    assert settings.max_concurrent_gpu_jobs == 1


def test_environment_variable_overrides_default(monkeypatch):
    monkeypatch.setenv("GARDROPAI_PORT", "8123")

    settings = Settings(_env_file=None)

    assert settings.port == 8123


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("port", 0),
        ("port", 70000),
        ("device", "tpu"),
        ("max_concurrent_gpu_jobs", 0),
        ("max_upload_mb", 0),
        ("max_image_pixels", 24_000_001),
        ("image_padding", -1),
        ("image_square_margin_fraction", 0.6),
        ("draft_ttl_seconds", 0),
        ("draft_max_pending_jobs", 0),
        ("draft_queue_timeout_seconds", float("nan")),
        ("draft_max_attempts", 0),
    ],
)
def test_invalid_configuration_is_rejected(
    field,
    invalid_value,
):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            **{field: invalid_value},
        )


def test_settings_are_cached():
    get_settings.cache_clear()

    try:
        first = get_settings()
        second = get_settings()

        assert first is second
    finally:
        get_settings.cache_clear()
