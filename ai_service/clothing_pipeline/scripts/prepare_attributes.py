"""Prepare small frozen text prototypes once on CPU; no fitting or image inference."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from gardirop_ai_clothing.config import get_settings
from gardirop_ai_clothing.embeddings.marqo import load_marqo_encoder
from gardirop_ai_clothing.labeling.attribute_bank import (
    ATTRIBUTE_VERSION,
    ENTRIES,
    PROMPTS,
    PROMPTS_SHA256,
    TOKENIZER_REPO,
    TOKENIZER_REVISION,
    load_bank,
)
from gardirop_ai_clothing.model_specs import MARQO_REVISION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    directory = settings.attribute_bank_dir
    if (directory / "metadata.json").exists() or args.check:
        _, metadata = load_bank(directory)
        print(
            json.dumps(
                {
                    "status": "ATTRIBUTES_READY",
                    "training_run": False,
                    "preparation_run": False,
                    "prototypes": len(ENTRIES),
                    "sha256": metadata["sha256"],
                },
                indent=2,
            )
        )
        return
    import torch
    from huggingface_hub import hf_hub_download

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    print(
        "Pinli küçük tokenizer dosyaları hazırlanıyor. Yeni görüntü modeli indirilmeyecek.",
        flush=True,
    )
    tokenizer_files = [
        Path(
            hf_hub_download(
                repo_id=TOKENIZER_REPO,
                revision=TOKENIZER_REVISION,
                filename=name,
                local_files_only=args.offline,
            )
        )
        for name in ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json")
    ]
    print(
        "Mevcut Marqo CPU'da açılıyor; 13 sabit metin bir kez encode edilecek. Eğitim yok.",
        flush=True,
    )
    encoder = load_marqo_encoder(settings.model_manifest_path, device="cpu")
    vectors = []
    for start in range(0, len(PROMPTS), 4):
        vectors.extend(encoder.text_runner(PROMPTS[start : start + 4], tokenizer_files[0].parent))
    vectors = np.asarray(vectors, dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    metadata = {
        "attribute_version": ATTRIBUTE_VERSION,
        "encoder_revision": MARQO_REVISION,
        "tokenizer_revision": TOKENIZER_REVISION,
        "prompts_sha256": PROMPTS_SHA256,
        "prompts": PROMPTS,
        "training_run": False,
        "text_encoding_device": "cpu",
        "tokenizer_files_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tokenizer_files
        },
        "limits": "Zero-shot suggestions with uncalibrated abstention thresholds; no measured attribute accuracy.",
    }
    directory.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=directory.parent) as temporary:
        temp = Path(temporary)
        np.savez_compressed(
            temp / "prototypes.npz",
            vectors=vectors,
            labels=np.array([f"{g}:{label}" for g, label, _ in ENTRIES]),
        )
        metadata["sha256"] = hashlib.sha256((temp / "prototypes.npz").read_bytes()).hexdigest()
        (temp / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        load_bank(temp)
        directory.mkdir(exist_ok=True)
        # Metadata is committed last. Interrupted preparation can be retried.
        os.replace(temp / "prototypes.npz", directory / "prototypes.npz")
        os.replace(temp / "metadata.json", directory / "metadata.json")
    print(
        json.dumps(
            {
                "status": "ATTRIBUTES_READY",
                "training_run": False,
                "image_inference": False,
                "text_prompts_encoded": len(PROMPTS),
                "runtime_attribute_gpu_inference": False,
                "sha256": metadata["sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
