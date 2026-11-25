"""Check HTTP construction and public contracts without a server or neural models."""

import json

from fastapi.testclient import TestClient

from gardirop_ai_clothing.app import create_app


def main() -> None:
    with TestClient(
        create_app(api_key="unit-test-only-service-key-000000000000"),
        headers={"X-API-Key": "unit-test-only-service-key-000000000000"},
    ) as client:
        live = client.get("/health/live")
        live.raise_for_status()

        ready = client.get("/health/ready")
        assert ready.status_code == 503
        assert ready.json()["modelsWarmed"] is False

        taxonomy = client.get("/v1/clothing/taxonomy")
        taxonomy.raise_for_status()

        openapi = client.get("/openapi.json")
        openapi.raise_for_status()

        paths = openapi.json()["paths"]
        assert "post" in paths["/v1/clothing/jobs"]
        assert "put" in paths["/v1/clothing/jobs/{job_id}/views/{view}"]
        assert "get" in paths["/v1/clothing/jobs/{job_id}"]

        for route in (
            "/v1/clothing/jobs/{job_id}/results/{revision}",
            "/v1/clothing/jobs/{job_id}/results/{revision}/embedding",
            "/v1/clothing/jobs/{job_id}/results/{revision}/images/{view}",
        ):
            assert "get" in paths[route]

        assert "patch" in paths["/v1/clothing/jobs/{job_id}/category"]
        assert "post" in paths["/v1/clothing/jobs/{job_id}/retry"]
        assert "delete" in paths["/v1/clothing/jobs/{job_id}"]
        unauthorized = client.get("/v1/clothing/taxonomy", headers={"X-API-Key": "wrong"})
        assert unauthorized.status_code == 401
        assert (
            openapi.json()["components"]["securitySchemes"]["ClothingServiceKey"]["name"]
            == "X-API-Key"
        )

        data = taxonomy.json()
        assert live.json()["status"] == "ALIVE"
        assert live.json()["photoProcessingAvailable"] is False
        assert len(data["categories"]) == 3
        assert len(data["subCategories"]) == 20
        assert data["embeddingDimension"] == 1536
        assert [item["classId"] for item in data["subCategories"]] == list(range(20))

        report = {
            "status": "HTTP_READINESS_AND_COMPACT_STORAGE_READY",
            "scope": "Contract-only app: authenticated uploads/downloads and category/retry/cancel routes.",
            "photoProcessingAvailable": False,
            "neuralInference": False,
            "backendConnected": False,
            "apiKeyAuthenticationChecked": True,
            "readinessContractChecked": True,
            "mainCategories": len(data["categories"]),
            "subCategories": len(data["subCategories"]),
            "httpPaths": sorted(openapi.json()["paths"]),
            "launchCommand": "make api",
            "localUrl": "http://127.0.0.1:8001",
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
