from __future__ import annotations

import base64
import time
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai.chat_models import ChatGoogleGenerativeAI

from app.core.config import settings
from app.schemas.models import ReceiptAnalysis, VisionAnalysis

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
    "0) is_profile_screenshot: FIRST decide whether this is a screenshot of ONE social-media "
    "PROFILE page. Set false for a feed/post/DM/search-result, a web or desktop capture, a photo, "
    "meme, document, or any non-profile UI. If false, you may set platform='unknown' and "
    "is_verified=false (it is out of scope).\n"
    "1) platform: identify the platform from layout cues (icons, fonts, tab bar, button styles). "
    "Use 'unknown' if it is none of instagram/x/tiktok.\n"
    "2) name_adjacent_observation: BEFORE judging, literally describe what is printed immediately "
    "to the right of the display name AND to the right of the @handle.\n"
    "3) is_verified: decide STRICTLY from that observation.\n"
    "4) Extract profile fields verbatim.\n"
    "5) account_type: classify the account as 'individual' (a person), 'organization' (brand / "
    "company / media outlet), 'government' (official state body), or 'unknown'.\n"
    "6) african_classification: decide if the account is AFRICAN — for ANY account_type. 'African' "
    "means EITHER (a) the account is African — a person from or based in Africa, or an African "
    "brand / media outlet / organization / government body; OR (b) its content and audience are "
    "MAJORLY African (content about Africa, captions/comments in African languages or pidgin/slang, "
    "African locations or topics, .ng/.za/.ke etc., an audience that is primarily African). It is "
    "NOT about ethnicity/descent: a Black person in the diaspora (e.g. African-American, Black "
    "British) is NOT 'african' on appearance alone — only if they are actually African or have a "
    "majorly African audience. Weigh ALL signals: display name, @handle, bio, links, location/flag, "
    "language, and the post/content & comments (for the audience read) — not just the name or the "
    "photo. COMMIT to 'african' or 'non_african' whenever the balance of evidence leans one way — "
    "express any doubt through african_confidence (a lean = ~0.5-0.7, a clear case = ~0.8-1.0), do "
    "NOT retreat to generic/unclear just because you are not fully certain. Use 'generic' ONLY when "
    "the identifying text is a culturally-neutral / common international name or generic brand (e.g. "
    "'angel', 'official', 'thebest') AND the content/audience give no signal either. Use 'unclear' "
    "ONLY when there is essentially nothing to assess. Give african_confidence in [0,1]. This is "
    "INFORMATIONAL analytics ONLY and must NOT influence is_verified or the verdict.\n\n"
    "CRITICAL — DEFAULT TO NOT VERIFIED:\n"
    "Most accounts are NOT verified. Only set is_verified=true if you can point to an actual "
    "verified BADGE — a small SOLID COLORED SEAL/DISC with a WHITE CHECKMARK inside it, fused "
    "directly onto the name/handle line. On X (Twitter) the checkmark may be BLUE (individuals), "
    "GOLD/yellow (businesses & organizations) or GREY (government / officials) — ALL THREE count "
    "as verified, not just blue. On Instagram and TikTok the badge is blue. If you cannot clearly "
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
        thinking_budget=settings.gemini_thinking_budget,  # 0 = no thinking tokens (cheaper)
    )
    return model.with_structured_output(VisionAnalysis)


@lru_cache(maxsize=1)
def _receipt_model():
    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=0,
        google_api_key=settings.google_api_key or None,
        thinking_budget=settings.gemini_thinking_budget,
    )
    return model.with_structured_output(ReceiptAnalysis)


_RECEIPT_SYSTEM = (
    "You read bank-transfer / payment receipt screenshots. Given ONE image, return a JSON object "
    "matching the ReceiptAnalysis schema. Decide is_receipt (is this a payment/transfer receipt or "
    "confirmation?). Extract `amount` = the TOTAL amount that was paid or transferred, as a plain "
    "number with no currency symbol and no thousands separators (e.g. '₦12,500.00' -> 12500.00). "
    "If several figures appear, choose the actual transfer/paid total (not a balance or fee). "
    "Set amount to null if no amount is clearly visible. Record the currency symbol/code if shown."
)


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
    # Retry transient Gemini failures (network/quota/5xx) with short backoff.
    last_err = None
    for attempt in range(settings.llm_max_retries + 1):
        try:
            return _structured_model().invoke(messages)
        except Exception as e:
            last_err = e
            if attempt < settings.llm_max_retries:
                time.sleep(0.5 * (2 ** attempt))  # 0.5s, 1s, ...
    raise last_err


@traceable(run_type="llm", name="receipt-analyze")
def extract_receipt_amount(image_bytes: bytes, mime: str = "image/jpeg") -> ReceiptAnalysis:
    """Read a bank-receipt screenshot -> is_receipt + amount paid (for invoice settlement)."""
    messages = [
        SystemMessage(content=_RECEIPT_SYSTEM),
        HumanMessage(
            content=[
                {"type": "text", "text": "Read this payment receipt. Return JSON only."},
                {"type": "image_url", "image_url": {"url": _data_uri(image_bytes, mime)}},
            ]
        ),
    ]
    last_err = None
    for attempt in range(settings.llm_max_retries + 1):
        try:
            return _receipt_model().invoke(messages)
        except Exception as e:
            last_err = e
            if attempt < settings.llm_max_retries:
                time.sleep(0.5 * (2 ** attempt))
    raise last_err
