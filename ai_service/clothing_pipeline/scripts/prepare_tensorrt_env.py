"""Isolated native TensorRT overlay; base and ONNX packages are reused read-only."""

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

from gardirop_ai_clothing.tensorrt_experiment import TRT_PACKAGES

ROOT = Path(__file__).resolve().parents[1]
ENV_ROOT = ROOT / ".venv-trt"
PACKAGES = TRT_PACKAGES


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
        raise SystemExit("Run through the project environment: make tensorrt-env.")
    output = ROOT / "outputs/tensorrt_environment"
    if ENV_ROOT.is_symlink() or not ENV_ROOT.resolve().is_relative_to(ROOT):
        raise SystemExit("Unsafe overlay path.")
    if not output.resolve().is_relative_to(ROOT):
        raise SystemExit("Unsafe report path.")
    output.mkdir(parents=True, exist_ok=True)
    state_path = output / "state.json"
    onnx_state_path = ROOT / "outputs/onnx_environment/state.json"
    onnx_state = json.loads(onnx_state_path.read_text())
    if onnx_state.get("status") != "READY":
        raise SystemExit("The prepared ONNX overlay is required first.")
    onnx_site = (
        ROOT
        / ".venv-onnx"
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    if not onnx_site.is_dir() or not onnx_site.resolve().is_relative_to(ROOT):
        raise SystemExit("Unexpected ONNX overlay site-packages.")
    overlay_versions = json.loads(
        subprocess.check_output(
            [
                str(ROOT / ".venv-onnx/bin/python"),
                "-c",
                "import importlib.metadata as m,json,re; print(json.dumps({re.sub(r'[-_.]+','-',d.metadata['Name']).lower():d.version for d in m.distributions()}))",
            ],
            text=True,
        )
    )
    base = inventory()
    constraints_versions = dict(base)
    for name, version in overlay_versions.items():
        if name in constraints_versions and constraints_versions[name] != version:
            raise SystemExit(f"Base/ONNX overlay version conflict: {name}")
        constraints_versions[name] = version
    base_site = Path(sysconfig.get_path("purelib")).resolve()
    if not base_site.is_relative_to((ROOT / ".venv").resolve()):
        raise SystemExit("Unexpected base site-packages path.")
    state = {
        "status": "FAILED",
        "base_versions": base,
        "requested": list(PACKAGES),
        "base_python": sys.executable,
        "onnx_overlay_versions": overlay_versions,
        "base_site": str(base_site),
        "environment": str(ENV_ROOT),
        "training_run": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    if ENV_ROOT.exists():
        old = json.loads(state_path.read_text()) if state_path.is_file() else {}
        if old.get("base_site") != str(base_site) or old.get("requested") != list(PACKAGES):
            raise SystemExit("Unrecognized .venv-trt; it was not modified.")
        if old.get("onnx_overlay_versions") != overlay_versions:
            raise SystemExit(
                "ONNX overlay packages changed since TensorRT overlay creation; send this output."
            )
        if old.get("base_versions") != base:
            raise SystemExit("Base packages changed since overlay creation; send this output.")
    else:
        print("Ayrı .venv-trt oluşturuluyor (ensurepip kullanılmıyor)...", flush=True)
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
        (site / "gardiropai_base.pth").write_text(
            str(onnx_site.resolve()) + "\n" + str(base_site) + "\n"
        )
        constraints = output / "base_constraints.txt"
        constraints.write_text(
            "".join(
                f"{name}=={version}\n"
                for name, version in sorted(constraints_versions.items())
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
            "--index",
            "https://pypi.nvidia.com",
            "--default-index",
            "https://pypi.org/simple",
            "--no-sources",
        ]
        # Base constraints still participate in resolution, but their packages
        # are omitted from installation and remain visible via the .pth file.
        requested_names = {value.split("==")[0] for value in PACKAGES}
        for name in sorted(constraints_versions):
            if name not in requested_names:
                command.extend(["--no-emit-package", name])
        print("TensorRT paketleri sürüm/hash kilidiyle çözülüyor...", flush=True)
        subprocess.run(command, cwd=output, env=env, check=True)
        state["requirements_lock_sha256"] = hashlib.sha256(lock.read_bytes()).hexdigest()
        print("Paketler yalnız .venv-trt içine kuruluyor...", flush=True)
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
                "--index",
                "https://pypi.nvidia.com",
                "--default-index",
                "https://pypi.org/simple",
            ],
            cwd=output,
            env=env,
            check=True,
        )
        probe = """
import importlib.metadata as m,json,sys,torch,onnx
from pathlib import Path
import tensorrt_bindings as trt
assert Path(sys.prefix).resolve() == Path(sys.argv[1]).resolve()
assert Path(torch.__file__).resolve().is_relative_to(Path(sys.argv[2]))
assert Path(trt.__file__).resolve().is_relative_to(Path(sys.argv[1]))
logger = trt.Logger(trt.Logger.WARNING)
builder = trt.Builder(logger)
assert builder is not None
print(json.dumps({"prefix": sys.prefix, "torch_file": torch.__file__,
 "torch": torch.__version__, "cuda_runtime": torch.version.cuda,
 "cuda_available": torch.cuda.is_available(), "tensorrt_version": trt.__version__,
 "packages": {p:m.version(p) for p in ("tensorrt-cu13-bindings","tensorrt-cu13-libs")},
 "binding_module": "tensorrt_bindings", "builder_created": True}))
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
        if details["packages"] != {
            value.split("==")[0]: value.split("==")[1] for value in PACKAGES
        }:
            raise ValueError("TensorRT package versions differ from the pinned experiment.")
        if not details["cuda_available"] or not details["builder_created"]:
            raise ValueError("CUDA unavailable in the overlay.")
        if base != inventory():
            raise ValueError("Base environment inventory unexpectedly changed.")
        state.update(status="READY", details=details, base_environment_unchanged=True)
    except Exception as exc:
        state["error"] = str(exc)
        raise
    finally:
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        print(f"TensorRT ortam raporu: {state_path}", flush=True)
    print(
        json.dumps(
            {"status": state["status"], **state["details"], "base_environment_unchanged": True},
            indent=2,
        )
    )
    print(
        "TensorRT Builder doğrulandı. Model yüklenmedi; motor derlenmedi; ana ortam değiştirilmedi."
    )


if __name__ == "__main__":
    main()
