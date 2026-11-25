"""Download pinned files into the HF cache, then atomically update readiness."""

import argparse
import copy
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import yaml

from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256
from gardirop_ai_clothing.model_manifest import load_manifest, verify_manifest
from gardirop_ai_clothing.model_specs import ENCODERS, PARENT_HEAD_NAME, PARENT_HEAD_SHA256

ROOT = Path(__file__).resolve().parents[1]


def prepare(
    path: Path,
    *,
    offline: bool = False,
    downloader=None,
    output_path: Path | None = None,
) -> list[str]:
    destination = output_path if output_path is not None else path
    if destination.resolve().parent != path.resolve().parent:
        raise ValueError("Output manifest must share the source configs directory.")
    data = copy.deepcopy(load_manifest(path))
    head = data["models"][PARENT_HEAD_NAME]
    declared_weights = next((e for e in head["artifacts"] if e["name"] == "weights"), None)
    if declared_weights is None or declared_weights["sha256"] != PARENT_HEAD_SHA256:
        raise ValueError("Selected research parent LR weights are not installed.")
    # Check all existing ready entries before downloading anything.
    verify_manifest(path)
    if downloader is None:
        from huggingface_hub import hf_hub_download

        downloader = hf_hub_download
    for name, spec in ENCODERS.items():
        entries = []
        for filename in spec["files"]:
            local = Path(
                downloader(
                    repo_id=spec["repo_id"],
                    filename=filename,
                    revision=spec["revision"],
                    local_files_only=offline,
                )
            )
            entries.append(
                {"name": filename, "path": str(local.absolute()), "sha256": file_sha256(local)}
            )
        data["models"][name]["artifacts"] = entries
        data["models"][name]["status"] = "ready"
    # Temporary manifest stays under configs so relative artifact paths retain meaning.
    temp_path = None
    try:
        with NamedTemporaryFile(
            mode="w", dir=destination.parent, suffix=".yaml", delete=False
        ) as stream:
            temp_path = Path(stream.name)
            yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)
        states = verify_manifest(temp_path, require_ready=True)
        os.replace(temp_path, destination)
        return states
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "configs/model_manifest.yaml")
    parser.add_argument("--output-manifest", type=Path)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    destination = args.output_manifest or args.manifest.with_name("model_manifest.local.yaml")
    for state in prepare(
        args.manifest,
        offline=args.offline,
        output_path=destination,
    ):
        print(state)
    print(f"Local manifest: {destination}")
    print("Pinned model files verified. No inference or training was performed.")


if __name__ == "__main__":
    main()
