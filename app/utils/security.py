"""
utils/security.py — Password hashing, OTP generation, input sanitisation.
"""
import secrets
import string
import bcrypt
import re
from app.config import config


# ── Password ──────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Return bcrypt hash of the password."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Check plaintext password against stored bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── OTP ───────────────────────────────────────────────────────

def generate_otp(length: int | None = None) -> str:
    """Generate a cryptographically-secure numeric OTP."""
    n = length or config.OTP_LENGTH
    return "".join(secrets.choice(string.digits) for _ in range(n))


def hash_otp(otp: str) -> str:
    """Hash OTP with bcrypt for secure storage."""
    return bcrypt.hashpw(otp.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_otp_hash(plain_otp: str, hashed: str) -> bool:
    """Verify submitted OTP against stored hash."""
    return bcrypt.checkpw(plain_otp.encode(), hashed.encode())


# ── Validation helpers ────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_PHONE_RE = re.compile(r"^[6-9]\d{9}$")   # Indian 10-digit mobile

def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


def is_valid_phone(phone: str) -> bool:
    return bool(_PHONE_RE.match(phone.strip()))


def is_strong_password(password: str) -> tuple[bool, str]:
    """
    Enforce password policy:
      - min 8 characters
      - at least 1 uppercase, 1 lowercase, 1 digit, 1 special char
    Returns (ok, reason).
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[^a-zA-Z0-9]", password):
        return False, "Password must contain at least one special character."
    return True, ""


def mask_email(email: str) -> str:
    user, domain = email.split("@", 1)
    return user[:2] + "****@" + domain


def mask_phone(phone: str) -> str:
    return "******" + phone[-4:]
