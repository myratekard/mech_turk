"""Non-phone-screenshot rejection: cheap aspect/size gate + the LLM is_profile_screenshot map."""
from __future__ import annotations

import io
import types

from PIL import Image

from app.services import image_gate
from app.api.routes.turk import map_status_points


def _png(w, h) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (123, 200, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_gate_accepts_phone_portrait():
    assert image_gate.check_phone_screenshot(_png(1290, 2796)) is None


def test_gate_rejects_landscape():
    assert image_gate.check_phone_screenshot(_png(1920, 1080)) is not None


def test_gate_rejects_square_and_tiny():
    assert image_gate.check_phone_screenshot(_png(800, 800)) is not None
    assert image_gate.check_phone_screenshot(_png(100, 200)) is not None


def test_gate_rejects_unreadable():
    assert image_gate.check_phone_screenshot(b"not an image") is not None


def _result(is_profile, verified=False, needs_review=False):
    return types.SimpleNamespace(
        is_profile_screenshot=is_profile,
        verification=types.SimpleNamespace(verified=verified, needs_review=needs_review),
    )


def test_map_status_non_profile_is_unsupported():
    status, points = map_status_points(_result(is_profile=False, verified=True))
    assert status == "unsupported"
    assert points == 0


def test_map_status_profile_verified_is_accepted():
    status, points = map_status_points(_result(is_profile=True, verified=True))
    assert status == "accepted"
