"""
services/sms_service.py — OTP delivery to the user's mobile.

WhatsApp (tesepr WAAS) is the ONLY phone channel. Twilio SMS has been
removed: the project sends OTPs over WhatsApp.

The function name send_otp_sms() is kept so otp_service.py needs no change.
"""
import logging

from app.services.waas_service import send_otp_whatsapp

logger = logging.getLogger(__name__)


def send_otp_sms(to_phone: str, otp: str) -> bool:
    """
    Deliver the OTP to the user's mobile over WhatsApp.
    Returns True on success, False on failure.

    Set WAAS_ENABLED=false in .env to print the code to the terminal
    instead of sending a real message.
    """
    ok = send_otp_whatsapp(to_phone, otp)

    if not ok:
        logger.error("WhatsApp OTP delivery failed for %s", _mask(to_phone))

    return ok


def _mask(phone: str) -> str:
    """Mask a number for logs: 9047999915 -> 90****9915."""
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    return f"{digits[:2]}****{digits[-4:]}" if len(digits) >= 6 else "**********"
