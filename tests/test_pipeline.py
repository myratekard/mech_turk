from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.schemas.models import CVSignal, LLMSignal, Metric
from app.services import fusion


# --------------------------- Metric parsing (pure) ---------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1M", 1_000_000),
        ("8.9M", 8_900_000),
        ("7,498", 7498),
        ("184", 184),
        ("96.4M", 96_400_000),
        ("57.5K", 57_500),
        ("1.2B", 1_200_000_000),
        (None, None),
        ("", None),
        ("Followers", None),
    ],
)
def test_metric_parse(raw, expected):
    assert Metric.parse(raw).value == expected


# --------------------------- Fusion logic (pure) -----------------------------
def _llm(v, c):
    return LLMSignal(is_verified=v, confidence=c)


def _cv(m, s):
    return CVSignal(matched=m, score=s)


def test_fuse_both_agree_high_confidence_no_review():
    r = fusion.fuse(_llm(True, 0.9), _cv(True, 0.85))
    assert r.verified is True
    assert r.needs_review is False
    assert r.confidence >= 0.8


def test_fuse_llm_only_high_conf_no_review():
    # High-confidence LLM is the trusted authority -> accept without review.
    r = fusion.fuse(_llm(True, 0.9), _cv(False, 0.2))
    assert r.verified is True
    assert r.needs_review is False


def test_fuse_llm_only_mid_conf_flags_review():
    # Above LLM_CONF_MIN but below LLM_CONF_HIGH -> accept but flag for review.
    r = fusion.fuse(_llm(True, 0.5), _cv(False, 0.2))
    assert r.verified is True
    assert r.needs_review is True


def test_fuse_cv_template_only_accepts_but_flags_review():
    # LLM missed but a precise template matched -> accept, flag for review.
    r = fusion.fuse(_llm(False, 0.1), _cv(True, 0.95))
    assert r.verified is True
    assert r.needs_review is True


def test_fuse_neither_rejects():
    r = fusion.fuse(_llm(False, 0.1), _cv(False, 0.2))
    assert r.verified is False
    assert r.needs_review is False


def test_fuse_low_conf_llm_ignored():
    # LLM says verified but below LLM_CONF_MIN, CV also misses -> not verified
    r = fusion.fuse(_llm(True, 0.2), _cv(False, 0.1))
    assert r.verified is False


# --------------------------- Integration (needs key) -------------------------
SAMPLES = Path(__file__).resolve().parents[1] / "verify" / "samples"


@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"), reason="GOOGLE_API_KEY not set; skipping live Gemini test"
)
@pytest.mark.parametrize("platform_dir,expected", [("instagram", "instagram"), ("tiktok", "tiktok")])
def test_pipeline_platform_id_live(platform_dir, expected):
    from app.services.pipeline import analyze

    folder = SAMPLES / platform_dir
    imgs = sorted([p for p in folder.rglob("*.jpeg")])
    if not imgs:
        pytest.skip(f"no samples in {folder}")
    res = analyze(imgs[0].read_bytes(), mime="image/jpeg", persist=False)
    assert res.platform == expected
