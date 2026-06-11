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
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "2"))   # transient-failure retries
    # Hard per-call deadline (seconds) for a Gemini invoke. Bounds the tail: under load a
    # throttled (429) call fails fast and routes to in_review instead of the client's inner
    # exponential backoff stacking to minutes. 0 disables.
    llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    # Client-side request rate cap (requests/sec, shared process-wide) to keep the worker pool
    # from bursting past Gemini's per-minute quota and tripping 429s. 0 disables.
    llm_rate_limit_rps: float = float(os.getenv("LLM_RATE_LIMIT_RPS", "0"))
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
    # African eligibility gate (informational classifier becomes a deciding factor):
    #   verified + african  (conf >= min)     -> accepted
    #   verified + non_african (conf >= min)   -> invalid (ineligible; disputable)
    #   verified + generic/unclear/low-conf    -> in_review (human decides)
    # Tuned on the labeled set: 0.7 yields ~10% review, 0 false-accepts (see verify/classification).
    african_gate_enabled: bool = os.getenv("AFRICAN_GATE_ENABLED", "true").lower() == "true"
    african_conf_min: float = float(os.getenv("AFRICAN_CONF_MIN", "0.7"))

    # --- Async processing (background worker) ---
    # When on, uploads are stored as 'queued' and returned instantly; a separate worker runs the
    # pipeline and updates the verdict. Off = legacy synchronous processing in the request.
    async_processing: bool = os.getenv("ASYNC_PROCESSING", "false").lower() == "true"
    worker_poll_seconds: float = float(os.getenv("WORKER_POLL_SECONDS", "2"))   # idle poll interval
    worker_stale_seconds: int = int(os.getenv("WORKER_STALE_SECONDS", "300"))   # requeue items stuck 'processing'
    worker_max_attempts: int = int(os.getenv("WORKER_MAX_ATTEMPTS", "3"))       # before parking as in_review
    # How many submissions one worker processes at once. The Gemini call is mostly network wait,
    # so overlapping a handful greatly raises throughput. Clamped to [1,10]; atomic claims keep
    # the concurrent workers from grabbing the same item.
    worker_concurrency: int = int(os.getenv("WORKER_CONCURRENCY", "8"))
    points_duplicate: int = int(os.getenv("POINTS_DUPLICATE", "-2"))          # regular duplicate, first tier (penalty)
    points_self_duplicate: int = int(os.getenv("POINTS_SELF_DUPLICATE", "-10"))  # self re-upload, final tier (penalty)
    # After a user racks up this many regular duplicates, the penalty escalates (to -5).
    points_duplicate_escalated: int = int(os.getenv("POINTS_DUPLICATE_ESCALATED", "-5"))
    duplicate_escalate_threshold: int = int(os.getenv("DUPLICATE_ESCALATE_THRESHOLD", "20"))
    # Self-duplicate escalation: first N = warning (0 pts), next M = mid penalty, then -10.
    self_dup_warn_count: int = int(os.getenv("SELF_DUP_WARN_COUNT", "5"))
    self_dup_mid_count: int = int(os.getenv("SELF_DUP_MID_COUNT", "15"))
    self_dup_mid_penalty: int = int(os.getenv("SELF_DUP_MID_PENALTY", "-5"))

    # --- Abuse / cost controls ---
    daily_upload_limit: int = int(os.getenv("DAILY_UPLOAD_LIMIT", "200"))  # per user / 24h
    phash_distance: int = int(os.getenv("PHASH_DISTANCE", "5"))            # legacy 64-bit avg-hash threshold
    # 256-bit dHash near-EXACT threshold: only a true re-upload of the same screenshot
    # short-circuits as a duplicate. Looser look-alikes fall through to the LLM, and the
    # account-level handle check decides — so two different profiles can't be collapsed.
    dhash_distance: int = int(os.getenv("DHASH_DISTANCE", "12"))
    # How many recent submissions the fuzzy dHash scan compares against. The scan is a linear
    # Hamming comparison (no index for "within N bits"), so this bounds its cost. Near-dupe
    # re-uploads are almost always recent, so a modest window suffices.
    phash_scan_limit: int = int(os.getenv("PHASH_SCAN_LIMIT", "1000"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "10"))             # per-image size cap
    # Downscale the image SENT TO THE LLM to this longest-edge px (full-res still used for CV).
    # Big phone screenshots (5-8MB) are slow to upload/process and cost more tokens; the badge
    # is legible well under this. 0 disables downscaling.
    llm_image_max_dim: int = int(os.getenv("LLM_IMAGE_MAX_DIM", "1280"))

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
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def use_r2(self) -> bool:
        """Cloudflare R2 when its credentials + bucket are configured, else local disk."""
        return bool(
            self.cloudflare_access_key_id and self.cloudflare_secret_key
            and self.cloudflare_endpoint and self.cloudflare_bucket
        )


settings = Settings()
