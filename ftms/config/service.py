from __future__ import annotations

import re

import frappe
from frappe.utils import getdate, nowdate


def _single(doctype):
    try:
        return frappe.get_single(doctype)
    except Exception:
        return None


def _value(doc, fieldname, default=None):
    if not doc:
        return default
    value = doc.get(fieldname)
    return default if value in (None, "") else value


def get_platform_settings():
    doc = _single("Platform Settings")
    return {
        "platform_name": _value(doc, "platform_name", "Ride Platform"),
        "frontend_base_url": _value(doc, "frontend_base_url", ""),
        "default_country": _value(doc, "default_country", ""),
        "default_currency": _value(doc, "default_currency", "SAR"),
        "default_timezone": _value(doc, "default_timezone", "Asia/Riyadh"),
        "default_language": _value(doc, "default_language", "en"),
        "platform_commission_rate": float(_value(doc, "platform_commission_rate", 5) or 5),
        "default_offer_expiry_minutes": int(_value(doc, "default_offer_expiry_minutes", 30) or 30),
        "default_group_invite_expiry_hours": int(_value(doc, "default_group_invite_expiry_hours", 24) or 24),
        "maintenance_mode": bool(_value(doc, "maintenance_mode", 0)),
        "enable_marketplace": bool(_value(doc, "enable_marketplace", 1)),
        "enable_public_links": bool(_value(doc, "enable_public_links", 1)),
        "enable_firebase_sync": bool(_value(doc, "enable_firebase_sync", 0)),
    }


def get_public_frontend_url():
    configured = get_platform_settings().get("frontend_base_url")
    return (configured or frappe.utils.get_url()).rstrip("/")


def get_integration_settings(include_private=False):
    doc = _single("Integration Settings")
    result = {
        "firebase_project_id": _value(doc, "firebase_project_id", ""),
        "firebase_auth_domain": _value(doc, "firebase_auth_domain", ""),
        "firebase_web_app_id": _value(doc, "firebase_web_app_id", ""),
        "firebase_android_app_id": _value(doc, "firebase_android_app_id", ""),
        "firebase_storage_bucket": _value(doc, "firebase_storage_bucket", ""),
        "firebase_messaging_sender_id": _value(doc, "firebase_messaging_sender_id", ""),
        "firebase_measurement_id": _value(doc, "firebase_measurement_id", ""),
        "frappe_api_base_url": _value(doc, "frappe_api_base_url", frappe.utils.get_url()),
        "sync_enabled": bool(_value(doc, "sync_enabled", 0)),
        "sync_interval_seconds": int(_value(doc, "sync_interval_seconds", 60) or 60),
        "sync_retry_count": int(_value(doc, "sync_retry_count", 5) or 5),
        "dead_letter_enabled": bool(_value(doc, "dead_letter_enabled", 1)),
        "payment_provider": _value(doc, "payment_provider", ""),
        "payment_public_key": _value(doc, "payment_public_key", ""),
        "maps_provider": _value(doc, "maps_provider", "Google"),
        "maps_country_restriction": _value(doc, "maps_country_restriction", "SA"),
        "apk_download_url": _value(doc, "apk_download_url", ""),
        "update_check_url": _value(doc, "update_check_url", ""),
        "min_supported_build": int(_value(doc, "min_supported_build", 0) or 0),
        "play_integrity_project_number": _value(doc, "play_integrity_project_number", ""),
    }
    if include_private and doc:
        result["firebase_web_api_key"] = doc.get_password("firebase_api_key", raise_exception=False) or ""
        result["firebase_android_api_key"] = doc.get_password("firebase_android_api_key", raise_exception=False) or ""
        result["payment_webhook_secret"] = doc.get_password("payment_webhook_secret", raise_exception=False) or ""
        result["maps_api_key"] = doc.get_password("maps_api_key", raise_exception=False) or ""
    return result


def get_app_config(include_private=False):
    """Complete mobile app configuration: Firebase keys, Maps key, Play Integrity,
    update/APK URLs and min supported build. Used by the Flutter app at startup."""
    integration = get_integration_settings(include_private=True)
    platform = get_platform_settings()
    return {
        "firebase": {
            "project_id": integration.get("firebase_project_id"),
            "auth_domain": integration.get("firebase_auth_domain"),
            "storage_bucket": integration.get("firebase_storage_bucket"),
            "messaging_sender_id": integration.get("firebase_messaging_sender_id"),
            "measurement_id": integration.get("firebase_measurement_id"),
            "web_app_id": integration.get("firebase_web_app_id"),
            "android_app_id": integration.get("firebase_android_app_id"),
            "web_api_key": integration.get("firebase_web_api_key", "") if include_private else "",
            "android_api_key": integration.get("firebase_android_api_key", "") if include_private else "",
        },
        "maps": {
            "provider": integration.get("maps_provider", "Google"),
            "country_restriction": integration.get("maps_country_restriction", "SA"),
            "api_key": "",
        },
        "play_integrity_project_number": integration.get("play_integrity_project_number", ""),
        "updates": {
            "apk_download_url": integration.get("apk_download_url", ""),
            "update_check_url": integration.get("update_check_url", ""),
            "min_supported_build": integration.get("min_supported_build", 0),
        },
        "api": {"base_url": integration.get("frappe_api_base_url")},
        "platform": platform,
        "version": frappe.get_attr("ftms.__version__"),
    }


def get_feature_flags(user=None, company=None, platform=None, country=None):
    filters = {"enabled": 1}
    try:
        rows = frappe.get_all(
            "Feature Flag",
            filters=filters,
            fields=["flag_key", "country", "company", "role", "platform", "start_date", "end_date", "rollout_percentage"],
        )
    except Exception:
        return {}

    role = None
    if user and user != "Guest":
        try:
            role = next((r for r in frappe.get_roles(user) if r not in {"All", "Guest"}), None)
        except Exception:
            role = None

    today = getdate(nowdate())
    result = {}
    for row in rows:
        if row.get("country") and row.get("country") != country:
            continue
        if row.get("company") and row.get("company") != company:
            continue
        if row.get("role") and row.get("role") != role:
            continue
        if row.get("platform") and row.get("platform") != platform:
            continue
        if row.get("start_date") and getdate(row["start_date"]) > today:
            continue
        if row.get("end_date") and getdate(row["end_date"]) < today:
            continue
        result[row["flag_key"]] = True
    return result


def get_document_format(country, document_type):
    try:
        rows = frappe.get_all(
            "Country Document Format",
            filters={"country": country, "document_type": document_type, "enabled": 1},
            fields=["country", "document_type", "pattern", "placeholder", "description", "minimum_length", "maximum_length", "normalization_rule", "attachment_allowed", "requires_expiry", "requires_verification", "validation_error_message"],
            order_by="priority desc, modified desc",
            limit=1,
        )
    except Exception:
        rows = []
    if rows:
        return rows[0]
    return None


def get_kashf_config(service_type=None, country=None):
    filters = {"enabled": 1}
    if service_type:
        filters["service_type"] = service_type
    if country:
        filters["country"] = country
    try:
        rows = frappe.get_all(
            "Kashf Template",
            filters=filters,
            fields=["template_name", "provider_identity_source", "show_passenger_documents", "show_passenger_mobile", "show_qr", "language", "footer_text"],
            order_by="modified desc",
            limit=1,
        )
    except Exception:
        rows = []
    return rows[0] if rows else {
        "template_name": "Default",
        "provider_identity_source": "Verified Company First",
        "show_passenger_documents": 0,
        "show_passenger_mobile": 0,
        "show_qr": 1,
        "language": "Bilingual",
        "footer_text": "",
    }


def normalize_document(value, rule=None):
    value = (value or "").strip()
    if rule == "Uppercase":
        return value.upper()
    if rule == "Lowercase":
        return value.lower()
    if rule == "Digits Only":
        return re.sub(r"\D", "", value)
    if rule == "Remove Spaces":
        return re.sub(r"\s+", "", value)
    return value


def validate_configured_document(country, document_type, value):
    config = get_document_format(country, document_type)
    if not config:
        return {"valid": bool(value and str(value).strip()), "format": None, "error": None}
    normalized = normalize_document(value, config.get("normalization_rule"))
    error = config.get("validation_error_message") or "Invalid document format"
    if not normalized:
        return {"valid": False, "format": config, "error": "Document number is required"}
    minimum = int(config.get("minimum_length") or 0)
    maximum = int(config.get("maximum_length") or 0)
    if minimum and len(normalized) < minimum or maximum and len(normalized) > maximum:
        return {"valid": False, "format": config, "value": normalized, "error": error}
    pattern = config.get("pattern")
    if pattern and not re.match(pattern, normalized):
        return {"valid": False, "format": config, "value": normalized, "error": error}
    return {"valid": True, "format": config, "value": normalized, "error": None}


def get_client_config(user=None, company=None, country=None, platform=None):
    platform_settings = get_platform_settings()
    integration = get_integration_settings(include_private=False)
    return {
        "platform": platform_settings,
        "firebase": {
            key: integration.get(key, "")
            for key in (
                "firebase_project_id", "firebase_auth_domain", "firebase_web_app_id",
                "firebase_storage_bucket", "firebase_messaging_sender_id", "firebase_measurement_id",
            )
        },
        "api": {"base_url": integration.get("frappe_api_base_url")},
        "sync": {
            "enabled": integration.get("sync_enabled", False),
            "interval_seconds": integration.get("sync_interval_seconds", 60),
        },
        "features": get_feature_flags(user=user, company=company, platform=platform, country=country),
        "version": frappe.get_attr("ftms.__version__"),
    }
