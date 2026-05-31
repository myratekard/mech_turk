"""Regression test for the CV second-opinion badge detector (app.services.badge_cv).

Runs the live detector against the committed WhatsApp-compressed sample set and asserts
the cross-domain-validated operating point holds: zero false positives, recall >= 0.95.
No network / API key needed — pure OpenCV against checked-in images + badges/ templates.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import badge_cv

SAMPLES = Path(__file__).resolve().parents[1] / "verify" / "samples"


def _imgs(label):
    return sorted(SAMPLES.glob(f"*/{label}/*.jpeg"))


def test_templates_are_loaded():
    # The packaged badges/ templates must be present, else every verdict degrades to LLM-only.
    assert len(badge_cv._templates()) >= 3


@pytest.mark.skipif(not _imgs("verified"), reason="compressed samples not available")
def test_detector_operating_point_on_compressed_samples():
    pos, neg = _imgs("verified"), _imgs("not_verified")
    tp = sum(1 for p in pos if badge_cv.detect(badge_cv.bgr_from_bytes(p.read_bytes())).matched)
    fp = sum(1 for p in neg if badge_cv.detect(badge_cv.bgr_from_bytes(p.read_bytes())).matched)
    recall = tp / len(pos)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    assert fp == 0, f"false positives on non-verified samples: {fp}"
    assert recall >= 0.95, f"recall regressed: {recall:.3f} ({tp}/{len(pos)})"
    assert precision == 1.0
