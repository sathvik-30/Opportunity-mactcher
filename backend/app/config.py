"""
config.py — Central configuration. All env vars read here.
Phase 3 additions: scheduler settings appended. Nothing removed.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# ── Database ──────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite:///./data/opportunity_matcher.db"
)

# ── JWT Authentication ────────────────────────────────────────────
# No insecure default: a hardcoded fallback secret would let anyone who
# reads this file forge valid tokens for any user. Startup fails fast
# instead if JWT_SECRET isn't set — set it in your .env file.
JWT_SECRET: str = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET environment variable is not set. Refusing to start "
        "with no signing secret — set JWT_SECRET in your .env file."
    )
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_HOURS: int = 24

# ── External APIs ─────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# ── Cache ─────────────────────────────────────────────────────────
CACHE_MINUTES: int = 10

# ── Scheduler (Phase 3) ───────────────────────────────────────────
# Set SCHEDULER_ENABLED=false to disable background scraping entirely.
SCHEDULER_ENABLED: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"

# Scrape interval. SCRAPER_INTERVAL_MINUTES overrides SCRAPER_INTERVAL_HOURS.
# For development: set SCRAPER_INTERVAL_MINUTES=5 in .env
# For production: SCRAPER_INTERVAL_HOURS=6 (default)
SCRAPER_INTERVAL_HOURS: int   = int(os.getenv("SCRAPER_INTERVAL_HOURS", "6"))
SCRAPER_INTERVAL_MINUTES: str = os.getenv("SCRAPER_INTERVAL_MINUTES", "")

# If true, runs scraper once in background immediately after startup.
RUN_SCRAPER_ON_STARTUP: bool = (
    os.getenv("RUN_SCRAPER_ON_STARTUP", "false").lower() == "true"
)

# Timezone for scheduled jobs (affects cron trigger times).
APP_TIMEZONE: str = os.getenv("APP_TIMEZONE", "Asia/Kolkata")

# ── AI Match Engine / Notifications (Phase 6) ─────────────────────
# Minimum weighted match score (0-100) required before a student is
# notified about a new opportunity. Configurable without code changes.
MATCH_THRESHOLD: int = int(os.getenv("MATCH_THRESHOLD", "70"))

# ── Email / SMTP (Phase 7) ─────────────────────────────────────────
# EMAIL_ENABLED=false (the default) means the system NEVER opens an SMTP
# connection — it only logs what it would have sent. Safe for local dev.
EMAIL_ENABLED: bool = os.getenv("EMAIL_ENABLED", "false").lower() == "true"

SMTP_HOST: str        = os.getenv("SMTP_HOST", "")
SMTP_PORT: int         = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME: str     = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD: str     = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL: str   = os.getenv("SMTP_FROM_EMAIL", "")
SMTP_FROM_NAME: str    = os.getenv("SMTP_FROM_NAME", "Opportunity Matcher")
SMTP_USE_TLS: bool     = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

# Rate limiting / safety — see notification_service.py
EMAIL_BATCH_SIZE: int      = int(os.getenv("EMAIL_BATCH_SIZE", "50"))
EMAIL_DELAY_SECONDS: float = float(os.getenv("EMAIL_DELAY_SECONDS", "1"))
EMAIL_MAX_RETRIES: int     = int(os.getenv("EMAIL_MAX_RETRIES", "3"))

# Used to build a safe "View in Dashboard" link in emails — never used to
# construct a fake per-opportunity URL, only the app's own root.
FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
