"""Safe image decoding, color normalization and lossless WebP encoding."""

import io
import warnings

from PIL import Image, ImageCms, ImageOps

from gardirop_ai_clothing.errors import ImageProcessingError

SUPPORTED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
DEFAULT_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_PIXELS = 24_000_000
WHITE_OUTPUT_PROFILE = {
    "profile": "white-square-lossless-webp-v1",
    "background": "#FFFFFF",
    "mode": "RGB",
    "format": "WEBP",
    "lossless": True,
    "method": 0,
    "quality": 20,
}


def _convert_to_srgb(image: Image.Image) -> Image.Image:
    """Convert image colors to sRGB and composite transparency on white."""
    has_alpha = "A" in image.getbands() or "transparency" in image.info

    alpha = image.convert("RGBA").getchannel("A") if has_alpha else None
    icc_profile = image.info.get("icc_profile")

    if icc_profile:
        try:
            # Preserve CMYK input until ICC conversion.
            color_image = image if image.mode in {"RGB", "CMYK"} else image.convert("RGB")

            source_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
            target_profile = ImageCms.createProfile("sRGB")

            rgb = ImageCms.profileToProfile(
                color_image,
                source_profile,
                target_profile,
                outputMode="RGB",
            )
        except Exception as exc:
            raise ImageProcessingError("Image ICC color profile could not be converted.") from exc
    else:
        # Images without ICC metadata are treated as sRGB.
        rgb = image.convert("RGB")

    if alpha is None:
        return rgb

    rgba = rgb.convert("RGBA")
    rgba.putalpha(alpha)

    white = Image.new(
        "RGBA",
        rgba.size,
        (255, 255, 255, 255),
    )

    return Image.alpha_composite(white, rgba).convert("RGB")


def decode_uploaded_image(
    data: bytes,
    *,
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    max_pixels: int = DEFAULT_MAX_PIXELS,
) -> Image.Image:
    """
    Decode a single-frame uploaded image into RGB/sRGB.

    Does not crop, resize or perform illumination correction.
    """
    if max_upload_bytes < 1 or max_pixels < 1:
        raise ImageProcessingError("Image input limits must be positive.")

    if not isinstance(data, bytes) or not data:
        raise ImageProcessingError("Image upload must contain non-empty bytes.")

    if len(data) > max_upload_bytes:
        raise ImageProcessingError("Image upload exceeds the configured byte limit.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            with Image.open(io.BytesIO(data)) as source:
                if source.format not in SUPPORTED_FORMATS:
                    raise ImageProcessingError(f"Unsupported image format: {source.format}")

                if getattr(source, "n_frames", 1) != 1:
                    raise ImageProcessingError("Animated or multi-frame images are not supported.")

                width, height = source.size

                if width < 1 or height < 1 or width * height > max_pixels:
                    raise ImageProcessingError("Image dimensions exceed the configured limit.")

                source.load()
                oriented = ImageOps.exif_transpose(source)
                return _convert_to_srgb(oriented)

    except ImageProcessingError:
        raise
    except (
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as exc:
        raise ImageProcessingError("Image could not be decoded safely.") from exc


def composite_rgba_on_white(
    image: Image.Image,
) -> Image.Image:
    """Prepare a transparent RGBA garment image for an RGB encoder."""
    if image.mode != "RGBA":
        raise ImageProcessingError("Expected an RGBA image for compositing.")

    background = Image.new(
        "RGBA",
        image.size,
        (255, 255, 255, 255),
    )

    return Image.alpha_composite(
        background,
        image,
    ).convert("RGB")


def encode_transparent_webp(
    image: Image.Image,
) -> bytes:
    """
    Encode an RGBA image as lossless transparent WebP.

    Visible colors and alpha are preserved. Hidden RGB values in
    completely transparent pixels are not guaranteed to survive.
    """
    if image.mode != "RGBA":
        raise ImageProcessingError("Lossless transparent WebP requires RGBA input.")

    if image.width < 1 or image.height < 1 or image.width * image.height > DEFAULT_MAX_PIXELS:
        raise ImageProcessingError("Invalid image dimensions for WebP encoding.")

    output = io.BytesIO()

    try:
        image.save(
            output,
            format="WEBP",
            lossless=True,
            method=0,
            quality=20,
            exact=False,
        )
    except (OSError, ValueError) as exc:
        raise ImageProcessingError("Lossless WebP encoding failed.") from exc

    return output.getvalue()


def encode_white_webp(image: Image.Image) -> bytes:
    """Losslessly compress already-composited RGB pixels; no alpha, no resize.

    In lossless mode quality=20 controls compression effort, not pixel loss.
    The white canvas is made upstream; this function never drops RGBA alpha.
    """
    if not isinstance(image, Image.Image) or image.mode != "RGB":
        raise ImageProcessingError("White WebP requires already-composited RGB input.")
    if image.width < 1 or image.height < 1 or image.width * image.height > DEFAULT_MAX_PIXELS:
        raise ImageProcessingError("Invalid image dimensions for WebP encoding.")
    output = io.BytesIO()
    try:
        image.save(output, format="WEBP", lossless=True, method=0, quality=20)
    except (OSError, ValueError) as exc:
        raise ImageProcessingError("White lossless WebP encoding failed.") from exc
    return output.getvalue()
