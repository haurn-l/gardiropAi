"""Pinned Marqo text prototypes; runtime scoring needs only existing image vectors."""

import hashlib
import json
from pathlib import Path

import numpy as np

from gardirop_ai_clothing.errors import ModelArtifactError
from gardirop_ai_clothing.model_specs import MARQO_REVISION

ATTRIBUTE_VERSION = "clothing-attributes-v1"
TOKENIZER_REPO = "timm/ViT-B-16-SigLIP"
TOKENIZER_REVISION = "41f575766f40e752fdd1383e9565b7f02388c1c4"
DESCRIPTIONS = {
    "season": {
        "KIS": "warm winter clothing for cold weather",
        "YAZ": "lightweight summer clothing for hot weather",
        "SONBAHAR": "autumn clothing for cool fall weather",
        "ILKBAHAR": "spring clothing for mild weather",
        "HER_MEVSIM": "versatile all season clothing worn throughout the year",
    },
    "pattern": {
        "plain": "plain solid colored clothing without a pattern or graphic print",
        "graphic": "clothing with a large graphic print or illustration",
        "logo_text": "clothing with a visible printed logo, lettering or text",
        "striped": "clothing with a striped pattern",
        "checked": "clothing with a checkered plaid pattern",
        "floral": "clothing with a floral flower pattern",
        "dotted": "clothing with a polka dot pattern",
        "other_pattern": "clothing with an all over decorative pattern",
    },
}
ENTRIES = [
    (group, label, description)
    for group, labels in DESCRIPTIONS.items()
    for label, description in labels.items()
]
PROMPTS = [f"A product photo of {description}." for _, _, description in ENTRIES]
PROMPTS_SHA256 = hashlib.sha256(json.dumps(PROMPTS).encode()).hexdigest()


def load_bank(directory: str | Path):
    root = Path(directory)
    try:
        metadata = json.loads((root / "metadata.json").read_text())
        expected = {
            "attribute_version": ATTRIBUTE_VERSION,
            "encoder_revision": MARQO_REVISION,
            "tokenizer_revision": TOKENIZER_REVISION,
            "prompts_sha256": PROMPTS_SHA256,
        }
        if any(metadata.get(k) != v for k, v in expected.items()):
            raise ValueError("Attribute producer identity mismatch.")
        path = root / "prototypes.npz"
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
            raise ValueError("Attribute prototypes SHA256 mismatch.")
        with np.load(path, allow_pickle=False) as data:
            vectors = data["vectors"].copy()
            if data["labels"].tolist() != [f"{g}:{label}" for g, label, _ in ENTRIES]:
                raise ValueError("Attribute prototype order mismatch.")
        if vectors.shape != (len(ENTRIES), 768) or vectors.dtype != np.float32:
            raise ValueError("Attribute prototype shape/dtype mismatch.")
        if not np.isfinite(vectors).all() or not np.allclose(
            np.linalg.norm(vectors, axis=1), 1, atol=1e-5
        ):
            raise ValueError("Attribute prototypes must be finite unit vectors.")
        vectors.setflags(write=False)
        return vectors, metadata
    except (OSError, ValueError, KeyError) as exc:
        raise ModelArtifactError(
            "Etiket prototipleri eksik veya bozuk. make attributes-prepare çalıştır."
        ) from exc


def rank_group(vectors, front, back, group):
    indices = [i for i, (g, _, _) in enumerate(ENTRIES) if g == group]
    scores = np.stack([vectors[indices] @ front, vectors[indices] @ back])
    # Season is a pair-level visual suitability guess; any printed side counts.
    combined = scores.mean(axis=0) if group == "season" else scores.max(axis=0)
    order = sorted(range(len(indices)), key=lambda i: (-float(combined[i]), indices[i]))
    return [
        {
            "label": ENTRIES[indices[i]][1],
            "score": float(combined[i]),
            "front_score": float(scores[0, i]),
            "back_score": float(scores[1, i]),
            "score_kind": "cosine_similarity_not_probability",
        }
        for i in order
    ]
