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


def _cv(m, s, method="template"):
    return CVSignal(matched=m, score=s, method=method)


def test_fuse_both_agree_high_confidence_no_review():
    r = fusion.fuse(_llm(True, 0.9), _cv(True, 0.85))
    assert r.verified is True
    assert r.needs_review is False
    assert r.confidence >= 0.8


def test_fuse_disagreement_llm_high_conf_cv_no_trusts_llm():
    # HIGH-confidence LLM verified but CV missed: CV template-match is fragile to client-side
    # compression, so we trust the LLM (verified, no review) — CV only trims confidence.
    r = fusion.fuse(_llm(True, 0.9), _cv(False, 0.2))
    assert r.verified is True
    assert r.needs_review is False


def test_fuse_disagreement_llm_borderline_cv_no_routes_to_review():
    # BORDERLINE LLM verified (>= conf_min, < conf_high) + CV miss -> a human reconciles.
    r = fusion.fuse(_llm(True, 0.5), _cv(False, 0.2))
    assert r.verified is True
    assert r.needs_review is True


def test_fuse_disagreement_cv_yes_llm_no_routes_to_review():
    # LLM missed but a precise template matched -> route to review (has caught LLM errors).
    r = fusion.fuse(_llm(False, 0.1), _cv(True, 0.95))
    assert r.verified is True
    assert r.needs_review is True


def test_fuse_both_agree_not_verified_no_review():
    r = fusion.fuse(_llm(False, 0.1), _cv(False, 0.2))
    assert r.verified is False
    assert r.needs_review is False


def test_fuse_low_conf_llm_and_cv_miss_agree_not_verified():
    # LLM says verified but below LLM_CONF_MIN -> treated as "no"; CV "no" too -> consensus no.
    r = fusion.fuse(_llm(True, 0.2), _cv(False, 0.1))
    assert r.verified is False
    assert r.needs_review is False


def test_fuse_cv_unavailable_falls_back_to_llm_high_conf():
    # No templates / load error -> LLM is the sole authority.
    r = fusion.fuse(_llm(True, 0.9), _cv(False, 0.0, method="unavailable"))
    assert r.verified is True
    assert r.needs_review is False


def test_fuse_cv_unavailable_falls_back_to_llm_mid_conf_review():
    r = fusion.fuse(_llm(True, 0.5), _cv(False, 0.0, method="unavailable"))
    assert r.verified is True
    assert r.needs_review is True


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
