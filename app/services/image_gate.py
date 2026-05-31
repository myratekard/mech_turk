"""Cheap pre-LLM gate: is this plausibly a phone screenshot?

Phone profile screenshots are tall portrait images. Rejecting landscape / square / tiny
images here (by dimensions only, no decode of the full raster needed beyond the header)
avoids spending a Gemini call on memes, desktop captures, and photos. Phone-shaped images
that still aren't a profile page are caught later by the LLM `is_profile_screenshot` field.
"""
from __future__ import annotations

import io
from typing import Optional

from PIL import Image

from app.core.config import settings


def check_phone_screenshot(image_bytes: bytes) -> Optional[str]:
    """Return a rejection reason string if the image is clearly not a phone screenshot,
    else None (passes the cheap gate)."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            w, h = img.size
    except Exception:
        return "Unreadable image file."
    if w <= 0 or h <= 0:
        return "Invalid image dimensions."
    if min(w, h) < settings.screenshot_min_short_side:
        return f"Image too small to be a phone screenshot ({w}x{h})."
    aspect = h / w  # portrait > 1
    if aspect < settings.screenshot_min_aspect:
        return "Not a portrait phone screenshot (too wide / landscape)."
    if aspect > settings.screenshot_max_aspect:
        return "Unusual aspect ratio for a phone screenshot."
    return None
