"""Fetch the pinned Hugging Face revision SHA for selected BiRefNet Dynamic."""

from huggingface_hub import HfApi

from gardirop_ai_clothing.model_specs import BIREFNET_REPO, BIREFNET_REVISION

MODEL_REPO = BIREFNET_REPO


def main() -> None:
    api = HfApi()
    info = api.model_info(MODEL_REPO, revision=BIREFNET_REVISION)

    print("Model repo:", MODEL_REPO)
    print("Pinned revision SHA:", info.sha)
    print()
    print("Suggested manifest values:")
    print(f"repo_id: {MODEL_REPO}")
    print(f"revision: {info.sha}")


if __name__ == "__main__":
    main()
