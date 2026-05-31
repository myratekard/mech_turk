from __future__ import annotations

from app.core.config import settings
from app.schemas.models import CVSignal, LLMSignal, VerificationResult, VisionAnalysis


def to_llm_signal(va: VisionAnalysis) -> LLMSignal:
    return LLMSignal(
        is_verified=va.is_verified,
        confidence=va.verification_confidence,
        badge_bbox=va.badge_bbox,
        badge_anchor=va.badge_anchor,
        reasoning=va.reasoning,
    )


def fuse(llm: LLMSignal, cv: CVSignal, badge_bbox=None) -> VerificationResult:
    """Fuse the LLM and CV verified-badge signals.

    The LLM is the primary authority for the verdict: on the labeled sample set it
    scores precision=recall=1.0, whereas the bare CV heuristic scores ~0. So CV is
    used only to CORROBORATE — and only a precise TEMPLATE match (cv.matched) counts
    as a CV signal; the loose blue-disc heuristic never asserts a positive.

    Lenient policy (per product decision — accept readily, flag the unsure):
      - LLM + CV template agree   -> verified, HIGH confidence, no review
      - LLM only                  -> verified; needs_review unless LLM is high-confidence
      - CV template only (LLM missed) -> verified, low confidence, needs_review
      - neither                    -> not verified
    """
    llm_fires = llm.is_verified and llm.confidence >= settings.llm_conf_min
    llm_high = llm.is_verified and llm.confidence >= settings.llm_conf_high
    cv_fires = cv.matched  # template-only (see cv_verifier)

    if llm_fires and cv_fires:
        confidence = round(min(1.0, 0.6 + 0.4 * (llm.confidence * 0.6 + cv.score * 0.4) + 0.1), 4)
        return VerificationResult(
            verified=True, confidence=max(confidence, 0.85), needs_review=False,
            llm_signal=llm, cv_signal=cv, badge_bbox=badge_bbox,
        )

    if llm_fires:
        # LLM is the trusted authority. Flag for review only when its own confidence
        # is not high (CV could not corroborate, since we have no/failed template).
        confidence = round(min(0.95, 0.55 + 0.4 * llm.confidence), 4)
        return VerificationResult(
            verified=True, confidence=confidence, needs_review=not llm_high,
            llm_signal=llm, cv_signal=cv, badge_bbox=badge_bbox,
        )

    if cv_fires:
        # LLM said no but a real badge-shaped template matched — surface for review.
        return VerificationResult(
            verified=True, confidence=round(min(0.6, 0.3 + 0.4 * cv.score), 4),
            needs_review=True, llm_signal=llm, cv_signal=cv, badge_bbox=badge_bbox,
        )

    # Neither fired -> not verified. Confidence = how sure we are it's NOT verified.
    residual = cv.score if cv.matched else 0.0
    return VerificationResult(
        verified=False, confidence=round(max(0.0, 1.0 - residual), 4), needs_review=False,
        llm_signal=llm, cv_signal=cv, badge_bbox=badge_bbox,
    )
