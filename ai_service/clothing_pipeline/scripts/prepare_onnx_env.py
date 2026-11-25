"""Isolated ONNX overlay; the existing application packages are reused read-only."""

import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import venv
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_ROOT = ROOT / ".venv-onnx"
PACKAGES = ("onnx==1.23.2", "onnxscript==0.7.2", "onnxruntime-gpu==1.30.0")


def inventory():
    result = {}
    for dist in importlib.metadata.distributions():
        name = re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower()
        if name in result and result[name] != dist.version:
            raise ValueError(f"Conflicting base distributions: {name}")
        result[name] = dist.version
    return result


def main():
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise SystemExit("Run through the project environment: make onnx-env.")
    output = ROOT / "outputs/onnx_environment"
    if ENV_ROOT.is_symlink() or not ENV_ROOT.resolve().is_relative_to(ROOT):
        raise SystemExit("Unsafe overlay path.")
    if not output.resolve().is_relative_to(ROOT):
        raise SystemExit("Unsafe report path.")
    output.mkdir(parents=True, exist_ok=True)
    state_path = output / "state.json"
    base = inventory()
    base_site = Path(sysconfig.get_path("purelib")).resolve()
    if not base_site.is_relative_to((ROOT / ".venv").resolve()):
        raise SystemExit("Unexpected base site-packages path.")
    state = {
        "status": "FAILED",
        "base_versions": base,
        "requested": list(PACKAGES),
        "base_python": sys.executable,
        "base_site": str(base_site),
        "environment": str(ENV_ROOT),
        "training_run": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    if ENV_ROOT.exists():
        old = json.loads(state_path.read_text()) if state_path.is_file() else {}
        if old.get("base_site") != str(base_site) or old.get("requested") != list(PACKAGES):
            raise SystemExit("Unrecognized .venv-onnx; it was not modified.")
        if old.get("base_versions") != base:
            raise SystemExit("Base packages changed since overlay creation; send this output.")
    else:
        print("Ayrı .venv-onnx oluşturuluyor (ensurepip kullanılmıyor)...", flush=True)
        venv.EnvBuilder(with_pip=False).create(ENV_ROOT)
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    python = ENV_ROOT / "bin/python"
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("UV_") or key.startswith("PIP_"):
            del env[key]
    (output / "tmp").mkdir(exist_ok=True)
    env.update(
        TMPDIR=str(output / "tmp"),
        UV_CACHE_DIR=str(output / "cache"),
        UV_PYTHON_DOWNLOADS="never",
        PYTHONDONTWRITEBYTECODE="1",
    )
    try:
        purelib = subprocess.check_output(
            [str(python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
            text=True,
            env=env,
        ).strip()
        site = Path(purelib).resolve()
        if not site.is_relative_to(ENV_ROOT):
            raise ValueError("Overlay site-packages escaped its environment.")
        (site / "gardiropai_base.pth").write_text(str(base_site) + "\n")
        constraints = output / "base_constraints.txt"
        constraints.write_text(
            "".join(
                f"{name}=={version}\n"
                for name, version in sorted(base.items())
                if name != "gardirop-ai-clothing"
            )
        )
        requested = output / "requirements.in"
        requested.write_text("\n".join(PACKAGES) + "\n")
        lock = output / "requirements.lock.txt"
        uv = shutil.which("uv")
        if not uv:
            raise ValueError("uv executable not found.")
        command = [
            uv,
            "pip",
            "compile",
            str(requested),
            "--constraints",
            str(constraints),
            "--output-file",
            str(lock),
            "--generate-hashes",
            "--no-header",
            "--no-annotate",
            "--only-binary",
            ":all:",
            "--python",
            sys.executable,
            "--default-index",
            "https://pypi.org/simple",
            "--no-sources",
        ]
        # Base constraints still participate in resolution, but their packages
        # are omitted from installation and remain visible via the .pth file.
        requested_names = {value.split("==")[0] for value in PACKAGES}
        for name in sorted(base):
            if name not in requested_names:
                command.extend(["--no-emit-package", name])
        print("ONNX paketleri sürüm/hash kilidiyle çözülüyor...", flush=True)
        subprocess.run(command, cwd=output, env=env, check=True)
        state["requirements_lock_sha256"] = hashlib.sha256(lock.read_bytes()).hexdigest()
        print("Paketler yalnız .venv-onnx içine kuruluyor...", flush=True)
        subprocess.run(
            [
                uv,
                "pip",
                "install",
                "--python",
                str(python),
                "--no-deps",
                "--require-hashes",
                "--only-binary",
                ":all:",
                "--requirements",
                str(lock),
                "--default-index",
                "https://pypi.org/simple",
            ],
            cwd=output,
            env=env,
            check=True,
        )
        probe = """
import importlib.metadata as m, json, sys, torch, onnx, onnxscript, onnxruntime as ort
from pathlib import Path
assert Path(sys.prefix).resolve() == Path(sys.argv[1]).resolve()
assert Path(torch.__file__).resolve().is_relative_to(Path(sys.argv[2]))
print(json.dumps({"prefix": sys.prefix, "torch_file": torch.__file__,
 "torch": torch.__version__, "cuda_runtime": torch.version.cuda,
 "cuda_available": torch.cuda.is_available(),
 "packages": {p: m.version(p) for p in ("onnx", "onnxscript", "onnxruntime-gpu")},
 "providers": ort.get_available_providers()}))
"""
        checked = subprocess.check_output(
            [str(python), "-c", probe, str(ENV_ROOT), str(base_site)],
            cwd=output,
            env=env,
            text=True,
        )
        details = json.loads(checked.strip().splitlines()[-1])
        if details["torch"] != base["torch"] or details["cuda_runtime"] != "13.0":
            raise ValueError("Expected unchanged CUDA 13 PyTorch runtime.")
        if not details["cuda_available"] or "CUDAExecutionProvider" not in details["providers"]:
            raise ValueError("CUDA unavailable in the overlay.")
        if base != inventory():
            raise ValueError("Base environment inventory unexpectedly changed.")
        state.update(status="READY", details=details, base_environment_unchanged=True)
    except Exception as exc:
        state["error"] = str(exc)
        raise
    finally:
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        print(f"ONNX ortam raporu: {state_path}", flush=True)
    print(
        json.dumps(
            {"status": state["status"], **state["details"], "base_environment_unchanged": True},
            indent=2,
        )
    )
    print("Model yüklenmedi/indirilmedi; export, çıkarım ve TensorRT derlemesi yapılmadı.")


if __name__ == "__main__":
    main()
