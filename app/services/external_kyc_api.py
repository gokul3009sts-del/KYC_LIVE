"""
services/external_kyc_api.py

NBA World Agency Creation API client.

Local application field names are mapped to the external API names:
    pan_number -> PANNo
    gst_number -> GSTNo

The external API also expects List_Docu_Images as a JSON STRING.
"""

import json
import logging

import requests

logger = logging.getLogger(__name__)

EXTERNAL_API_URL = (
    "http://nbaworld.mywebcheck.in/"
    "NW_AGENTCREATION_SERVICE/"
    "AgentCreationAPI.svc/"
    "AgencyCreation"
)

ACCESS_KEY = "NBATESEPR"


def _clean(value):
    """Convert None/empty values to None."""
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None


def send_kyc_to_external(data: dict) -> dict:
    """
    Send one KYC/Agency record to NBA World.

    data is the internal application payload created by kyc_routes.py.
    """

    # ========================================================
    # 1. READ PAN / GST
    # ========================================================
    pan_number = _clean(data.get("pan_number"))
    gst_number = _clean(data.get("gst_number"))

    if pan_number:
        pan_number = pan_number.upper()

    if gst_number:
        gst_number = gst_number.upper()

    # ========================================================
    # 2. LIST_DOCU_IMAGES
    # ========================================================
    # IMPORTANT:
    # The external API expects this as a STRING containing JSON.
    documents = {
        "Table1": [
            {
                "NAME": "PAN No.-P1",
                "ID": pan_number,
                "TYPE": "",
                "VALUE": None,
            },
            {
                "NAME": "GST No.-P2",
                "ID": gst_number,
                "TYPE": "",
                "VALUE": None,
            },
        ]
    }

    list_docu_images = json.dumps(
        documents,
        separators=(",", ":"),
    )

    # ========================================================
    # 3. BUILD EXTERNAL API PAYLOAD
    # ========================================================
    payload = {
        "AccessKey": ACCESS_KEY,

        # New agency creation.
        # Do NOT use the previous AgentID such as NSSTV0100102.
        "AgentID": None,

        "AgencyName": _clean(data.get("agency_name")),
        "MobileNo": _clean(data.get("phone")),
        "EmailID": _clean(data.get("email")),
        "Country": _clean(data.get("country")) or "India",
        "State": _clean(data.get("state")),
        "District": _clean(data.get("district")),
        "City": _clean(data.get("city")),
        "Address": _clean(data.get("office_address")),

        # IMPORTANT EXTERNAL FIELD NAMES
        "GSTNo": gst_number,
        "PANNo": pan_number,

        "LoginPassword": _clean(data.get("login_password")),
        "Tittle": _clean(data.get("title")),
        "FirstName": _clean(data.get("owner_first_name")),
        "LastName": _clean(data.get("owner_last_name")),
        "SalesManName": _clean(data.get("sales_person")),
        "PostalCode": _clean(data.get("postal_code")),

        "IS_Distributor": None,
        "Distributor_AgentID": None,
        "Credit_Day_Limit": data.get("credit_day_limit", 0),

        "Owner_Name": _clean(data.get("owner_name")),
        "WhatsAPPNo": _clean(
            data.get("whatsapp_no") or data.get("phone")
        ),

        "Region": _clean(data.get("region")),
        "selling_Airport": _clean(data.get("selling_airport")),

        "Management_source": _clean(data.get("management_source")),
        "Management_FiledSales": _clean(
            data.get("management_filed_sales")
        ),
        "Management_StateHead": _clean(
            data.get("management_state_head")
        ),
        "Management_RegisteredBy": _clean(
            data.get("management_registered_by")
        ),
        "Management_DemoBy": _clean(
            data.get("management_demo_by")
        ),

        "Management_BuisnessType": _clean(
            data.get("business_type")
        ),

        "Online_OTA": None,
        "Series_OTA": None,
        "AgentLogo_Serialized": None,

        # External API expects a JSON string here.
        "List_Docu_Images": list_docu_images,

        "TDS": None,
        "GST": None,
        "Allow_Ticketing": None,
        "Allow_BlockPNR": None,

        "Regional_Head": _clean(data.get("regional_head")),
        "National_Head": _clean(data.get("national_head")),

        "Primary_Business": _clean(
            data.get("primary_business") or data.get("business_type")
        ),
        "Secondary_Business": _clean(data.get("secondary_business")),

        "Primary_Monthy_Business": _clean(
            data.get("primary_monthly_business")
        ),
        "Secondary_Monthy_Business": _clean(
            data.get("secondary_monthly_business")
        ),

        "locality": _clean(data.get("locality")),

        "Series_OTA_A": data.get("series_ota_a", "NO"),
        "Series_OTA_B": data.get("series_ota_b", "NO"),
        "Online_OTA_A": data.get("online_ota_a", "NO"),
        "Online_OTA_B": data.get("online_ota_b", "NO"),

        "StateHeadMailID": _clean(
            data.get("state_head_mail_id")
        ),

        "Allow_LCC_BlockPNR": None,

        "RegionalHeadMailID": _clean(
            data.get("regional_head_mail_id")
        ),

        "AgentDisplayCurrency": _clean(
            data.get("agent_display_currency")
        ),
    }

    # ========================================================
    # 4. LOG EXACT PAN/GST MAPPING
    # ========================================================
    logger.info(
        "NBA payload prepared. Agency=%s PANNo=%s GSTNo=%s",
        payload.get("AgencyName"),
        payload.get("PANNo"),
        payload.get("GSTNo"),
    )

    # ========================================================
    # 5. CALL EXTERNAL API
    # ========================================================
    try:
        response = requests.post(
            EXTERNAL_API_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30,
        )

        response.raise_for_status()

        result = response.json()

        logger.info("NBA World API response: %s", result)

        # ResultCode 1 = Agency Created Successfully.
        if str(result.get("ResultCode")) == "1":
            return {
                "success": True,
                "agent_id": result.get("AgentID"),
                "message": result.get("strMessage"),
                "response": result,
            }

        return {
            "success": False,
            "agent_id": result.get("AgentID"),
            "message": result.get(
                "strMessage",
                "External API rejected the request.",
            ),
            "response": result,
        }

    except requests.exceptions.Timeout:
        logger.exception("NBA World API timeout")
        return {
            "success": False,
            "agent_id": None,
            "message": "External API request timed out.",
            "response": None,
        }

    except requests.exceptions.ConnectionError as exc:
        logger.exception("NBA World API connection error")
        return {
            "success": False,
            "agent_id": None,
            "message": "Could not connect to external API.",
            "error": str(exc),
            "response": None,
        }

    except requests.exceptions.HTTPError as exc:
        logger.exception("NBA World API HTTP error")
        return {
            "success": False,
            "agent_id": None,
            "message": "External API HTTP error.",
            "error": str(exc),
            "response": response.text,
        }

    except ValueError:
        logger.exception("NBA World API returned invalid JSON")
        return {
            "success": False,
            "agent_id": None,
            "message": "External API returned invalid JSON.",
            "response": response.text,
        }

    except Exception as exc:
        logger.exception("Unexpected NBA World API error")
        return {
            "success": False,
            "agent_id": None,
            "message": "Unexpected external API error.",
            "error": str(exc),
            "response": None,
        }
