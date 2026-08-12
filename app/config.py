"""config.py — Centralised configuration."""
import os
from datetime import timedelta
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()


def _pg_driver() -> str:
    """
    Pick whichever PostgreSQL driver is installed.

    psycopg2 is the usual one. psycopg (v3) is the fallback, which matters
    on very new Python versions where psycopg2 wheels may lag. Set
    DB_DRIVER in .env to force a specific one.
    """
    forced = os.getenv("DB_DRIVER", "").strip()
    if forced:
        return forced
    try:
        import psycopg2  # noqa: F401
        return "psycopg2"
    except ImportError:
        pass
    try:
        import psycopg  # noqa: F401
        return "psycopg"
    except ImportError:
        pass
    return "psycopg2"          # let SQLAlchemy raise a clear error


class Config:
    SECRET_KEY  = os.getenv("SECRET_KEY",  "change-this-secret-key")
    DEBUG       = os.getenv("FLASK_ENV", "development") == "development"

    DB_HOST     = os.getenv("DB_HOST",     "localhost")
    DB_PORT     = int(os.getenv("DB_PORT", 5432))
    DB_NAME     = os.getenv("DB_NAME",     "nbaworld_db")
    DB_USER     = os.getenv("DB_USER",     "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    @property
    def SQLALCHEMY_DATABASE_URI(self):
        return (
            f"postgresql+{_pg_driver()}://{quote_plus(self.DB_USER)}:{quote_plus(self.DB_PASSWORD)}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}

    JWT_SECRET_KEY             = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES   = timedelta(minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", 120)))
    JWT_REFRESH_TOKEN_EXPIRES  = timedelta(days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES_DAYS", 30)))
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME    = "Authorization"
    JWT_HEADER_TYPE    = "Bearer"

    # 4-digit OTP for this UI
    OTP_LENGTH           = int(os.getenv("OTP_LENGTH",                4))
    OTP_EXPIRY_SECONDS   = int(os.getenv("OTP_EXPIRY_SECONDS",      300))
    OTP_MAX_ATTEMPTS     = int(os.getenv("OTP_MAX_ATTEMPTS",           5))
    OTP_RESEND_COOLDOWN  = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", 30))

    SMTP_HOST     = os.getenv("SMTP_HOST",     "smtp.gmail.com")
    SMTP_PORT     = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER     = os.getenv("SMTP_USER",     "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM    = os.getenv("EMAIL_FROM",    "NBAWORLD.IN <no-reply@nbaworld.in>")

    # ── WhatsApp OTP (tesepr WAAS) — the ONLY phone channel ───
    # Defaults are live, so OTPs send even if .env is missing.
    # Set WAAS_ENABLED=false to print the code to the terminal instead.
    WAAS_ENABLED = os.getenv("WAAS_ENABLED", "true").strip().lower() in {"1", "true", "yes"}
    WAAS_API_URL = os.getenv("WAAS_API_URL",
                             "https://cpanel.tesepr.com/WEBAPI/api/Waas/WAASAgentMessageSend")
    WAAS_MAP_ID  = os.getenv("WAAS_MAP_ID", "20260316103903")   # approved template

    TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID",  "")
    TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN",   "")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

    # Comma-separated list of allowed frontend origins, e.g.
    #   ALLOWED_ORIGINS=https://nbaworld.in,https://www.nbaworld.in
    # "*" (the default) allows any origin — fine for local testing,
    # but should be locked down before going live.
    ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]

    RATELIMIT_DEFAULT   = os.getenv("RATELIMIT_DEFAULT",  "200 per day;50 per hour")
    RATELIMIT_OTP_SEND  = os.getenv("RATELIMIT_OTP_SEND", "5 per 10 minutes")
    RATELIMIT_LOGIN     = os.getenv("RATELIMIT_LOGIN",    "10 per minute")
    RATELIMIT_STORAGE_URL = "memory://"

    ADMIN_DEFAULT_EMAIL    = os.getenv("ADMIN_DEFAULT_EMAIL",    "admin@nbaworld.in")
    ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "Admin@123!")


config = Config()
