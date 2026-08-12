"""
routes/auth_routes.py — Token refresh and logout.
"""
from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    get_jwt_identity, get_jwt,
    verify_jwt_in_request,
)
from app.database import get_session_factory
from app.utils.helpers import success, error, write_log
from app.models.log import LogEvent

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# In production, store invalidated JTIs in Redis / DB. Here we use an in-process set.
_blocklist: set[str] = set()


def _db():
    return get_session_factory()()  # type: ignore


# ── POST /api/auth/refresh-token ──────────────────────────────

def refresh_token():
    """
    Obtain a new access token using a valid refresh token.
    ---
    tags: [Security]
    security: [{BearerAuth: []}]
    responses:
      200: {description: New access token issued}
      401: {description: Invalid or expired refresh token}
    """
    try:
        verify_jwt_in_request(refresh=True)
    except Exception as exc:
        return error(str(exc), 401)

    identity = get_jwt_identity()
    claims = get_jwt()
    jti = claims.get("jti")

    if jti in _blocklist:
        return error("Token has been revoked.", 401)

    new_access = create_access_token(
        identity=identity,
        additional_claims={"role": claims.get("role", "user")},
    )

    db = _db()
    try:
        write_log(db, identity, LogEvent.TOKEN_REFRESHED)
    finally:
        db.close()

    return success({"access_token": new_access}, "Token refreshed.")


# ── POST /api/auth/logout ─────────────────────────────────────

def logout():
    """
    Revoke the current access token (add JTI to blocklist).
    ---
    tags: [Security]
    security: [{BearerAuth: []}]
    responses:
      200: {description: Logged out}
    """
    try:
        verify_jwt_in_request()
        claims = get_jwt()
        jti = claims.get("jti")
        user_id = get_jwt_identity()
        if jti:
            _blocklist.add(jti)

        db = _db()
        try:
            write_log(db, user_id, LogEvent.LOGOUT)
        finally:
            db.close()

        return success(message="Logged out successfully.")
    except Exception as exc:
        return error(str(exc), 401)


auth_bp.add_url_rule("/refresh-token", view_func=refresh_token, methods=["POST"])
auth_bp.add_url_rule("/logout", view_func=logout, methods=["POST"])
