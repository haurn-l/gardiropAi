"""Foreground-only color palette, equally weighting front and back photos."""

import numpy as np
from PIL import Image

COLOR_PALETTE_VERSION = "foreground-lab-palette-v2-muted-blue"

PALETTE = {
    "Siyah": [(15, 15, 15)],
    "Beyaz": [(245, 245, 240)],
    "Gri": [(65, 65, 65), (110, 110, 110), (175, 175, 175)],
    "Kırmızı": [(190, 25, 35), (245, 50, 50)],
    "Bordo": [(95, 15, 35)],
    "Turuncu": [(240, 120, 25)],
    "Sarı": [(240, 210, 35)],
    "Yeşil": [(35, 125, 65), (90, 175, 70), (25, 65, 45)],
    "Haki": [(95, 100, 55)],
    "Mavi": [(35, 100, 200), (110, 175, 220), (65, 90, 110), (110, 135, 155)],
    "Lacivert": [(20, 35, 80)],
    "Mor": [(110, 45, 150)],
    "Pembe": [(225, 130, 170)],
    "Kahverengi": [(100, 65, 40)],
    "Bej": [(200, 180, 145)],
    "Krem": [(235, 225, 195)],
}


def _lab(rgb):
    srgb = np.asarray(rgb, dtype=np.float64) / 255
    linear = np.where(srgb > 0.04045, ((srgb + 0.055) / 1.055) ** 2.4, srgb / 12.92)
    xyz = (
        linear
        @ np.array(
            [
                [0.4124564, 0.3575761, 0.1804375],
                [0.2126729, 0.7151522, 0.0721750],
                [0.0193339, 0.1191920, 0.9503041],
            ]
        ).T
    )
    xyz /= [0.95047, 1.0, 1.08883]
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack(
        [116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])],
        axis=-1,
    )


def _view_palette(image):
    rgba = image.convert("RGBA")
    rgba.thumbnail((256, 256), Image.Resampling.LANCZOS)
    array = np.asarray(rgba)
    pixels = array[array[..., 3] >= 224, :3]
    if len(pixels) < 16:
        return None
    labs = _lab(pixels)
    labels = [name for name, colors in PALETTE.items() for _ in colors]
    centers = _lab([rgb for colors in PALETTE.values() for rgb in colors])
    nearest = np.argmin(((labs[:, None] - centers[None]) ** 2).sum(axis=2), axis=1)
    counts = {name: 0 for name in PALETTE}
    for i, name in enumerate(labels):
        counts[name] += int(np.count_nonzero(nearest == i))
    return {name: count / len(pixels) for name, count in counts.items()}


def detect_pair_color(front, back):
    return combine_view_palettes(_view_palette(front), _view_palette(back))


def view_palette(image):
    """The identical per-view palette used by full pair analysis."""
    return _view_palette(image)


def combine_view_palettes(front, back):
    views = [front, back]
    available = [v for v in views if v is not None]
    if not available:
        return {
            "value": None,
            "source": "foreground_lab_palette",
            "palette_version": COLOR_PALETTE_VERSION,
            "status": "insufficient_foreground",
            "palette": [],
        }
    scores = {name: sum(v[name] for v in available) / len(available) for name in PALETTE}
    ordered = sorted(scores, key=lambda name: (-scores[name], name))
    visible = [name for name in ordered[:2] if scores[name] >= 0.20]
    value = " / ".join(visible) if visible and scores[ordered[0]] >= 0.25 else None
    return {
        "value": value,
        "source": "foreground_lab_palette",
        "palette_version": COLOR_PALETTE_VERSION,
        "status": "suggested" if value else "uncertain",
        "palette": [
            {"label": name, "foreground_fraction": scores[name]}
            for name in ordered
            if scores[name] > 0.005
        ],
        "front_palette": views[0],
        "back_palette": views[1],
        "score_kind": "pixel_fraction_not_probability",
    }
