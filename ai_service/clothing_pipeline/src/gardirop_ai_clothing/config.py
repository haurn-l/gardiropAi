"""
GardropAI Clothing Pipeline
Central application configuration.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Root directory of ai_service/clothing_pipeline
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def default_model_manifest_path() -> Path:
    """Prefer local readiness without storing machine paths in Git."""
    local = PROJECT_ROOT / "configs" / "model_manifest.local.yaml"
    if local.is_file():
        return local
    return PROJECT_ROOT / "configs" / "model_manifest.yaml"


class Settings(BaseSettings):
    """Configuration shared across the clothing AI service."""

    model_config = SettingsConfigDict(
        env_prefix="GARDROPAI_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "GardropAI Clothing Pipeline"
    environment: Literal["development", "test", "production"] = "development"

    # HTTP service
    host: str = "127.0.0.1"
    port: int = Field(default=8001, ge=1, le=65535)

    api_key: SecretStr | None = None
    api_key_file: Path = PROJECT_ROOT / "configs" / "api_key.local"

    api_compact_storage: bool = True
    api_preload_models: bool = True
    api_release_warmup_cache: bool = False
    draft_storage_profile: Literal["full", "compact"] = "full"

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # GPU / inference
    device: Literal["auto", "cpu", "cuda"] = "auto"
    # Auto selects the accepted mixed FP16 policy on CUDA; CPU remains FP32.
    marqo_precision: Literal["auto", "fp32", "fp16"] = "auto"
    max_concurrent_gpu_jobs: int = Field(
        default=1,
        ge=1,
    )

    # Explicit opt-in: the standard API keeps the accepted PyTorch FP16 path.
    segmentation_backend: Literal["pytorch", "tensorrt"] = "pytorch"
    tensorrt_run: Path | None = None

    # Input limits
    max_upload_mb: int = Field(
        default=20,
        ge=1,
        le=100,
    )
    max_image_pixels: int = Field(default=24_000_000, ge=1, le=24_000_000)

    # Shared production image defaults; no dataset-specific fixed rotation.
    image_use_cleanup: bool = False
    image_auto_align: bool = False
    image_padding: int = Field(default=16, ge=0, le=512)
    image_square_margin_fraction: float = Field(default=0.10, ge=0, le=0.5)

    # Local paths
    model_manifest_path: Path = Field(default_factory=default_model_manifest_path)

    output_dir: Path = PROJECT_ROOT / "outputs"

    # One local worker; no Redis/Celery/backend required.
    draft_root: Path = PROJECT_ROOT / "outputs" / "draft_store"
    api_draft_root: Path = PROJECT_ROOT / "outputs" / "api_draft_store"
    draft_ttl_seconds: int = Field(default=3600, ge=1)
    draft_terminal_retention_seconds: int = Field(default=300, ge=0)
    draft_max_pending_jobs: int = Field(default=8, ge=1, le=64)
    draft_queue_timeout_seconds: float = Field(default=120, gt=0, allow_inf_nan=False)
    draft_processing_timeout_seconds: float = Field(default=120, gt=0, allow_inf_nan=False)
    draft_max_attempts: int = Field(default=3, ge=1, le=10)

    # Frozen text prototypes are prepared once; online inference remains offline.
    attribute_bank_dir: Path = PROJECT_ROOT / "models" / "attributes"

    # Loopback-only local demo; confirmed downloads are separate from raw uploads.
    demo_port: int = Field(default=7861, ge=1024, le=65535)
    demo_export_dir: Path = PROJECT_ROOT / "outputs" / "confirmed_exports"


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
