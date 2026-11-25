"""User-run loopback HTTP smoke: two chosen photos, downloaded evidence, no training."""

import argparse
import hashlib
import html
import io
import json
import mimetypes
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

import numpy as np
from PIL import Image

from gardirop_ai_clothing.api_auth import load_api_key
from gardirop_ai_clothing.config import get_settings

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {"1": "UST_GIYIM", "2": "ALT_GIYIM", "3": "DIS_GIYIM"}


def choose_path(value, prompt):
    value = value or input(prompt).strip()
    if len(value) > 1 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("Fotoğraf normal bir dosya olmalı ve 20 MiB sınırını aşmamalı.")
    return path


def multipart(fields, image):
    boundary = f"gardropai-{uuid4().hex}"
    body = bytearray()
    for key, value in fields.items():
        body.extend(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        )
    mime = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    body.extend(
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="photo"\r\nContent-Type: {mime}\r\n\r\n'.encode()
    )
    body.extend(image.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def save_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8"
    )


def run(args, output, report):
    parts = urlsplit(args.url)
    if parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Bu test yalnız yerel HTTP sunucusuna fotoğraf gönderir.")
    if (
        parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
        or parts.username
        or parts.password
    ):
        raise ValueError("--url yalnız yerel sunucunun kök adresi olmalı.")
    base = args.url.rstrip("/")
    opener = build_opener(ProxyHandler({}))
    service_key = load_api_key(get_settings()).get_secret_value()

    def request(path, *, method="GET", body=None, headers=None, binary=False):
        if not path.startswith("/v1/clothing/") and path != "/health/live":
            raise ValueError("Beklenmeyen HTTP kaynak yolu.")
        req = Request(
            base + path,
            data=body,
            headers={"X-API-Key": service_key, **(headers or {})},
            method=method,
        )
        try:
            with opener.open(req, timeout=30) as response:
                data = response.read()
                return data if binary else json.loads(data)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {detail[:1500]}") from exc

    live = request("/health/live")
    if not live.get("photoProcessingAvailable"):
        raise RuntimeError("Fotoğraf işleyici bağlı değil. Yeni kodla make api sunucusunu başlat.")
    front = choose_path(args.front, "Ön fotoğrafın tam dosya yolu: ")
    back = choose_path(args.back, "Arka fotoğrafın tam dosya yolu: ")
    category = args.category
    if category is None:
        answer = input("Ana kategori [1: üst, 2: alt, 3: dış]: ").strip()
        category = CATEGORIES.get(answer, answer)
    if category not in CATEGORIES.values():
        raise ValueError("Ana kategori UST_GIYIM, ALT_GIYIM veya DIS_GIYIM olmalı.")
    print("Ön fotoğraf gönderiliyor; arka fotoğrafı beklemeden işlenecek.", flush=True)
    start = time.monotonic()
    body, content_type = multipart(
        {
            "category": category,
            "captureId": uuid4().hex,
            "manualRotation": args.front_rotation,
        },
        front,
    )
    created = request(
        "/v1/clothing/jobs",
        method="POST",
        body=body,
        headers={
            "Content-Type": content_type,
            "Idempotency-Key": uuid4().hex,
        },
    )
    save_json(output / "front_submission.json", created)
    report["jobId"] = created["jobId"]
    status_path = f"/v1/clothing/jobs/{created['jobId']}"
    if args.capture_gap:
        time.sleep(args.capture_gap)
    state = request(status_path)
    report["statusBeforeBack"] = state
    body, content_type = multipart(
        {
            "captureId": uuid4().hex,
            "expectedRevision": state["revision"],
            "manualRotation": args.back_rotation,
        },
        back,
    )
    print("Arka fotoğraf gönderiliyor...", flush=True)
    back_started = time.monotonic()
    submitted = request(
        f"{status_path}/views/BACK", method="PUT", body=body, headers={"Content-Type": content_type}
    )
    back_accepted = time.monotonic()
    save_json(output / "back_submission.json", submitted)
    deadline, last_status = time.monotonic() + 300, None
    while True:
        state = request(status_path)
        if state["status"] != last_status:
            print(f"İş durumu: {state['status']}", flush=True)
            last_status = state["status"]
        if state["status"] == "READY":
            break
        if state["status"] == "FAILED":
            save_json(output / "failed_job.json", state)
            raise RuntimeError(json.dumps(state.get("error"), ensure_ascii=False))
        if time.monotonic() >= deadline:
            raise TimeoutError("300 saniye içinde sonuç hazır olmadı; iş sunucuda devam edebilir.")
        time.sleep(0.5)
    ready_at = time.monotonic()
    result = request(state["resultUrl"])
    save_json(output / "result.json", result)
    report.update(revision=result["revision"], category=result["category"], tags=result["tags"])
    for view in ("FRONT", "BACK"):
        descriptor = result["images"][view]
        data = request(descriptor["url"], binary=True)
        if hashlib.sha256(data).hexdigest() != descriptor["sha256"]:
            raise ValueError(f"{view}: SHA256 uyuşmuyor.")
        if len(data) != descriptor["byteLength"]:
            raise ValueError(f"{view}: dosya boyutu uyuşmuyor.")
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if image.format != "WEBP" or image.mode != "RGB":
                raise ValueError(f"{view}: RGB WebP bekleniyordu.")
            if list(image.size) != [descriptor["width"], descriptor["height"]]:
                raise ValueError(f"{view}: görüntü boyutları uyuşmuyor.")
            corners = (
                (0, 0),
                (image.width - 1, 0),
                (0, image.height - 1),
                (image.width - 1, image.height - 1),
            )
            if any(image.getpixel(point) != (255, 255, 255) for point in corners):
                raise ValueError(f"{view}: beyaz zemin köşeleri doğrulanamadı.")
        (output / f"{view.lower()}.webp").write_bytes(data)
    embedding = request(result["embedding"]["url"])
    save_json(output / "embedding.json", embedding)
    vector = np.asarray(embedding["values"], dtype=np.float32)
    if vector.shape != (1536,) or not np.isfinite(vector).all():
        raise ValueError("Embedding 1536 sonlu değerden oluşmalı.")
    if embedding["viewOrder"] != ["FRONT", "BACK"] or embedding["dtype"] != "float32":
        raise ValueError("Embedding sırası veya veri türü uyuşmuyor.")
    if abs(float(np.linalg.norm(vector)) - 1) > 1e-3:
        raise ValueError("Birleşik embedding normu geçersiz.")
    for half in (vector[:768], vector[768:]):
        if abs(float(np.linalg.norm(half)) - 1 / np.sqrt(2)) > 1e-3:
            raise ValueError("Embedding yarımlarının normu geçersiz.")
    report.update(
        status="PASSED",
        embeddingDimension=1536,
        timingSeconds={
            "backRequestStartToReadyObserved": ready_at - back_started,
            "backAcceptedToReadyObserved": ready_at - back_accepted,
            "backAcceptedToAllDownloadsVerified": time.monotonic() - back_accepted,
            "totalObserved": time.monotonic() - start,
        },
        timingLimits="One run; includes 0.5-second polling. Not a throughput or optimization benchmark.",
        scope="HTTP/data integrity only. Inspect cleaning quality and tag correctness visually.",
    )
    details = html.escape(json.dumps(result, ensure_ascii=False, indent=2))
    page = (
        '<!doctype html><html lang="tr"><meta charset="utf-8"><title>GardropAI HTTP testi</title>'
        "<style>body{font:16px system-ui;max-width:1100px;margin:30px auto;padding:16px}"
        "figure{display:inline-block;width:44%;vertical-align:top}img{width:100%;background:white}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f4f6;padding:16px}</style>"
        "<h1>GardropAI HTTP testi</h1><p>Görsel kaliteyi ve önerilen etiketleri kontrol et.</p>"
        '<figure><img src="front.webp"><figcaption>Temizlenmiş ön</figcaption></figure>'
        '<figure><img src="back.webp"><figcaption>Temizlenmiş arka</figcaption></figure>'
        f"<h2>Etiketler ve model çıktıları</h2><pre>{details}</pre></html>"
    )
    (output / "report.html").write_text(page, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--front")
    parser.add_argument("--back")
    parser.add_argument("--category", choices=list(CATEGORIES.values()))
    parser.add_argument("--front-rotation", type=int, choices=[-90, 0, 90, 180], default=0)
    parser.add_argument("--back-rotation", type=int, choices=[-90, 0, 90, 180], default=0)
    parser.add_argument("--capture-gap", type=float, default=0)
    args = parser.parse_args()
    if not 0 <= args.capture_gap <= 60:
        parser.error("--capture-gap 0 ile 60 saniye arasında olmalı.")
    output = (
        ROOT
        / "outputs"
        / "http_smoke"
        / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8])
    )
    output.mkdir(parents=True, exist_ok=False)
    report = {"status": "FAILED", "trainingRun": False, "backendConnected": False}
    print(f"Sonuç klasörü: {output}", flush=True)
    try:
        run(args, output, report)
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        save_json(output / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASSED":
        raise SystemExit(1)
    print(f"Görsel inceleme raporu: {output / 'report.html'}")


if __name__ == "__main__":
    main()
