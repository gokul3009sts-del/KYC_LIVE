"""
routes/otp_routes.py — OTP send, verify, resend endpoints.
"""
from flask import Blueprint, request
from app.database import get_session_factory
from app.services.otp_service import send_otp, verify_otp, resend_otp, OTPError
from app.services.user_service import get_user_by_id, mark_channel_verified, UserError
from app.utils.security import is_valid_email, is_valid_phone, mask_email, mask_phone
from app.utils.helpers import success, error
from app.middleware.auth import jwt_required_custom, get_current_user_id

otp_bp = Blueprint("otp", __name__, url_prefix="/api")


def _db():
    return get_session_factory()()  # type: ignore


# ── POST /api/send-otp/email ──────────────────────────────────

@jwt_required_custom
def send_email_otp():
    """
    Send OTP to the authenticated user's email.
    ---
    tags: [OTP Workflow]
    security: [{BearerAuth: []}]
    requestBody:
      content:
        application/json:
          schema:
            properties:
              email: {type: string, format: email}
    responses:
      200: {description: OTP sent}
      400: {description: Validation error}
    """
    user_id = get_current_user_id()
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()

    if not email or not is_valid_email(email):
        return error("A valid email address is required.", 400)

    db = _db()
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return error("User not found.", 404)

        result = send_otp(db, user_id, "email", email, user.agency_name)
        return success(
            {"masked_destination": mask_email(email), **result},
            "OTP sent to your email address.",
        )
    except OTPError as e:
        return error(str(e), 400)
    finally:
        db.close()


# ── POST /api/send-otp/phone ──────────────────────────────────

@jwt_required_custom
def send_phone_otp():
    """
    Send OTP to the authenticated user's mobile number.
    ---
    tags: [OTP Workflow]
    security: [{BearerAuth: []}]
    requestBody:
      content:
        application/json:
          schema:
            properties:
              phone: {type: string, example: "9876543210"}
    responses:
      200: {description: OTP sent}
    """
    user_id = get_current_user_id()
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "").strip()

    if not phone or not is_valid_phone(phone):
        return error("A valid 10-digit Indian mobile number is required.", 400)

    db = _db()
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return error("User not found.", 404)

        result = send_otp(db, user_id, "phone", phone, user.agency_name)
        return success(
            {"masked_destination": mask_phone(phone), **result},
            "OTP sent to your mobile number.",
        )
    except OTPError as e:
        return error(str(e), 400)
    finally:
        db.close()


# ── POST /api/verify-otp ──────────────────────────────────────

@jwt_required_custom
def verify_otp_endpoint():
    """
    Verify OTP for a given channel (email or phone).
    ---
    tags: [OTP Workflow]
    security: [{BearerAuth: []}]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            required: [channel, otp]
            properties:
              channel: {type: string, enum: [email, phone]}
              otp:     {type: string, minLength: 6, maxLength: 6}
    responses:
      200: {description: OTP verified}
      400: {description: Wrong or expired OTP}
    """
    user_id = get_current_user_id()
    data = request.get_json(silent=True) or {}
    channel = data.get("channel", "").strip()
    otp_plain = str(data.get("otp", "")).strip()

    if channel not in ("email", "phone"):
        return error("channel must be 'email' or 'phone'.", 400)
    if not otp_plain or len(otp_plain) != 6 or not otp_plain.isdigit():
        return error("OTP must be a 6-digit numeric code.", 400)

    db = _db()
    try:
        verify_otp(db, user_id, channel, otp_plain)
        user = get_user_by_id(db, user_id)
        if user:
            mark_channel_verified(db, user, channel)
        return success(
            {"channel": channel, "verified": True},
            f"{channel.capitalize()} verified successfully.",
        )
    except OTPError as e:
        return error(str(e), 400)
    finally:
        db.close()


# ── POST /api/resend-otp ──────────────────────────────────────

@jwt_required_custom
def resend_otp_endpoint():
    """
    Resend OTP (subject to cooldown).
    ---
    tags: [OTP Workflow]
    security: [{BearerAuth: []}]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            required: [channel]
            properties:
              channel:     {type: string, enum: [email, phone]}
              email:       {type: string}
              phone:       {type: string}
    responses:
      200: {description: OTP resent}
      429: {description: Cooldown not elapsed}
    """
    user_id = get_current_user_id()
    data = request.get_json(silent=True) or {}
    channel = data.get("channel", "").strip()

    if channel not in ("email", "phone"):
        return error("channel must be 'email' or 'phone'.", 400)

    db = _db()
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return error("User not found.", 404)

        destination = data.get("email" if channel == "email" else "phone", "").strip()
        if not destination:
            destination = user.email if channel == "email" else user.phone

        result = resend_otp(db, user_id, channel, destination, user.agency_name)
        return success(result, f"OTP resent to your {channel}.")
    except OTPError as e:
        status_code = 429 if e.code == "COOLDOWN" else 400
        return error(str(e), status_code)
    finally:
        db.close()


# ── Register ──────────────────────────────────────────────────
otp_bp.add_url_rule("/send-otp/email", view_func=send_email_otp, methods=["POST"])
otp_bp.add_url_rule("/send-otp/phone", view_func=send_phone_otp, methods=["POST"])
otp_bp.add_url_rule("/verify-otp", view_func=verify_otp_endpoint, methods=["POST"])
otp_bp.add_url_rule("/resend-otp", view_func=resend_otp_endpoint, methods=["POST"])
