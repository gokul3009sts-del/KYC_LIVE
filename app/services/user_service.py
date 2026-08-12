"""
services/user_service.py — Registration, OTP-based auth, KYC.
No password required in the standard registration flow.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.user import User, UserRole, UserStatus
from app.models.log import LogEvent
from app.utils.security import hash_password, verify_password
from app.utils.helpers import new_uuid, utc_now, write_log

logger = logging.getLogger(__name__)


class UserError(Exception):
    def __init__(self, message: str, code: str = "USER_ERROR", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def register_user(db: Session, data: dict) -> User:
    """
    Create user account — NO password required.
    email + phone uniqueness enforced.
    """
    email = data["email"].strip().lower()
    phone = data["phone"].strip()

    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email:
        # If already registered but not yet OTP-verified, allow re-use (resend OTP)
        if existing_email.status == UserStatus.PENDING and not existing_email.otp_verified:
            return existing_email
        raise UserError("An account with this email already exists.", "EMAIL_EXISTS", 409)

    existing_phone = db.query(User).filter(User.phone == phone).first()
    if existing_phone:
        if existing_phone.status == UserStatus.PENDING and not existing_phone.otp_verified:
            return existing_phone
        raise UserError("An account with this mobile number already exists.", "PHONE_EXISTS", 409)

    user = User(
        id=new_uuid(),
        agency_name=data["agency_name"].strip(),
        owner_first_name=data["owner_first_name"].strip(),
        owner_last_name=data["owner_last_name"].strip(),
        email=email,
        phone=phone,
        password_hash=None,   # passwordless flow
        role=UserRole.USER,
        status=UserStatus.PENDING,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    write_log(db, user.id, LogEvent.REGISTER, detail={"email": email})
    logger.info("New user registered (passwordless): %s", email)
    return user


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.strip().lower()).first()


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Admin login only — requires password_hash set."""
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise UserError("Invalid email or password.", "INVALID_CREDENTIALS", 401)
    if user.status == UserStatus.SUSPENDED:
        raise UserError("Account suspended. Contact support.", "SUSPENDED", 403)
    user.last_login_at = utc_now()
    db.commit()
    write_log(db, user.id, LogEvent.LOGIN, detail={"email": email})
    return user


def mark_otp_verified(db: Session, user: User):
    """
    Called once ANY single OTP is validated successfully.
    Marks both channels as verified (single shared OTP confirms identity).
    Promotes status from PENDING → VERIFIED.
    """
    user.otp_verified   = True
    user.email_verified = True
    user.phone_verified = True
    if user.status == UserStatus.PENDING:
        user.status = UserStatus.VERIFIED
    db.commit()


def update_kyc(db: Session, user: User, kyc_payload: dict):
    import json
    user.kyc_data = json.dumps(kyc_payload)
    user.status   = UserStatus.KYC_SUBMITTED
    db.commit()
    write_log(db, user.id, LogEvent.KYC_SUBMITTED)
