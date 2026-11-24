"""Inspect file readiness only; no model inference or downloads."""

import argparse
import sys
from pathlib import Path

from gardirop_ai_clothing.errors import ConfigurationError, ModelArtifactError
from gardirop_ai_clothing.model_manifest import verify_manifest

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "configs/model_manifest.yaml"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    try:
        states = verify_manifest(args.manifest, require_ready=args.require_ready)
    except (ConfigurationError, ModelArtifactError, OSError, ValueError) as exc:
        print(f"CHECK FAILED: {exc}", file=sys.stderr)
        return 1
    print("Manifest structure: VALID")
    for state in states:
        print(state)
    complete = all(state.startswith("READY:") for state in states)
    print("Model readiness:", "VERIFIED" if complete else "INCOMPLETE")
    print("Readiness scope: artifact files only; inference/service not verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
