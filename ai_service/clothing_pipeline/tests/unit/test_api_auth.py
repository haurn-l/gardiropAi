"""Key loading and authorization before any job/body processing."""

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from gardirop_ai_clothing.api_auth import (
    ApiKeyMiddleware,
    load_api_key,
    read_key_file,
    validate_key,
)
from gardirop_ai_clothing.app import create_app
from gardirop_ai_clothing.config import Settings
from gardirop_ai_clothing.errors import ConfigurationError

KEY = "unit-test-only-service-key-000000000000"


@pytest.mark.parametrize("value", ["short", "x" * 257, "a" * 32 + "\n", "ü" * 32])
def test_invalid_keys_fail_without_echoing_the_value(value):
    with pytest.raises(ConfigurationError) as error:
        validate_key(value)
    assert value not in str(error.value)


def test_secret_is_masked_and_explicit_setting_overrides_file(tmp_path):
    settings = Settings(api_key=KEY, api_key_file=tmp_path / "missing")
    assert load_api_key(settings).get_secret_value() == KEY
    assert KEY not in repr(settings)


def test_private_file_loads_but_public_permissions_and_symlinks_fail(tmp_path):
    target = tmp_path / "key.local"
    target.write_text(KEY + "\n")
    target.chmod(0o600)
    assert read_key_file(target).get_secret_value() == KEY
    target.chmod(0o644)
    with pytest.raises(ConfigurationError):
        read_key_file(target)
    target.chmod(0o600)
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(OSError):
        read_key_file(link)


def test_key_preparation_is_private_idempotent_and_never_prints_key(tmp_path, monkeypatch, capsys):
    script = Path(__file__).resolve().parents[2] / "scripts" / "prepare_api_key.py"
    spec = importlib.util.spec_from_file_location("prepare_api_key_unit", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / "configs" / "api_key.local"
    settings = Settings(api_key=None, api_key_file=target)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    module.main()
    secret = read_key_file(target).get_secret_value()
    assert len(secret) >= 32 and target.stat().st_mode & 0o777 == 0o600
    assert secret not in capsys.readouterr().out
    module.main()
    assert read_key_file(target).get_secret_value() == secret
    assert secret not in capsys.readouterr().out


def test_processing_startup_without_key_fails_before_worker_creation(tmp_path):
    called = []
    settings = Settings(api_key=None, api_key_file=tmp_path / "missing")
    app = create_app(
        processing_enabled=True, settings=settings, service_factory=lambda _: called.append(True)
    )
    with pytest.raises(ConfigurationError):
        with TestClient(app):
            pass
    assert called == []


@pytest.mark.parametrize("header", [None, "wrong", "ş" * 32])
def test_protected_endpoints_reject_invalid_key(header):
    with TestClient(create_app(api_key=KEY)) as client:
        # HTTPX headers are ASCII; non-ASCII supplied bytes exercise server handling.
        headers = {} if header is None else {b"X-API-Key": header.encode("utf-8")}
        response = client.get("/v1/clothing/taxonomy", headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
        assert KEY not in response.text
        assert client.get("/health/live").status_code == 200
        assert client.get("/docs").status_code == 200


def test_valid_key_allows_taxonomy_and_is_documented_in_openapi():
    with TestClient(create_app(api_key=KEY), headers={"X-API-Key": KEY}) as client:
        assert client.get("/v1/clothing/taxonomy").status_code == 200
        schema = client.get("/openapi.json").json()
        security = schema["components"]["securitySchemes"]["ClothingServiceKey"]
        assert security == {"type": "apiKey", "in": "header", "name": "X-API-Key"}
        for path, operations in schema["paths"].items():
            if path.startswith("/v1/"):
                for operation in operations.values():
                    assert {"ClothingServiceKey": []} in operation["security"]


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/v1/clothing/jobs"),
        ("put", "/v1/clothing/jobs/missing/views/BACK"),
        ("get", "/v1/clothing/jobs/missing"),
        ("get", "/v1/clothing/jobs/missing/results/3"),
        ("get", "/v1/clothing/jobs/missing/results/3/embedding"),
        ("get", "/v1/clothing/jobs/missing/results/3/images/FRONT"),
        ("patch", "/v1/clothing/jobs/missing/category"),
        ("post", "/v1/clothing/jobs/missing/retry"),
        ("delete", "/v1/clothing/jobs/missing"),
    ],
)
def test_missing_key_protects_all_photo_routes(method, path):
    with TestClient(create_app(api_key=KEY)) as client:
        assert client.request(method, path).status_code == 401


def test_unauthorized_upload_never_reads_request_body():
    messages = []

    async def forbidden(*args):
        raise AssertionError("Unauthorized request must not enter the app or read its body.")

    async def send(message):
        messages.append(message)

    application = SimpleNamespace(
        state=SimpleNamespace(api_auth_required=True, api_secret=validate_key(KEY))
    )
    middleware = ApiKeyMiddleware(forbidden, application)
    scope = {"type": "http", "path": "/v1/clothing/jobs", "headers": [], "method": "POST"}
    asyncio.run(middleware(scope, forbidden, send))
    assert messages[0]["status"] == 401
