"""
services/otp_service.py
Single 4-digit OTP sent to BOTH email and phone simultaneously.
Verifying one is sufficient to proceed.
"""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.config import config
from app.models.otp import OTPRecord, OTPChannel, OTPStatus
from app.models.log import LogEvent
from app.utils.security import generate_otp, hash_otp, verify_otp_hash
from app.utils.helpers import new_uuid, utc_now, write_log
from app.services.email_service import send_otp_email
from app.services.sms_service import send_otp_sms

logger = logging.getLogger(__name__)


class OTPError(Exception):
    def __init__(self, message: str, code: str = "OTP_ERROR"):
        super().__init__(message)
        self.code = code


def _invalidate_pending(db: Session, user_id: str):
    """Expire all pending OTP records for this user regardless of channel."""
    db.query(OTPRecord).filter(
        OTPRecord.user_id == user_id,
        OTPRecord.status  == OTPStatus.PENDING,
    ).update({"status": OTPStatus.EXPIRED})
    db.commit()


def _active_otp(db: Session, user_id: str) -> OTPRecord | None:
    return (
        db.query(OTPRecord)
        .filter(OTPRecord.user_id == user_id, OTPRecord.status == OTPStatus.PENDING)
        .order_by(OTPRecord.created_at.desc())
        .first()
    )


def send_otp_both_channels(db: Session, user_id: str,
                            email: str, phone: str, agency_name: str = "") -> dict:
    """
    Generate ONE 4-digit OTP and dispatch it to BOTH email AND phone.
    Invalidates any previous pending OTP first.
    """
    _invalidate_pending(db, user_id)

    otp_plain  = generate_otp()           # 4 digits (config.OTP_LENGTH = 4)
    otp_hashed = hash_otp(otp_plain)
    expires_at = utc_now() + timedelta(seconds=config.OTP_EXPIRY_SECONDS)

    record = OTPRecord(
        id          = new_uuid(),
        user_id     = user_id,
        channel     = OTPChannel.BOTH,
        destination = f"{email}|{phone}",
        otp_hash    = otp_hashed,
        status      = OTPStatus.PENDING,
        attempts    = 0,
        max_attempts= config.OTP_MAX_ATTEMPTS,
        expires_at  = expires_at,
    )
    db.add(record)
    db.commit()

    # Dispatch to both — failures are logged but don't abort (at least one must land)
    # WhatsApp goes FIRST: it is the primary channel and the one users watch.
    phone_ok = send_otp_sms(phone,  otp_plain)
    email_ok = send_otp_email(email, otp_plain, agency_name)

    if not email_ok and not phone_ok:
        logger.error("Both OTP dispatches failed user=%s", user_id)
        raise OTPError("Failed to send OTP. Please try again.", "SEND_FAILED")

    write_log(db, user_id, LogEvent.OTP_SENT, channel="both",
              detail={"email": email, "phone": phone, "record_id": record.id})

    return {
        "record_id":      record.id,
        "expires_at":     expires_at.isoformat(),
        "expiry_seconds": config.OTP_EXPIRY_SECONDS,
        "email_sent":     email_ok,
        "phone_sent":     phone_ok,
    }


def verify_otp_single(db: Session, user_id: str, submitted_otp: str) -> bool:
    """
    Verify the submitted OTP against the pending record.
    One correct OTP verifies the user regardless of which channel they received it on.
    Returns True on success, raises OTPError on failure.
    """
    record = _active_otp(db, user_id)

    if not record:
        raise OTPError("No pending OTP found. Please request a new one.", "NOT_FOUND")

    if record.is_expired:
        record.status = OTPStatus.EXPIRED
        db.commit()
        write_log(db, user_id, LogEvent.OTP_EXPIRED, channel="both")
        raise OTPError("OTP has expired. Please request a new one.", "EXPIRED")

    if record.is_exhausted:
        record.status = OTPStatus.EXHAUSTED
        db.commit()
        raise OTPError("Too many incorrect attempts. Please request a new OTP.", "EXHAUSTED")

    record.attempts += 1

    if not verify_otp_hash(submitted_otp, record.otp_hash):
        remaining = record.max_attempts - record.attempts
        db.commit()
        write_log(db, user_id, LogEvent.OTP_FAILED, channel="both",
                  detail={"attempts": record.attempts, "remaining": remaining})
        raise OTPError(f"Incorrect OTP. {remaining} attempt(s) remaining.", "WRONG_OTP")

    record.status      = OTPStatus.VERIFIED
    record.verified_at = utc_now()
    db.commit()

    write_log(db, user_id, LogEvent.OTP_VERIFIED, channel="both")
    return True


def resend_otp(db: Session, user_id: str,
               email: str, phone: str, agency_name: str = "") -> dict:
    """Resend with cooldown enforcement."""
    last = _active_otp(db, user_id)
    if last:
        now       = utc_now()
        last_sent = (last.last_resent_at or last.created_at)
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        elapsed = (now - last_sent).total_seconds()
        if elapsed < config.OTP_RESEND_COOLDOWN:
            wait = int(config.OTP_RESEND_COOLDOWN - elapsed)
            raise OTPError(f"Please wait {wait}s before resending.", "COOLDOWN")

    write_log(db, user_id, LogEvent.OTP_RESENT, channel="both",
              detail={"email": email, "phone": phone})
    return send_otp_both_channels(db, user_id, email, phone, agency_name)
