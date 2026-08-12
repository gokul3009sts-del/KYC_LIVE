"""
routes/user_routes.py
Endpoints:
  POST /api/register-and-send-otp  — Step 1: register + dispatch OTP to both channels
  POST /api/verify-otp             — Step 2: verify single 4-digit OTP
  POST /api/resend-otp             — Resend OTP (cooldown enforced)
  POST /api/login                  — Admin password login
  GET  /api/users/<id>             — Get user profile
  GET  /api/users                  — List users (admin only)
"""
from flask import Blueprint, request
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt

from app.database import get_session_factory
from app.services.user_service import (
    register_user, authenticate_user, get_user_by_id,
    mark_otp_verified, UserError,
)
from app.services.otp_service import (
    send_otp_both_channels, verify_otp_single, resend_otp, OTPError,
)
from app.utils.security import (
    is_valid_email, is_valid_phone, is_strong_password, mask_email, mask_phone,
)
from app.utils.helpers import success, error, paginate, pagination_meta
from app.middleware.auth import jwt_required_custom, admin_required, get_current_user_id
from app.models.user import UserRole

user_bp = Blueprint("users", __name__, url_prefix="/api")


def _db():
    return get_session_factory()()


# ── POST /api/register-and-send-otp ──────────────────────────
def register_and_send_otp():
    """
    Step 1 of the registration flow.
    Registers the user (no password), then sends one 4-digit OTP to
    BOTH email and phone simultaneously.
    Returns a short-lived JWT access_token so the next step can be
    authenticated.
    ---
    tags: [Registration Flow]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            required: [agency_name, owner_first_name, owner_last_name, email, phone]
            properties:
              agency_name:       {type: string}
              owner_first_name:  {type: string}
              owner_last_name:   {type: string}
              email:             {type: string, format: email}
              phone:             {type: string, example: "9876543210"}
    responses:
      200: {description: OTP dispatched, token returned}
      400: {description: Validation error}
      409: {description: Duplicate email or phone}
    """
    data = request.get_json(silent=True) or {}
    required = ["agency_name", "owner_first_name", "owner_last_name", "email", "phone"]
    missing  = [f for f in required if not data.get(f, "").strip()]
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}", 400)

    if not is_valid_email(data["email"]):
        return error("Invalid email address.", 400)
    if not is_valid_phone(data["phone"]):
        return error("Invalid mobile number. Must be a 10-digit Indian number starting with 6-9.", 400)

    db = _db()
    try:
        user   = register_user(db, data)
        result = send_otp_both_channels(
            db, user.id,
            email=data["email"].strip().lower(),
            phone=data["phone"].strip(),
            agency_name=user.agency_name,
        )

        # Issue a short-lived access token so screen 2 can call /api/verify-otp
        token = create_access_token(
            identity=user.id,
            additional_claims={"role": user.role.value},
        )

        return success({
            "access_token":      token,
            "user_id":           user.id,
            "masked_email":      mask_email(data["email"]),
            "masked_phone":      mask_phone(data["phone"]),
            "otp_expires_at":    result["expires_at"],
            "expiry_seconds":    result["expiry_seconds"],
        }, "OTP sent to your email and mobile number.")

    except OTPError as e:
        return error(str(e), 400)
    except UserError as e:
        return error(str(e), e.status)
    finally:
        db.close()


# ── POST /api/verify-otp ──────────────────────────────────────
@jwt_required_custom
def verify_otp_endpoint():
    """
    Step 2: verify the 4-digit OTP.
    Verifying ONE correct OTP marks both email and phone as verified
    and promotes the user to VERIFIED status.
    Returns a full-access JWT on success.
    ---
    tags: [Registration Flow]
    security: [{BearerAuth: []}]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            required: [otp]
            properties:
              otp: {type: string, minLength: 4, maxLength: 4}
    responses:
      200: {description: Verified — full JWT returned}
      400: {description: Wrong/expired OTP}
    """
    user_id   = get_current_user_id()
    data      = request.get_json(silent=True) or {}
    otp_plain = str(data.get("otp", "")).strip()

    if not otp_plain or len(otp_plain) != 4 or not otp_plain.isdigit():
        return error("OTP must be a 4-digit numeric code.", 400)

    db = _db()
    try:
        verify_otp_single(db, user_id, otp_plain)

        user = get_user_by_id(db, user_id)
        if user:
            mark_otp_verified(db, user)

        # Issue full-access tokens now that identity is confirmed
        claims        = {"role": user.role.value if user else "user"}
        access_token  = create_access_token(identity=user_id,  additional_claims=claims)
        refresh_token = create_refresh_token(identity=user_id, additional_claims=claims)

        return success({
            "verified":      True,
            "access_token":  access_token,
            "refresh_token": refresh_token,
            "user":          user.to_dict() if user else None,
        }, "Contact verified successfully. You may proceed to KYC.")

    except OTPError as e:
        status_code = 429 if e.code == "EXHAUSTED" else 400
        return error(str(e), status_code)
    finally:
        db.close()


# ── POST /api/resend-otp ──────────────────────────────────────
@jwt_required_custom
def resend_otp_endpoint():
    """
    Resend the shared OTP to both channels (cooldown enforced).
    ---
    tags: [Registration Flow]
    security: [{BearerAuth: []}]
    responses:
      200: {description: OTP resent}
      429: {description: Cooldown active}
    """
    user_id = get_current_user_id()
    db      = _db()
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return error("User not found.", 404)

        result = resend_otp(db, user_id, user.email, user.phone, user.agency_name)
        return success(result, "OTP resent to your email and mobile.")

    except OTPError as e:
        return error(str(e), 429 if e.code == "COOLDOWN" else 400)
    finally:
        db.close()


# ── POST /api/login (admin / password login) ──────────────────
def login():
    """Password-based login for admin accounts."""
    data     = request.get_json(silent=True) or {}
    email    = data.get("email",    "").strip()
    password = data.get("password", "")

    if not email or not password:
        return error("Email and password are required.", 400)

    db = _db()
    try:
        user   = authenticate_user(db, email, password)
        claims = {"role": user.role.value}
        return success({
            "access_token":  create_access_token(identity=user.id,  additional_claims=claims),
            "refresh_token": create_refresh_token(identity=user.id, additional_claims=claims),
            "user":          user.to_dict(),
        }, "Login successful.")
    except UserError as e:
        return error(str(e), e.status)
    finally:
        db.close()


# ── GET /api/users/<id> ───────────────────────────────────────
@jwt_required_custom
def get_user(user_id: str):
    current_id = get_current_user_id()
    claims     = get_jwt()
    is_admin   = claims.get("role") == UserRole.ADMIN.value
    if current_id != user_id and not is_admin:
        return error("Access denied.", 403)
    db = _db()
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return error("User not found.", 404)
        return success(user.to_dict(include_sensitive=is_admin))
    finally:
        db.close()


# ── GET /api/users (admin) ────────────────────────────────────
@admin_required
def list_users():
    from app.models.user import User, UserStatus
    db = _db()
    try:
        page          = max(1, int(request.args.get("page", 1)))
        per_page      = min(100, max(1, int(request.args.get("per_page", 20))))
        status_filter = request.args.get("status")
        search        = request.args.get("search", "").strip()

        q = db.query(User)
        if status_filter:
            try:
                q = q.filter(User.status == UserStatus(status_filter))
            except ValueError:
                return error(f"Invalid status: {status_filter}", 400)
        if search:
            q = q.filter(
                User.email.ilike(f"%{search}%") |
                User.agency_name.ilike(f"%{search}%") |
                User.phone.ilike(f"%{search}%")
            )
        q = q.order_by(User.created_at.desc())
        items, total, pages = paginate(q, page, per_page)
        return success({
            "users":      [u.to_dict() for u in items],
            "pagination": pagination_meta(page, per_page, total, pages),
        })
    finally:
        db.close()


# ── Register ──────────────────────────────────────────────────
user_bp.add_url_rule("/register-and-send-otp", view_func=register_and_send_otp, methods=["POST"])
user_bp.add_url_rule("/verify-otp",            view_func=verify_otp_endpoint,   methods=["POST"])
user_bp.add_url_rule("/resend-otp",            view_func=resend_otp_endpoint,   methods=["POST"])
user_bp.add_url_rule("/login",                 view_func=login,                 methods=["POST"])
user_bp.add_url_rule("/users/<user_id>",       view_func=get_user,              methods=["GET"])
user_bp.add_url_rule("/users",                 view_func=list_users,            methods=["GET"])
