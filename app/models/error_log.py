"""
models/error_log.py — Server-side error log.

Purpose: once this runs on a real host, nobody is watching the terminal.
Unhandled exceptions (500s) are written here so they can be reviewed
from the admin panel instead of SSH-ing in to read log files.

Shared table — both apps write to it and the admin app reads it.
"""
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Text, Integer

from app.database import Base


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(String(36), primary_key=True)

    # Which app logged this — "user" (port 5000) or "admin" (port 5001).
    source = Column(String(10), nullable=False, index=True)

    method = Column(String(10), nullable=True)      # GET / POST / ...
    path = Column(String(500), nullable=True)        # request path
    status_code = Column(Integer, nullable=True)      # usually 500

    error_type = Column(String(200), nullable=True)   # exception class name
    message = Column(Text, nullable=True)             # str(exception)
    traceback = Column(Text, nullable=True)            # full traceback text

    ip_address = Column(String(45), nullable=True)
    user_id = Column(String(36), nullable=True)        # if known at time of error

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        nullable=False, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "error_type": self.error_type,
            "message": self.message,
            "traceback": self.traceback,
            "ip_address": self.ip_address,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
