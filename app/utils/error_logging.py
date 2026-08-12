"""
utils/error_logging.py — Write unhandled exceptions to the error_logs table.

Used by the 500 handler in both apps. Never raises itself — a failure to
log an error must not turn one error into two.
"""
import traceback
import logging

from flask import request

logger = logging.getLogger(__name__)


def record_error(source: str, exc: Exception, status_code: int = 500) -> None:
    """Best-effort write of an unhandled exception to error_logs."""
    try:
        # Flask's errorhandler(500) receives a generic InternalServerError
        # wrapper, not the exception that was actually raised. The real
        # one — with the real message and type — is on .original_exception.
        real_exc = getattr(exc, "original_exception", None) or exc

        from app.database import get_session_factory
        from app.models.error_log import ErrorLog
        from app.utils.helpers import new_uuid

        user_id = None
        try:
            from flask_jwt_extended import get_jwt_identity
            user_id = get_jwt_identity()
        except Exception:
            pass

        tb = "".join(traceback.format_exception(
            type(real_exc), real_exc, real_exc.__traceback__
        ))[:8000]

        db = get_session_factory()()
        try:
            db.add(ErrorLog(
                id=new_uuid(),
                source=source,
                method=request.method if request else None,
                path=request.path if request else None,
                status_code=status_code,
                error_type=type(real_exc).__name__,
                message=str(real_exc)[:2000],
                traceback=tb,
                ip_address=request.remote_addr if request else None,
                user_id=user_id,
            ))
            db.commit()
        finally:
            db.close()
    except Exception as log_exc:
        # Logging the error must never crash the error handler itself.
        logger.error("Failed to write to error_logs: %s", log_exc)
