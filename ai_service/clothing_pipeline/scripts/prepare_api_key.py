"""Create a private local service key without printing or replacing it."""

import os
import secrets

from gardirop_ai_clothing.api_auth import load_api_key, read_key_file
from gardirop_ai_clothing.config import PROJECT_ROOT, get_settings


def main():
    settings = get_settings()
    if settings.api_key is not None:
        load_api_key(settings)
        print("API anahtarı ortam ayarından sağlanıyor; dosya oluşturulmadı.")
        return
    path = settings.api_key_file
    if path.is_symlink() or not path.resolve().is_relative_to(PROJECT_ROOT.resolve()):
        raise SystemExit("Anahtar dosyası clothing_pipeline içinde olmalı; işlem yapılmadı.")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        read_key_file(path)
        print("Mevcut yerel anahtar geçerli; değiştirilmedi.")
    else:
        try:
            with os.fdopen(descriptor, "w", encoding="ascii") as stream:
                stream.write(secrets.token_urlsafe(32) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        print("Yerel servis anahtarı oluşturuldu (0600).")
    print(f"Dosya: {path}")
    print("Anahtar ekrana yazdırılmadı. Sunucu ve smoke-http aynı yerel ayarı kullanır.")


if __name__ == "__main__":
    main()
