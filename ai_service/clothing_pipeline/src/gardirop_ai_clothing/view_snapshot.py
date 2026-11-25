"""Small durable inputs for pair analysis; diagnostic masks stay in full records."""

from dataclasses import dataclass

from gardirop_ai_clothing.image.io import WHITE_OUTPUT_PROFILE


@dataclass(frozen=True)
class StoredGarmentImage:
    source_size: tuple[int, int]
    output_size: tuple[int, int]
    white_webp: bytes
    rotation_degrees: float
    color_palette: dict[str, float] | None

    @property
    def delivery_webp(self):
        return self.white_webp

    @property
    def delivery_profile(self):
        return WHITE_OUTPUT_PROFILE["profile"]
