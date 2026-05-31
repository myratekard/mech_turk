from __future__ import annotations

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Platform = Literal["instagram", "x", "tiktok", "unknown"]


# ----------------------------------------------------------------------------
# Metric — social counts come as strings like "1M", "8.9M", "7,498".
# We keep the raw string for fidelity and a best-effort parsed integer.
# ----------------------------------------------------------------------------
class Metric(BaseModel):
    raw: Optional[str] = Field(None, description="Verbatim count as shown, e.g. '8.9M'")
    value: Optional[int] = Field(None, description="Parsed integer, e.g. 8900000")

    @staticmethod
    def parse(raw: Optional[str]) -> "Metric":
        if raw is None:
            return Metric(raw=None, value=None)
        s = str(raw).strip()
        if not s:
            return Metric(raw=raw, value=None)
        m = re.match(r"^\s*([\d.,]+)\s*([kKmMbB]?)", s)
        if not m:
            return Metric(raw=raw, value=None)
        num_str, suffix = m.group(1), m.group(2).lower()
        num_str = num_str.replace(",", "")
        try:
            num = float(num_str)
        except ValueError:
            return Metric(raw=raw, value=None)
        mult = {"": 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[suffix]
        return Metric(raw=raw, value=int(round(num * mult)))


# ----------------------------------------------------------------------------
# ProfileArtifact — the structured details extracted once verified.
# posts is Instagram-specific; likes is TikTok-specific; X uses followers/following.
# ----------------------------------------------------------------------------
class ProfileArtifact(BaseModel):
    platform: Platform
    display_name: Optional[str] = None
    handle: Optional[str] = Field(None, description="Username, without the leading @")
    bio: Optional[str] = None
    category: Optional[str] = Field(
        None, description="Profile category/label, e.g. 'Artist', 'Food Consultant'"
    )
    external_links: List[str] = Field(default_factory=list)
    followers: Metric = Field(default_factory=Metric)
    following: Metric = Field(default_factory=Metric)
    posts: Optional[Metric] = Field(None, description="Instagram post count")
    likes: Optional[Metric] = Field(None, description="TikTok like count")


# ----------------------------------------------------------------------------
# Raw structured output from the Gemini vision call (one shot).
# Kept separate from the final fused result so we can audit the LLM signal.
# ----------------------------------------------------------------------------
class VisionProfile(BaseModel):
    """Profile fields as the LLM reads them (strings; parsed later)."""

    display_name: Optional[str] = None
    handle: Optional[str] = None
    bio: Optional[str] = None
    category: Optional[str] = None
    external_links: List[str] = Field(default_factory=list)
    followers: Optional[str] = None
    following: Optional[str] = None
    posts: Optional[str] = None
    likes: Optional[str] = None


class VisionAnalysis(BaseModel):
    """The single structured object Gemini returns for a screenshot."""

    platform: Platform = Field(description="Which platform layout this screenshot shows")
    platform_confidence: float = Field(ge=0.0, le=1.0)

    # Classify the image kind FIRST: only a single profile page is in scope.
    is_profile_screenshot: bool = Field(
        default=True,
        description=(
            "True only if this is a screenshot of ONE social-media PROFILE page "
            "(Instagram/X/TikTok). False for anything else: a feed/post/DM/search-result, "
            "a web or desktop capture, a photo, meme, document, or any non-profile UI."
        ),
    )

    # Reasoning-FIRST: the model must describe what sits next to the name BEFORE
    # committing to the boolean. This field is intentionally ordered before
    # is_verified so structured generation produces the observation first.
    name_adjacent_observation: str = Field(
        description=(
            "Describe EXACTLY what appears immediately to the right of the display name "
            "and of the @handle: e.g. 'nothing/blank', 'a bell icon', 'a heart emoji', "
            "'a small blue disc with a white check', etc. Be literal."
        )
    )

    is_verified: bool = Field(
        description="True ONLY if name_adjacent_observation describes an official verified badge"
    )
    verification_confidence: float = Field(ge=0.0, le=1.0)
    badge_bbox: Optional[List[float]] = Field(
        None,
        description="Normalized [x0,y0,x1,y1] (0..1) bounding box of the verified badge, if present",
    )
    badge_anchor: Optional[str] = Field(
        None, description="What the badge sits next to, e.g. 'right of display name'"
    )
    reasoning: Optional[str] = Field(
        None, description="Short justification for the verification verdict"
    )

    profile: VisionProfile = Field(default_factory=VisionProfile)


# ----------------------------------------------------------------------------
# Signals + final fused verdict
# ----------------------------------------------------------------------------
class LLMSignal(BaseModel):
    is_verified: bool
    confidence: float
    badge_bbox: Optional[List[float]] = None
    badge_anchor: Optional[str] = None
    reasoning: Optional[str] = None


class CVSignal(BaseModel):
    matched: bool
    score: float
    method: Optional[str] = Field(None, description="Which CV check fired: template|heuristic")
    box: Optional[List[int]] = Field(None, description="Pixel [x1,y1,x2,y2] of the CV match")


class VerificationResult(BaseModel):
    verified: bool
    confidence: float = Field(ge=0.0, le=1.0)
    needs_review: bool
    llm_signal: LLMSignal
    cv_signal: CVSignal
    badge_bbox: Optional[List[float]] = None


class AnalysisResult(BaseModel):
    id: str
    created_at: str
    platform: Platform
    platform_confidence: float
    is_profile_screenshot: bool = True
    verification: VerificationResult
    profile: Optional[ProfileArtifact] = None  # populated only when verified
    source_image_ref: Optional[str] = None
    badge_crop_ref: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
