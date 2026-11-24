"""Pinned identities for the selected models; no model loading."""

from gardirop_ai_clothing.contracts import (
    EMBEDDING_DIMENSION,
    FUSION_METHOD,
    NUM_CLASSES,
    TAXONOMY_VERSION,
    VIEW_EMBEDDING_DIMENSION,
    VIEW_ORDER,
)

MARQO_IMAGE_SIZE = 224
MARQO_CONFIG_SHA256 = "bf024fad1091ed3280e48f8ff2dcdf68785abaa56dad02588c0feed1a6529c42"
MARQO_REVISION = "c56244cc94f92419e8369fa71efdaf403b124ce8"
BIREFNET_REVISION = "280306042f57b7a33854319da62fd86aaa89ec4c"
BIREFNET_MODEL_NAME = "birefnet_dynamic"
BIREFNET_REPO = "ZhengPeng7/BiRefNet_dynamic"
SEGMENTATION_PROFILE = "birefnet-dynamic-aspect1024-m64-min256-white-v1"
BIREFNET_FILE_SHA256 = {
    "config.json": "557f461de22ede5b0a2ff60967e579180194ded47587f6e30a3a09ad08ae248b",
    "BiRefNet_config.py": "e7b8c2a74f6cea6a59553d517f71d47f2c1d90e670a13416af17c25fe2f3dc52",
    "birefnet.py": "2a45b4e0ece72d7c4212bca1a988e7d7e52bfe9f98ec59c58b8809c8a8b7a831",
    "model.safetensors": "e3d2e4884e51ff30f0cd630edc6b1e41b06b7f23a0a2a5169f7b7cb33a711c2d",
}
PARENT_HEAD_NAME = "marqo_parent_lr"
PARENT_HEAD_SHA256 = "5546b1bcb3e9676ca3e55099626ffba8b1b567c1cbec8af43031fcab064afe40"

ENCODERS = {
    BIREFNET_MODEL_NAME: {
        "role": "segmentation",
        "repo_id": BIREFNET_REPO,
        "revision": BIREFNET_REVISION,
        "files": ("config.json", "BiRefNet_config.py", "birefnet.py", "model.safetensors"),
        "weight_sha256": BIREFNET_FILE_SHA256["model.safetensors"],
        "files_sha256": BIREFNET_FILE_SHA256,
    },
    "marqo_fashionsiglip": {
        "role": "embedding",
        "repo_id": "Marqo/marqo-fashionSigLIP",
        "revision": MARQO_REVISION,
        "files": ("open_clip_config.json", "open_clip_model.safetensors"),
        "weight_sha256": "88908200434959fa3154ef79d408aac33341e8797fe5ca8ca6f0463aab32e6b3",
    },
}

PIPELINE_CONTRACT = {
    "segmentation_model": BIREFNET_MODEL_NAME,
    "segmentation_preprocessing": SEGMENTATION_PROFILE,
    "embedding_dimension_per_view": VIEW_EMBEDDING_DIMENSION,
    "combined_embedding_dimension": EMBEDDING_DIMENSION,
    "subcategory_count": NUM_CLASSES,
    "taxonomy_version": TAXONOMY_VERSION,
    "view_order": list(VIEW_ORDER),
    "fusion_method": FUSION_METHOD,
    "classifier_input_dimension": EMBEDDING_DIMENSION,
    "classifier_architecture": "parent_logistic_regression",
}
