"""
utils/helpers.py — Shared response builders, UUID generation, logging helper.
"""
import uuid
import json
from datetime import datetime, timezone
from flask import request, jsonify
from typing import Any


def new_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── Standardised API responses ────────────────────────────────

def success(data: Any = None, message: str = "Success", status_code: int = 200):
    body = {"success": True, "message": message}
    if data is not None:
        body["data"] = data
    return jsonify(body), status_code


def error(message: str, status_code: int = 400, errors: list | None = None):
    body = {"success": False, "message": message}
    if errors:
        body["errors"] = errors
    return jsonify(body), status_code


# ── Pagination ────────────────────────────────────────────────

def paginate(query, page: int, per_page: int):
    """
    Apply LIMIT/OFFSET to a SQLAlchemy query.
    Returns (items, total, pages).
    """
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    pages = (total + per_page - 1) // per_page
    return items, total, pages


def pagination_meta(page: int, per_page: int, total: int, pages: int) -> dict:
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1,
    }


# ── Request context helpers ───────────────────────────────────

def get_client_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()


def get_user_agent() -> str:
    return request.headers.get("User-Agent", "")[:512]


# ── Audit log writer ──────────────────────────────────────────

def write_log(db, user_id: str | None, event, channel: str | None = None, detail: dict | None = None):
    """Persist a VerificationLog row. Import here to avoid circular imports."""
    from app.models.log import VerificationLog
    log = VerificationLog(
        id=new_uuid(),
        user_id=user_id,
        event=event,
        channel=channel,
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
        detail=json.dumps(detail) if detail else None,
    )
    db.add(log)
    db.commit()
