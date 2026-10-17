"""Locating and inspecting the notification icon and badge."""

from __future__ import annotations

from dataclasses import dataclass


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "/"))


def image_url(value: str) -> str:
    """Turn the ICON / BADGE setting into a URL the browser can load."""
    if not value:
        return ""
    if is_url(value):
        return value
    from django.templatetags.static import static

    return static(value)


def find_image_file(value: str) -> str | None:
    """Path on disk of a static ICON / BADGE, or None when it is a URL or missing."""
    if not value or is_url(value):
        return None
    from django.contrib.staticfiles import finders

    found = finders.find(value)
    if isinstance(found, list):
        return found[0] if found else None
    return found


@dataclass
class ImageReport:
    width: int
    height: int
    has_alpha: bool
    transparent_share: float  # 0..1, pixels that are fully or mostly transparent
    fills_frame: bool  # opaque pixels reach close to all four edges


def inspect_image(path: str) -> ImageReport:
    from PIL import Image

    with Image.open(path) as img:
        img.load()
        width, height = img.size
        has_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
        if not has_alpha:
            return ImageReport(width, height, False, 0.0, True)
        alpha = img.convert("RGBA").getchannel("A")
        histogram = alpha.histogram()
        total = width * height
        transparent = sum(histogram[:32])
        bbox = alpha.point(lambda a: 255 if a >= 32 else 0).getbbox()
        if bbox:
            left, upper, right, lower = bbox
            fills = (right - left) >= 0.9 * width and (lower - upper) >= 0.9 * height
        else:
            fills = False
        return ImageReport(width, height, True, transparent / total if total else 0.0, fills)


def badge_problems(report: ImageReport) -> list[tuple[str, str]]:
    """(check id, message) for each problem found in a badge image."""
    problems = []
    if not report.has_alpha:
        problems.append(
            ("W003", "The push badge has no transparent pixels, so Android shows it as a solid white square.")
        )
    else:
        opaque = 1 - report.transparent_share
        if opaque > 0.6 or (report.fills_frame and opaque > 0.5):
            problems.append(
                (
                    "W004",
                    "The push badge is mostly solid (it looks like a full app icon). Android draws every "
                    "non-transparent pixel white, so it shows as a white blob instead of a symbol.",
                )
            )
    if min(report.width, report.height) < 72:
        problems.append(
            ("W005", f"The push badge is {report.width}x{report.height}; use at least 72x72 (96x96 is best).")
        )
    return problems
