"""Unit tests for application configuration."""

import pytest
from pydantic import ValidationError

from gardirop_ai_clothing import config as config_module
from gardirop_ai_clothing.config import (
    PROJECT_ROOT,
    Settings,
    get_settings,
)


def test_project_root_and_explicit_manifest_path():
    settings = Settings(
        _env_file=None,
        model_manifest_path=PROJECT_ROOT / "configs" / "model_manifest.yaml",
    )

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


@pytest.mark.parametrize(
    ("local_exists", "expected_name"),
    [
        (False, "model_manifest.yaml"),
        (True, "model_manifest.local.yaml"),
    ],
)
def test_default_manifest_selection(tmp_path, monkeypatch, local_exists, expected_name):
    monkeypatch.delenv("GARDROPAI_MODEL_MANIFEST_PATH", raising=False)
    monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)

    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "model_manifest.yaml").write_text("portable", encoding="utf-8")
    if local_exists:
        (configs / "model_manifest.local.yaml").write_text("local", encoding="utf-8")

    settings = Settings(_env_file=None)
    assert settings.model_manifest_path == configs / expected_name


def test_explicit_environment_manifest_overrides_local_default(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "model_manifest.local.yaml").write_text("local", encoding="utf-8")
    custom = tmp_path / "custom.yaml"
    custom.write_text("custom", encoding="utf-8")
    monkeypatch.setenv("GARDROPAI_MODEL_MANIFEST_PATH", str(custom))

    assert Settings(_env_file=None).model_manifest_path == custom
