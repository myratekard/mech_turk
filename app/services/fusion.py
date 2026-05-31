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
    """Fuse the LLM verdict with the CV badge detector as an independent SECOND OPINION.

    Both signals reach precision=recall=1.0 on their labeled sets, and they fail in
    different ways (the CV detector even caught LLM mislabels). The rule is consensus-based:

      - both AGREE verified      -> verified, HIGH confidence, no review
      - both AGREE not verified  -> not verified, no review
      - they DISAGREE            -> treat as a candidate but ROUTE TO THE REVIEW QUEUE
                                    (needs_review) so a human reconciles
      - CV unavailable (no templates / load error) -> fall back to LLM-only, flagging
        for review unless the LLM is high-confidence

    `cv.matched` is the template-match verdict (score >= badge_cv_threshold); the bare
    blue-disc heuristic never asserts a positive on its own.
    """
    llm_yes = llm.is_verified and llm.confidence >= settings.llm_conf_min
    llm_high = llm.is_verified and llm.confidence >= settings.llm_conf_high

    # No CV opinion available -> LLM is the sole authority.
    if cv.method == "unavailable":
        return VerificationResult(
            verified=llm_yes,
            confidence=round(min(0.95, 0.55 + 0.4 * llm.confidence) if llm_yes
                             else max(0.0, 1.0 - llm.confidence), 4),
            needs_review=llm_yes and not llm_high,
            llm_signal=llm, cv_signal=cv, badge_bbox=badge_bbox,
        )

    cv_yes = cv.matched

    if llm_yes and cv_yes:
        # Consensus verified — strongest signal we can produce.
        confidence = round(min(1.0, 0.85 + 0.15 * (0.6 * llm.confidence + 0.4 * cv.score)), 4)
        return VerificationResult(
            verified=True, confidence=confidence, needs_review=False,
            llm_signal=llm, cv_signal=cv, badge_bbox=badge_bbox,
        )

    if not llm_yes and not cv_yes:
        # Consensus NOT verified. Confidence = how sure we are it is not verified.
        return VerificationResult(
            verified=False, confidence=round(max(0.0, 1.0 - cv.score), 4), needs_review=False,
            llm_signal=llm, cv_signal=cv, badge_bbox=badge_bbox,
        )

    # Disagreement (one says verified, the other does not) -> human review.
    return VerificationResult(
        verified=True, confidence=0.5, needs_review=True,
        llm_signal=llm, cv_signal=cv, badge_bbox=badge_bbox,
    )
