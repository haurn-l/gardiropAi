"""Application-specific errors for the clothing AI pipeline."""


class ClothingPipelineError(Exception):
    """Base error for expected pipeline failures."""

    code = "PIPELINE_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigurationError(ClothingPipelineError):
    """Invalid or incomplete application configuration."""

    code = "CONFIGURATION_ERROR"


class ModelArtifactError(ClothingPipelineError):
    """Missing, corrupted or incompatible model artifact."""

    code = "MODEL_ARTIFACT_ERROR"


class ImageProcessingError(ClothingPipelineError):
    """Failure while decoding or processing a clothing image."""

    code = "IMAGE_PROCESSING_ERROR"


class InferenceError(ClothingPipelineError):
    """Model inference failed."""

    code = "INFERENCE_ERROR"


class DraftConflictError(ClothingPipelineError):
    """An outdated revision, closed draft or conflicting idempotency token."""

    code = "DRAFT_CONFLICT"


class DraftNotFoundError(ClothingPipelineError):
    code = "DRAFT_NOT_FOUND"


class JobQueueFullError(ClothingPipelineError):
    code = "JOB_QUEUE_FULL"


class LocalStorageError(ClothingPipelineError):
    code = "LOCAL_STORAGE_ERROR"
