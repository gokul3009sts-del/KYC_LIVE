"""
services/waas_service.py — Send OTP over WhatsApp via the tesepr WAAS API.

Endpoint (no authentication header — the JSON body is the whole request):

    POST https://cpanel.tesepr.com/WEBAPI/api/Waas/WAASAgentMessageSend

    {
        "To": "9047999915",
        "MapId": "20260316103903",
        "Header": "",
        "FileName": "",
        "Product": "",
        "Variable": ["7896"],
        "Button": []
    }

"Variable" holds the template placeholders. This project's template has a
single placeholder: the OTP.

Configuration (.env):
    WAAS_ENABLED   true  -> send real WhatsApp messages
                   false -> dev mode, the OTP is printed to the terminal
    WAAS_API_URL   endpoint override (a working default is built in)
    WAAS_MAP_ID    approved template id — 20260316103903
"""
import logging

import requests

from app.config import config

logger = logging.getLogger(__name__)

API_URL = "https://cpanel.tesepr.com/WEBAPI/api/Waas/WAASAgentMessageSend"
MAP_ID  = "20260316103903"
TIMEOUT_SECONDS = 20


def send_otp_whatsapp(to_phone: str, otp: str) -> bool:
    """
    Send an OTP over WhatsApp. Returns True on success, False on failure.

    When WAAS_ENABLED is false the code is printed to the terminal instead,
    so local development needs no live credentials.
    """
    msisdn = _to_local_10_digit(to_phone)

    if not msisdn:
        logger.error("WAAS: unusable phone number %r — OTP not sent", to_phone)
        return False

    # ── Dev mode ────────────────────────────────────────────
    if not config.WAAS_ENABLED:
        if config.DEBUG:
            print(f"\n{'=' * 45}")
            print(f"  WHATSAPP OTP  →  {msisdn}")
            print(f"  CODE          →  {otp}")
            print(f"  (dev mode — set WAAS_ENABLED=true to send)")
            print(f"{'=' * 45}\n")
            return True
        logger.error(
            "WhatsApp OTP not sent to %s — WAAS_ENABLED is false. "
            "Set WAAS_ENABLED=true before going live.", _mask(msisdn),
        )
        return False

    payload = build_payload(msisdn, otp)

    try:
        response = requests.post(
            getattr(config, "WAAS_API_URL", None) or API_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=TIMEOUT_SECONDS,
        )

        ok = response.status_code == 200 and _looks_successful(response)

        # One-line result, not the raw vendor payload — enough to diagnose
        # a failure without dumping response bodies into production logs.
        if ok:
            logger.info("WAAS OTP delivered to %s", _mask(msisdn))
        else:
            logger.error(
                "WAAS OTP failed for %s — HTTP %s: %s",
                _mask(msisdn), response.status_code, (response.text or "")[:200],
            )
        return ok

    except requests.exceptions.Timeout:
        logger.error("WAAS: timed out after %ss for %s", TIMEOUT_SECONDS, _mask(msisdn))
        return False
    except requests.exceptions.RequestException as exc:
        logger.error("WAAS: request failed for %s: %s", _mask(msisdn), exc)
        return False


def build_payload(msisdn: str, otp: str) -> dict:
    """The exact body the WAAS endpoint expects. Separated so it can be tested."""
    return {
        "To":       msisdn,
        "MapId":    getattr(config, "WAAS_MAP_ID", None) or MAP_ID,
        "Header":   "",
        "FileName": "",
        "Product":  "",
        "Variable": [str(otp)],
        "Button":   [],
    }


def _looks_successful(response) -> bool:
    """
    Decide whether the vendor actually accepted the message.

    This endpoint returns HTTP 200 even when a send fails, so the body has
    to be inspected. The observed success reply is:

        {"strError": "Message Sent Successfully", "strStatus": "01", ...}

    strStatus "01" means accepted; anything else is a failure, and
    strError carries the reason.
    """
    try:
        data = response.json()
    except ValueError:
        return True                      # 200 with a non-JSON body

    if not isinstance(data, dict):
        return True

    # This vendor's own flag takes priority.
    if "strStatus" in data:
        ok = str(data.get("strStatus", "")).strip() == "01"
        if not ok:
            logger.error("WAAS rejected the message: strStatus=%r strError=%r",
                         data.get("strStatus"), data.get("strError"))
        return ok

    # Fallbacks for other response shapes.
    for key in ("ResultCode", "resultCode", "Status", "status",
                "Success", "success", "IsSuccess"):
        if key in data:
            value = data[key]
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "01", "true", "success", "ok"}

    return True


def _to_local_10_digit(phone: str) -> str:
    """
    The API wants a bare 10-digit Indian number ("9047999915"), not E.164.
    Strips +, a 91 country prefix, a leading 0, spaces and dashes.
    Returns "" if the result isn't exactly 10 digits.
    """
    if not phone:
        return ""

    digits = "".join(ch for ch in str(phone) if ch.isdigit())

    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    return digits if len(digits) == 10 else ""


def _mask(msisdn: str) -> str:
    """Mask a number for logs: 9047999915 -> 90****9915."""
    return f"{msisdn[:2]}****{msisdn[-4:]}" if len(msisdn) == 10 else "**********"
