"""
middleware/auth.py — JWT helpers and role-based access decorators.
"""
import logging
from functools import wraps
from flask import g, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt

from app.models.user import UserRole

logger = logging.getLogger(__name__)


def jwt_required_custom(fn):
    """Wrap a route to require a valid access token."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception as exc:
            return jsonify({"success": False, "message": str(exc)}), 401
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    """Require authenticated user with admin role."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("role") != UserRole.ADMIN.value:
                return jsonify({"success": False, "message": "Admin access required."}), 403
        except Exception as exc:
            return jsonify({"success": False, "message": str(exc)}), 401
        return fn(*args, **kwargs)
    return wrapper


def get_current_user_id() -> str:
    return get_jwt_identity()


def get_current_role() -> str:
    return get_jwt().get("role", "user")
