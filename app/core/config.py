from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()  # loads .env for local dev


@dataclass(frozen=True)
class Settings:
    # Gemini (LangChain) — reuse the shared myratekard GOOGLE_API_KEY
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    # Gemini 2.5 "thinking" tokens are billed as output and dominate cost; 0 disables them.
    gemini_thinking_budget: int = int(os.getenv("GEMINI_THINKING_BUDGET", "0"))

    # Accepted upload mime types
    allowed_mime: tuple[str, ...] = (
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/tiff",
    )

    # Platforms supported in v1
    platforms: tuple[str, ...] = ("instagram", "x", "tiktok")

    # --- Fusion thresholds (see app/services/fusion.py) ---
    # CV template-match score at/above which the CV signal counts as a hit.
    cv_match_threshold: float = float(os.getenv("CV_MATCH_THRESHOLD", "0.72"))
    # LLM verification_confidence at/above which the LLM signal is "high".
    llm_conf_high: float = float(os.getenv("LLM_CONF_HIGH", "0.75"))
    # LLM verification_confidence below which the LLM signal is ignored entirely.
    llm_conf_min: float = float(os.getenv("LLM_CONF_MIN", "0.40"))
    # Template-match score at/above which the CV second opinion asserts a verified badge.
    # 0.76 = the clean badge/non-badge split validated on full-res + WhatsApp-compressed sets.
    badge_cv_threshold: float = float(os.getenv("BADGE_CV_THRESHOLD", "0.76"))

    # Cheap pre-LLM gate: reject obvious non-phone-screenshots (landscape/square/tiny) by
    # aspect (height/width) + min short side, before spending a Gemini call.
    screenshot_min_aspect: float = float(os.getenv("SCREENSHOT_MIN_ASPECT", "1.3"))
    screenshot_max_aspect: float = float(os.getenv("SCREENSHOT_MAX_ASPECT", "3.0"))
    screenshot_min_short_side: int = int(os.getenv("SCREENSHOT_MIN_SHORT_SIDE", "300"))

    # Where analyzed artifacts (JSON + badge crops) are written
    artifact_dir: str = os.getenv("ARTIFACT_DIR", "artifacts")

    # --- Auth (self-hosted JWT) ---
    auth_secret: str = os.getenv("AUTH_SECRET", "dev-mech-turk-secret-change-me")
    auth_algorithm: str = os.getenv("AUTH_ALGORITHM", "HS256")
    auth_token_ttl_hours: int = int(os.getenv("AUTH_TOKEN_TTL_HOURS", "168"))  # 7 days
    superuser_username: str = os.getenv("SUPERUSER_USERNAME", "adeyehat")
    superuser_password: str = os.getenv("SUPERUSER_PASSWORD", "adeyehat123")
    # Invoicing: org admins bill the superuser for outstanding points × rate.
    invoice_point_rate: float = float(os.getenv("INVOICE_POINT_RATE", "1.0"))  # money per point
    invoice_currency: str = os.getenv("INVOICE_CURRENCY", "USD")

    points_accepted: int = int(os.getenv("POINTS_ACCEPTED", "50"))            # new verified capture
    points_duplicate: int = int(os.getenv("POINTS_DUPLICATE", "-5"))          # account already captured / others' re-upload (penalty)
    points_self_duplicate: int = int(os.getenv("POINTS_SELF_DUPLICATE", "-10"))  # same user re-uploads the same image (penalty)
    # After a user racks up this many regular duplicates, the penalty eases off.
    points_duplicate_reduced: int = int(os.getenv("POINTS_DUPLICATE_REDUCED", "-2"))
    duplicate_reduce_threshold: int = int(os.getenv("DUPLICATE_REDUCE_THRESHOLD", "20"))

    # --- Abuse / cost controls ---
    daily_upload_limit: int = int(os.getenv("DAILY_UPLOAD_LIMIT", "200"))  # per user / 24h
    phash_distance: int = int(os.getenv("PHASH_DISTANCE", "5"))            # near-dup bit threshold

    # Public base URL of the frontend, used to build registration links in emails.
    app_base_url: str = os.getenv("APP_BASE_URL", "http://localhost:5173")

    # --- Clerk auth ---
    clerk_publishable_key: str = os.getenv("CLERK_PUBLISHABLE_KEY", "")
    clerk_secret_key: str = os.getenv("CLERK_SECRET_KEY", "")
    superuser_email: str = os.getenv("SUPERUSER_EMAIL", "")

    # --- Email (best-effort; ZeptoMail preferred, SMTP fallback) ---
    zeptomail_url: str = os.getenv("ZEPTOMAIL_BASE_URL", "https://api.zeptomail.com/v1.1/email")
    zeptomail_token: str = os.getenv("ZEPTOMAIL_TOKEN", "")
    zeptomail_sender: str = os.getenv("ZEPTOMAIL_SENDER", "")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("SMTP_FROM", "")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # Directory of per-platform badge templates (instagram.png, x.png, tiktok.png)
    badges_dir: str = os.getenv("BADGES_DIR", "badges")

    # --- Persistence: SQLite (local dev default) vs MongoDB (deployed) ---
    mongo_uri: str = os.getenv("MONGO_URI", "")
    mongo_db: str = os.getenv("MONGO_DB", "mech_turk")
    db_backend: str = os.getenv("DB_BACKEND", "")   # "sqlite" | "mongo" | "" → auto
    # Prefix all mech_turk collections (e.g. "turk_") when sharing a database with another
    # app, so our users/submissions/counters don't collide with theirs.
    mongo_collection_prefix: str = os.getenv("MONGO_COLLECTION_PREFIX", "")

    # --- Object storage: local disk (dev) vs Cloudflare R2 (deployed) ---
    cloudflare_access_key_id: str = os.getenv("CLOUDFLARE_ACCESS_KEY_ID", "")
    cloudflare_secret_key: str = os.getenv("CLOUDFLARE_SECRET_KEY", "")
    cloudflare_endpoint: str = os.getenv("CLOUDFLARE_ENDPOINT", "")
    cloudflare_bucket: str = os.getenv("CLOUDFLARE_BUCKET", "")
    cloudflare_cdn_url: str = os.getenv("CLOUDFLARE_CDN_URL", "")

    @property
    def use_mongo(self) -> bool:
        """MongoDB when DB_BACKEND=mongo, or auto-on whenever a MONGO_URI is configured."""
        if self.db_backend == "mongo":
            return True
        if self.db_backend == "sqlite":
            return False
        return bool(self.mongo_uri)

    @property
    def use_r2(self) -> bool:
        """Cloudflare R2 when its credentials + bucket are configured, else local disk."""
        return bool(
            self.cloudflare_access_key_id and self.cloudflare_secret_key
            and self.cloudflare_endpoint and self.cloudflare_bucket
        )


settings = Settings()
