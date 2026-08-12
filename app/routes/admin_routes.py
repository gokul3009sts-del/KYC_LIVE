"""
routes/admin_routes.py — Admin dashboard: users, logs, statistics.
All routes require admin JWT.
"""
from flask import Blueprint, request
from sqlalchemy import func, case

from app.database import get_session_factory
from app.models.user import User, UserStatus, UserRole
from app.models.otp import OTPRecord, OTPStatus, OTPChannel
from app.models.log import VerificationLog, LogEvent
from app.utils.helpers import success, error, paginate, pagination_meta
from app.middleware.auth import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _db():
    return get_session_factory()()  # type: ignore


# ── GET /api/admin/users ──────────────────────────────────────

@admin_required
def admin_list_users():
    """
    Paginated list of all users with filters.
    ---
    tags: [Admin Dashboard]
    security: [{BearerAuth: []}]
    parameters:
      - {in: query, name: status, schema: {type: string, enum: [pending, verified, kyc_submitted, active, suspended]}}
      - {in: query, name: email_verified, schema: {type: boolean}}
      - {in: query, name: phone_verified, schema: {type: boolean}}
      - {in: query, name: search, schema: {type: string}}
      - {in: query, name: page, schema: {type: integer, default: 1}}
      - {in: query, name: per_page, schema: {type: integer, default: 20}}
    responses:
      200: {description: Filtered user list with pagination}
    """
    db = _db()
    try:
        page     = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
        search   = request.args.get("search", "").strip()
        status   = request.args.get("status", "").strip()
        ev       = request.args.get("email_verified", "").lower()
        pv       = request.args.get("phone_verified", "").lower()

        q = db.query(User)

        if status:
            try:
                q = q.filter(User.status == UserStatus(status))
            except ValueError:
                return error(f"Invalid status '{status}'.", 400)

        if ev in ("true", "false"):
            q = q.filter(User.email_verified == (ev == "true"))
        if pv in ("true", "false"):
            q = q.filter(User.phone_verified == (pv == "true"))

        if search:
            q = q.filter(
                User.email.ilike(f"%{search}%") |
                User.agency_name.ilike(f"%{search}%") |
                User.phone.ilike(f"%{search}%") |
                User.owner_first_name.ilike(f"%{search}%") |
                User.owner_last_name.ilike(f"%{search}%")
            )

        q = q.order_by(User.created_at.desc())
        items, total, pages = paginate(q, page, per_page)

        return success({
            "users": [u.to_dict(include_sensitive=True) for u in items],
            "pagination": pagination_meta(page, per_page, total, pages),
        })
    finally:
        db.close()


# ── GET /api/admin/logs ───────────────────────────────────────

@admin_required
def admin_logs():
    """
    Audit log viewer with filters.
    ---
    tags: [Admin Dashboard]
    security: [{BearerAuth: []}]
    parameters:
      - {in: query, name: event, schema: {type: string}}
      - {in: query, name: user_id, schema: {type: string}}
      - {in: query, name: channel, schema: {type: string, enum: [email, phone]}}
      - {in: query, name: page, schema: {type: integer, default: 1}}
      - {in: query, name: per_page, schema: {type: integer, default: 50}}
    responses:
      200: {description: Log entries}
    """
    db = _db()
    try:
        page     = max(1, int(request.args.get("page", 1)))
        per_page = min(200, max(1, int(request.args.get("per_page", 50))))
        event_f  = request.args.get("event", "").strip()
        user_f   = request.args.get("user_id", "").strip()
        channel_f = request.args.get("channel", "").strip()

        q = db.query(VerificationLog)
        if event_f:
            try:
                q = q.filter(VerificationLog.event == LogEvent(event_f))
            except ValueError:
                return error(f"Invalid event '{event_f}'.", 400)
        if user_f:
            q = q.filter(VerificationLog.user_id == user_f)
        if channel_f:
            q = q.filter(VerificationLog.channel == channel_f)

        q = q.order_by(VerificationLog.created_at.desc())
        items, total, pages = paginate(q, page, per_page)

        return success({
            "logs": [l.to_dict() for l in items],
            "pagination": pagination_meta(page, per_page, total, pages),
        })
    finally:
        db.close()


# ── GET /api/admin/stats ──────────────────────────────────────

@admin_required
def admin_stats():
    """
    System statistics: OTP success rate, user breakdown, recent activity.
    ---
    tags: [Admin Dashboard]
    security: [{BearerAuth: []}]
    responses:
      200: {description: Dashboard statistics}
    """
    db = _db()
    try:
        # User counts by status
        user_counts = (
            db.query(User.status, func.count(User.id))
            .group_by(User.status)
            .all()
        )
        by_status = {r[0].value: r[1] for r in user_counts}

        total_users = db.query(func.count(User.id)).scalar() or 0
        email_verified = db.query(func.count(User.id)).filter(User.email_verified == True).scalar() or 0
        phone_verified = db.query(func.count(User.id)).filter(User.phone_verified == True).scalar() or 0
        both_verified  = db.query(func.count(User.id)).filter(
            User.email_verified == True, User.phone_verified == True
        ).scalar() or 0

        # OTP stats
        total_otp  = db.query(func.count(OTPRecord.id)).scalar() or 0
        otp_ok     = db.query(func.count(OTPRecord.id)).filter(OTPRecord.status == OTPStatus.VERIFIED).scalar() or 0
        otp_failed = db.query(func.count(OTPRecord.id)).filter(OTPRecord.status == OTPStatus.EXHAUSTED).scalar() or 0
        otp_expired = db.query(func.count(OTPRecord.id)).filter(OTPRecord.status == OTPStatus.EXPIRED).scalar() or 0

        otp_success_rate = round(otp_ok / total_otp * 100, 1) if total_otp else 0.0

        # Recent 7-day registration trend
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import cast, Date
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        daily = (
            db.query(
                func.date(User.created_at).label("day"),
                func.count(User.id).label("count")
            )
            .filter(User.created_at >= week_ago)
            .group_by(func.date(User.created_at))
            .order_by(func.date(User.created_at))
            .all()
        )

        return success({
            "users": {
                "total": total_users,
                "email_verified": email_verified,
                "phone_verified": phone_verified,
                "both_verified": both_verified,
                "by_status": by_status,
            },
            "otp": {
                "total_sent": total_otp,
                "verified": otp_ok,
                "failed_attempts": otp_failed,
                "expired": otp_expired,
                "success_rate_pct": otp_success_rate,
            },
            "registrations_last_7_days": [
                {"date": str(r.day), "count": r.count} for r in daily
            ],
        })
    finally:
        db.close()


# ── GET /api/admin/users/<id>/otp-records ────────────────────

@admin_required
def user_otp_records(user_id: str):
    """Return OTP history for a specific user."""
    db = _db()
    try:
        records = (
            db.query(OTPRecord)
            .filter(OTPRecord.user_id == user_id)
            .order_by(OTPRecord.created_at.desc())
            .limit(50)
            .all()
        )
        return success({"otp_records": [r.to_dict() for r in records]})
    finally:
        db.close()


# ── Register ──────────────────────────────────────────────────
admin_bp.add_url_rule("/users", view_func=admin_list_users, methods=["GET"])
admin_bp.add_url_rule("/logs", view_func=admin_logs, methods=["GET"])
admin_bp.add_url_rule("/stats", view_func=admin_stats, methods=["GET"])
admin_bp.add_url_rule("/users/<user_id>/otp-records", view_func=user_otp_records, methods=["GET"])
