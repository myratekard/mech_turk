"""Tiny perceptual hash (average hash) — stdlib + PIL/numpy, no extra deps.

Used to detect re-uploaded / near-identical screenshots BEFORE calling the LLM, so
spam re-uploads don't burn tokens and can be penalized.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image


def average_hash(image_bytes: bytes, size: int = 8) -> str:
    """64-bit average hash as a 16-char hex string."""
    img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((size, size), Image.LANCZOS)
    px = np.asarray(img, dtype=np.float32)
    bits = (px > px.mean()).flatten()
    val = 0
    for b in bits:
        val = (val << 1) | int(b)
    return f"{val:0{size * size // 4}x}"


def dhash(image_bytes: bytes, size: int = 16) -> str:
    """256-bit difference (gradient) hash as a 64-char hex string.

    Resizes to (size+1, size) grayscale and compares each pixel to its right
    neighbour — encoding the horizontal gradient rather than gross light/dark
    layout. Far more discriminating than average_hash for phone screenshots that
    share UI structure (status bar, centered avatar, thumbnail grid), so distinct
    profiles no longer collide. Different length from the old 8x8 average_hash, so
    hamming() treats legacy hashes as non-matching (length guard) — intentional.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((size + 1, size), Image.LANCZOS)
    px = np.asarray(img, dtype=np.float32)
    bits = (px[:, 1:] > px[:, :-1]).flatten()  # size rows x size cols = size*size bits
    val = 0
    for b in bits:
        val = (val << 1) | int(b)
    return f"{val:0{size * size // 4}x}"


def hamming(a: str, b: str) -> int:
    """Bit distance between two hex hashes (large if different lengths)."""
    if not a or not b or len(a) != len(b):
        return 999
    return bin(int(a, 16) ^ int(b, 16)).count("1")
