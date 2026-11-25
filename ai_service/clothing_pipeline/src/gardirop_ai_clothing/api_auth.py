"""Shared backend-to-AI key; reject unauthorized bodies before multipart parsing."""

import os
import re
import secrets
import stat
from pathlib import Path
from typing import Annotated

from fastapi import HTTPException, Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import SecretStr
from starlette.datastructures import Headers

from gardirop_ai_clothing.config import Settings
from gardirop_ai_clothing.errors import ConfigurationError

KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]{32,256}\Z")
KEY_HEADER = APIKeyHeader(name="X-API-Key", scheme_name="ClothingServiceKey", auto_error=False)


def validate_key(value: str) -> SecretStr:
    if not KEY_PATTERN.fullmatch(value):
        raise ConfigurationError("API key must contain 32..256 URL-safe characters.")
    return SecretStr(value)


def read_key_file(path: Path) -> SecretStr:
    # Reject links and broad permissions rather than silently exposing a secret.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            raise ConfigurationError("Local API key must be a regular file with mode 0600.")
        if info.st_size > 257:
            raise ConfigurationError("Local API key file has invalid length.")
        value = os.read(descriptor, 258).decode("ascii").strip()
        return validate_key(value)
    finally:
        os.close(descriptor)


def load_api_key(settings: Settings) -> SecretStr:
    if settings.api_key is not None:
        return validate_key(settings.api_key.get_secret_value())
    try:
        return read_key_file(settings.api_key_file)
    except (OSError, UnicodeError) as exc:
        raise ConfigurationError(
            "API key is unavailable; run make api-key before make api."
        ) from exc


def auth_error(application, supplied):
    if not application.state.api_auth_required:
        return None
    expected = application.state.api_secret
    if expected is None:
        return 503, {"code": "SERVICE_NOT_READY", "message": "Service is not initialized."}
    if supplied is None or not secrets.compare_digest(
        expected.get_secret_value().encode("utf-8"), supplied.encode("utf-8")
    ):
        return 401, {"code": "UNAUTHORIZED", "message": "A valid X-API-Key is required."}
    return None


def require_api_key(
    request: Request,
    supplied: Annotated[str | None, Security(KEY_HEADER)] = None,
):
    """Also declares the header scheme for Swagger/OpenAPI clients."""
    error = auth_error(request.app, supplied)
    if error:
        status, detail = error
        raise HTTPException(status_code=status, detail=detail)


class ApiKeyMiddleware:
    def __init__(self, app, application):
        self.app, self.application = app, application

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/v1/"):
            error = auth_error(self.application, Headers(scope=scope).get("x-api-key"))
            if error:
                status, detail = error
                response = JSONResponse(
                    status_code=status,
                    content={"error": detail},
                    headers={"Cache-Control": "no-store"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
