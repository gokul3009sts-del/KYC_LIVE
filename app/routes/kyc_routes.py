"""
routes/kyc_routes.py

KYC submission flow:
    POST /api/kyc/submit
        1. Validate logged-in user
        2. Read KYC form
        3. Read PAN/GST from the dynamic document fields
        4. Save uploaded documents
        5. Save KYC data into local database
        6. Call NBA World Agency Creation API
        7. Save returned AgentID/API result
        8. Return result to frontend

    GET /api/kyc/<user_id>
        User can view own KYC; admin can view any KYC.

    GET /api/admin/kyc
        Admin list of KYC.

    POST /api/kyc/submission-confirmation
        Send confirmation email.
"""

import os
import logging

from flask import Blueprint, request, current_app
from werkzeug.utils import secure_filename

from app.database import get_session_factory
from app.services.user_service import get_user_by_id, update_kyc
from app.services.external_kyc_api import send_kyc_to_external
from app.utils.helpers import success, error, new_uuid
from app.middleware.auth import (
    jwt_required_custom,
    admin_required,
    get_current_user_id,
)
from app.models.kyc_details import KYCDetails

logger = logging.getLogger(__name__)

kyc_bp = Blueprint("kyc", __name__, url_prefix="/api")

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}
MAX_FILE_SIZE = 5 * 1024 * 1024


def _db():
    return get_session_factory()()


def _allowed(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def _clean(value):
    """Convert empty/whitespace values to None."""
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None


def _form_value(form, *names):
    """Return the first non-empty value among the supplied form names."""
    for name in names:
        value = _clean(form.get(name))
        if value is not None:
            return value
    return None


def _find_dynamic_document_number(form, suffixes):
    """
    The frontend creates document-number inputs dynamically.

    Examples from the current frontend:
        sole_gst_owner_pan_num
        sole_gst_gst_num
        sole_no_gst_owner_pan_num
        pvt_ltd_agency_pan_num
        partnership_non_llp_gst_num

    Return the first matching non-empty value.
    """
    for key in form.keys():
        key_lower = key.lower()
        if any(key_lower.endswith(suffix) for suffix in suffixes):
            value = _clean(form.get(key))
            if value is not None:
                return value
    return None


def _get_pan_number(form):
    # Support both a future simple field and the current dynamic fields.
    value = _form_value(form, "pan_number")
    if value:
        return value.upper()

    value = _find_dynamic_document_number(
        form,
        (
            "_owner_pan_num",
            "_agency_pan_num",
            "_pan_num",
        ),
    )
    return value.upper() if value else None


def _get_gst_number(form):
    # Support both a future simple field and the current dynamic field.
    value = _form_value(form, "gst_number")
    if value:
        return value.upper()

    value = _find_dynamic_document_number(
        form,
        (
            "_gst_num",
        ),
    )
    return value.upper() if value else None


# ============================================================
# POST /api/kyc/submit
# ============================================================

@jwt_required_custom
def submit_kyc():
    """
    Submit KYC using multipart/form-data.

    Panel A:
        agency_name
        owner_first_name
        owner_last_name
        email
        phone

    Panel B:
        authorised_first
        authorised_last
        designation
        landline
        iata_status
        iata_number
        country
        state
        city
        postal
        office_address
        sales_person

    Panel C:
        business_type

    Dynamic document numbers:
        sole_gst_owner_pan_num
        sole_gst_gst_num
        sole_no_gst_owner_pan_num
        pvt_ltd_agency_pan_num
        partnership_non_llp_agency_pan_num
        partnership_non_llp_gst_num
        etc.
    """

    user_id = get_current_user_id()
    db = _db()

    try:
        # ====================================================
        # 1. FIND USER
        # ====================================================
        user = get_user_by_id(db, user_id)
        if not user:
            return error("User not found.", 404)

        # ====================================================
        # 2. CHECK OTP
        # ====================================================
        if not user.otp_verified:
            return error(
                "OTP verification required before KYC submission.",
                403,
            )

        # ====================================================
        # 3. READ FORM
        # ====================================================
        f = request.form

        logger.info(
            "KYC form received. user_id=%s fields=%s",
            user_id,
            list(f.keys()),
        )

        # ====================================================
        # 4. REQUIRED FIELDS
        # ====================================================
        required_fields = [
            "authorised_first",
            "authorised_last",
            "designation",
            "iata_status",
            "country",
            "state",
            "city",
            "postal",
            "office_address",
            "business_type",
        ]

        missing = []
        for field in required_fields:
            if not _clean(f.get(field)):
                missing.append(field)

        if missing:
            return error(
                "Missing required fields: " + ", ".join(missing),
                400,
            )

        # ====================================================
        # 5. PANEL A
        # ====================================================
        agency_name = _form_value(
            f, "agency_name"
        ) or _clean(user.agency_name)

        owner_first_name = _form_value(
            f, "owner_first_name"
        ) or _clean(user.owner_first_name)

        owner_last_name = _form_value(
            f, "owner_last_name"
        ) or _clean(user.owner_last_name)

        email = _form_value(f, "email") or _clean(user.email)
        phone = _form_value(f, "phone") or _clean(user.phone)

        # ====================================================
        # 6. PAN + GST
        # ====================================================
        # IMPORTANT:
        # The current HTML does NOT send "pan_number" directly.
        # It creates names such as:
        #   sole_gst_owner_pan_num
        #   sole_gst_gst_num
        # Therefore we explicitly read those dynamic names.
        pan_number = _get_pan_number(f)
        gst_number = _get_gst_number(f)

        logger.info(
            "KYC PAN/GST received. user_id=%s PAN=%s GST=%s",
            user_id,
            pan_number,
            gst_number,
        )

        # ====================================================
        # 7. DOCUMENT FOLDER
        # ====================================================
        base_dir = os.path.join(
            current_app.root_path,
            "..",
            "KYC Documents",
            user_id,
        )
        base_dir = os.path.abspath(base_dir)
        os.makedirs(base_dir, exist_ok=True)

        doc_folder_path = os.path.join(
            "KYC Documents",
            user_id,
        )

        # ====================================================
        # 8. SAVE UPLOADED FILES
        # ====================================================
        saved_files = {}

        for field_name, file_obj in request.files.items():
            if not file_obj or not file_obj.filename:
                continue

            if not _allowed(file_obj.filename):
                return error(
                    f"File '{file_obj.filename}' has an unsupported format. "
                    "Allowed: JPG, JPEG, PNG, PDF.",
                    400,
                )

            file_obj.seek(0, 2)
            size = file_obj.tell()
            file_obj.seek(0)

            if size > MAX_FILE_SIZE:
                return error(
                    f"File '{file_obj.filename}' exceeds the 5 MB limit.",
                    400,
                )

            original_name = secure_filename(file_obj.filename)
            saved_name = f"{field_name}__{original_name}"
            save_path = os.path.join(base_dir, saved_name)

            file_obj.save(save_path)
            saved_files[field_name] = saved_name

            logger.info("Saved KYC document: %s", save_path)

        # ====================================================
        # 9. CREATE / UPDATE LOCAL KYC ROW
        # ====================================================
        existing = (
            db.query(KYCDetails)
            .filter(KYCDetails.user_id == user_id)
            .first()
        )

        if existing:
            kyc = existing
        else:
            kyc = KYCDetails(
                id=new_uuid(),
                user_id=user_id,
            )
            db.add(kyc)

        # ----------------------------------------------------
        # Panel A
        # ----------------------------------------------------
        kyc.agency_name = agency_name
        kyc.owner_first_name = owner_first_name
        kyc.owner_last_name = owner_last_name
        kyc.email = email
        kyc.phone = phone

        # ----------------------------------------------------
        # Panel B
        # ----------------------------------------------------
        kyc.authorised_first_name = _clean(f.get("authorised_first"))
        kyc.authorised_last_name = _clean(f.get("authorised_last"))
        kyc.designation = _clean(f.get("designation"))
        kyc.landline = _clean(f.get("landline"))
        kyc.iata_status = _clean(f.get("iata_status"))
        kyc.iata_number = _clean(f.get("iata_number"))
        kyc.country = _clean(f.get("country"))
        kyc.state = _clean(f.get("state"))
        kyc.city = _clean(f.get("city"))
        kyc.postal_code = _clean(f.get("postal"))
        kyc.office_address = _clean(f.get("office_address"))
        kyc.sales_person = _clean(f.get("sales_person"))

        # ----------------------------------------------------
        # Panel C
        # ----------------------------------------------------
        kyc.business_type = _clean(f.get("business_type"))
        kyc.doc_folder_path = doc_folder_path

        # ----------------------------------------------------
        # PAN / GST — THIS WAS MISSING IN YOUR ORIGINAL FILE
        # ----------------------------------------------------
        kyc.pan_number = pan_number
        kyc.gst_number = gst_number

        # External API status starts as pending.
        kyc.external_api_status = "pending"
        kyc.external_api_message = None

        # ====================================================
        # 10. SAVE LOCAL DATABASE FIRST
        # ====================================================
        db.commit()
        db.refresh(kyc)

        logger.info(
            "Local KYC saved. user_id=%s kyc_id=%s PAN=%s GST=%s",
            user_id,
            kyc.id,
            kyc.pan_number,
            kyc.gst_number,
        )

        # ====================================================
        # 11. UPDATE USER KYC STATUS
        # ====================================================
        update_kyc(
            db,
            user,
            {
                "business_type": kyc.business_type,
                "doc_folder_path": doc_folder_path,
                "saved_files": saved_files,
                "pan_number": kyc.pan_number,
                "gst_number": kyc.gst_number,
            },
        )

        # ====================================================
        # 12. PREPARE NBA WORLD PAYLOAD DATA
        # ====================================================
        owner_name = " ".join(
            part
            for part in [
                kyc.owner_first_name,
                kyc.owner_last_name,
            ]
            if part
        ).strip()

        nba_data = {
            # Panel A
            "agency_name": kyc.agency_name,
            "owner_first_name": kyc.owner_first_name,
            "owner_last_name": kyc.owner_last_name,
            "email": kyc.email,
            "phone": kyc.phone,

            # PAN / GST
            "pan_number": kyc.pan_number,
            "gst_number": kyc.gst_number,

            # Panel B
            "authorised_first_name": kyc.authorised_first_name,
            "authorised_last_name": kyc.authorised_last_name,
            "designation": kyc.designation,
            "landline": kyc.landline,
            "iata_status": kyc.iata_status,
            "iata_number": kyc.iata_number,
            "country": kyc.country,
            "state": kyc.state,
            "city": kyc.city,
            "postal_code": kyc.postal_code,
            "office_address": kyc.office_address,
            "sales_person": kyc.sales_person,

            # Panel C
            "business_type": kyc.business_type,

            # Derived
            "owner_name": owner_name,

            # Fields not currently collected by this KYC form.
            # None becomes JSON null in the external payload.
            "district": _clean(f.get("district")),
            "title": _clean(f.get("title")),
            "region": _clean(f.get("region")),
            "selling_airport": _clean(f.get("selling_airport")),
            "management_source": _clean(f.get("management_source")),
            "management_filed_sales": _clean(f.get("management_filed_sales")),
            "management_state_head": _clean(f.get("management_state_head")),
            "management_registered_by": _clean(f.get("management_registered_by")),
            "management_demo_by": _clean(f.get("management_demo_by")),
            "regional_head": _clean(f.get("regional_head")),
            "national_head": _clean(f.get("national_head")),
            "secondary_business": _clean(f.get("secondary_business")),
            "primary_monthly_business": _clean(f.get("primary_monthly_business")),
            "secondary_monthly_business": _clean(f.get("secondary_monthly_business")),
            "locality": _clean(f.get("locality")),
            "state_head_mail_id": _clean(f.get("state_head_mail_id")),
            "regional_head_mail_id": _clean(f.get("regional_head_mail_id")),
            "agent_display_currency": _clean(f.get("agent_display_currency")),

            # Defaults from your external API model.
            "credit_day_limit": 0,
            "series_ota_a": "NO",
            "series_ota_b": "NO",
            "online_ota_a": "NO",
            "online_ota_b": "NO",
            "primary_business": kyc.business_type,
        }

        # ====================================================
        # 13. CALL NBA WORLD AGENCY CREATION API
        # ====================================================
        logger.info(
            "Calling NBA World Agency Creation API. agency=%s user_id=%s PAN=%s GST=%s",
            kyc.agency_name,
            user_id,
            kyc.pan_number,
            kyc.gst_number,
        )

        nba_result = send_kyc_to_external(nba_data)

        logger.info("NBA World API result: %s", nba_result)

        # ====================================================
        # 14. SAVE EXTERNAL API RESULT
        # ====================================================
        if nba_result.get("success"):
            kyc.external_agent_id = nba_result.get("agent_id")
            kyc.external_api_status = "success"
            kyc.external_api_message = nba_result.get("message")

            db.commit()

            logger.info(
                "NBA World agency created successfully. AgentID=%s",
                nba_result.get("agent_id"),
            )
        else:
            kyc.external_agent_id = nba_result.get("agent_id")
            kyc.external_api_status = "failed"
            kyc.external_api_message = nba_result.get("message")

            db.commit()

            logger.error(
                "NBA World agency creation failed: %s",
                nba_result.get("message"),
            )

        # ====================================================
        # 15. RESPONSE TO FRONTEND
        # ====================================================
        return success(
            {
                "kyc_id": kyc.id,
                "status": (
                    user.status.value
                    if hasattr(user.status, "value")
                    else str(user.status)
                ),
                "doc_folder_path": doc_folder_path,
                "files_saved": saved_files,
                "pan_number": kyc.pan_number,
                "gst_number": kyc.gst_number,
                "external_agent_id": kyc.external_agent_id,
                "external_api_status": kyc.external_api_status,
                "external_api_message": kyc.external_api_message,
            },
            "KYC submitted successfully.",
        )

    except Exception as exc:
        db.rollback()
        logger.exception("KYC submit error: %s", exc)
        return error(
            "An unexpected error occurred. Please try again.",
            500,
        )
    finally:
        db.close()


# ============================================================
# GET /api/kyc/<user_id>
# ============================================================

@jwt_required_custom
def get_kyc(user_id: str):
    from flask_jwt_extended import get_jwt
    from app.models.user import UserRole

    current_id = get_current_user_id()
    claims = get_jwt()
    is_admin = claims.get("role") == UserRole.ADMIN.value

    if current_id != user_id and not is_admin:
        return error("Access denied.", 403)

    db = _db()
    try:
        kyc = (
            db.query(KYCDetails)
            .filter(KYCDetails.user_id == user_id)
            .first()
        )

        if not kyc:
            return error("KYC details not found for this user.", 404)

        return success(kyc.to_dict())
    finally:
        db.close()


# ============================================================
# GET /api/admin/kyc
# ============================================================

@admin_required
def list_all_kyc():
    from app.utils.helpers import paginate, pagination_meta

    db = _db()
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(
            100,
            max(1, int(request.args.get("per_page", 20))),
        )
        biz_filter = request.args.get("business_type", "").strip()
        search = request.args.get("search", "").strip()

        q = db.query(KYCDetails)

        if biz_filter:
            q = q.filter(KYCDetails.business_type == biz_filter)

        if search:
            q = q.filter(
                KYCDetails.agency_name.ilike(f"%{search}%")
                | KYCDetails.email.ilike(f"%{search}%")
                | KYCDetails.phone.ilike(f"%{search}%")
            )

        q = q.order_by(KYCDetails.submitted_at.desc())
        items, total, pages = paginate(q, page, per_page)

        return success(
            {
                "kyc_list": [k.to_dict() for k in items],
                "pagination": pagination_meta(
                    page,
                    per_page,
                    total,
                    pages,
                ),
            }
        )
    finally:
        db.close()


# ============================================================
# POST /api/kyc/submission-confirmation
# ============================================================

@jwt_required_custom
def kyc_submission_confirmation():
    user_id = get_current_user_id()
    db = _db()

    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return error("User not found.", 404)

        from app.services.email_service import send_kyc_confirmation_email

        send_kyc_confirmation_email(
            user.email,
            user.agency_name,
            user.owner_first_name,
        )

        return success(message="Confirmation email sent.")
    finally:
        db.close()


# ============================================================
# REGISTER ROUTES
# ============================================================

kyc_bp.add_url_rule(
    "/kyc/submit",
    view_func=submit_kyc,
    methods=["POST"],
)

kyc_bp.add_url_rule(
    "/kyc/<user_id>",
    view_func=get_kyc,
    methods=["GET"],
)

kyc_bp.add_url_rule(
    "/admin/kyc",
    view_func=list_all_kyc,
    methods=["GET"],
)

kyc_bp.add_url_rule(
    "/kyc/submission-confirmation",
    view_func=kyc_submission_confirmation,
    methods=["POST"],
)
