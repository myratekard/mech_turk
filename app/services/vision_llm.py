from __future__ import annotations

import base64
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai.chat_models import ChatGoogleGenerativeAI

from app.core.config import settings
from app.schemas.models import VisionAnalysis

try:
    from langsmith import traceable
except Exception:  # langsmith optional
    def traceable(*_args, **_kwargs):
        def _wrap(fn):
            return fn
        return _wrap


_SYSTEM = (
    "You are a meticulous social-media screenshot analyst. You are given ONE screenshot of a "
    "profile page from Instagram, X (Twitter), or TikTok. Return a single JSON object matching "
    "the VisionAnalysis schema.\n\n"
    "TASKS:\n"
    "1) platform: identify the platform from layout cues (icons, fonts, tab bar, button styles). "
    "Use 'unknown' if it is none of instagram/x/tiktok.\n"
    "2) name_adjacent_observation: BEFORE judging, literally describe what is printed immediately "
    "to the right of the display name AND to the right of the @handle.\n"
    "3) is_verified: decide STRICTLY from that observation.\n"
    "4) Extract profile fields verbatim.\n\n"
    "CRITICAL — DEFAULT TO NOT VERIFIED:\n"
    "Most accounts are NOT verified. Only set is_verified=true if you can point to an actual "
    "verified BADGE — a small SOLID COLORED SEAL/DISC (blue; gold or grey on X for orgs) with a "
    "WHITE CHECKMARK inside it, fused directly onto the name/handle line. If you cannot clearly "
    "see a white check inside a colored disc on the name line, is_verified=false.\n\n"
    "THESE ARE NOT BADGES (is_verified=false) — do not be fooled by them:\n"
    "- ANY emoji inside the display name: hearts (❤️💙), sparkles (✨), stars (⭐), flags (🇺🇸🇳🇬), "
    "bubbles (🫧), check emoji (✅), blue circle emoji (🔵), crowns, etc.\n"
    "- Colored/gradient rings or a red 'LIVE' tag around the profile photo.\n"
    "- Blue 'Follow' buttons, blue category/business chips, blue hyperlinks, the bell/menu/share "
    "icons in the top bar, blank space.\n"
    "- A check that is in the bio text or a post rather than fused to the name line.\n"
    "- A small/new follower count does NOT decide it either way — judge ONLY by the badge.\n\n"
    "PLATFORM BADGE LOCATION:\n"
    "- Instagram: right of the @handle in the top bar, OR right of the display name.\n"
    "- X (Twitter): right of the display name (the bold name, not the @handle).\n"
    "- TikTok: right of the @handle/nickname under the centered avatar.\n\n"
    "RULES:\n"
    "- verification_confidence and platform_confidence are your own calibrated confidence in [0,1]. "
    "If is_verified=false, verification_confidence is your confidence that NO badge is present.\n"
    "- badge_bbox: normalized [x0,y0,x1,y1] in 0..1 (origin top-left) tightly around the badge; "
    "null if no badge.\n"
    "- For profile fields, copy text EXACTLY as shown (counts like '1M', '8.9M', '7,498' stay as "
    "strings). Use null for anything not visible. Never invent data.\n"
    "- handle is the username WITHOUT a leading '@'."
)


@lru_cache(maxsize=1)
def _structured_model():
    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=0,
        google_api_key=settings.google_api_key or None,
    )
    return model.with_structured_output(VisionAnalysis)


def _data_uri(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


@traceable(run_type="llm", name="vision-analyze")
def analyze_screenshot(image_bytes: bytes, mime: str = "image/jpeg") -> VisionAnalysis:
    """One Gemini vision call -> platform + verification verdict + profile fields."""
    messages = [
        SystemMessage(content=_SYSTEM),
        HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": (
                        "Analyze this profile screenshot. Identify the platform, decide strictly "
                        "whether the official verified badge is present, and extract the profile "
                        "fields. Return JSON only."
                    ),
                },
                {"type": "image_url", "image_url": {"url": _data_uri(image_bytes, mime)}},
            ]
        ),
    ]
    return _structured_model().invoke(messages)
