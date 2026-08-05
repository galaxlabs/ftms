from __future__ import annotations

import json
import urllib.error
import urllib.request

import frappe
from frappe.utils import now_datetime


def send_to_user(user, title, body, data=None, failed_only=False):
    credentials, project_id = _credentials()
    if not credentials or not project_id:
        return {"configured": False, "sent": 0}

    filters = {"user": user, "active": 1}
    has_failed_tokens = failed_only and frappe.db.count(
        "Device Push Token",
        {"user": user, "active": 1, "last_error": ("is", "set")},
    )
    if has_failed_tokens:
        filters["last_error"] = ("is", "set")
    tokens = frappe.get_all(
        "Device Push Token",
        filters=filters,
        fields=["name", "token"],
        limit_page_length=20,
    )
    sent = 0
    errors = []
    for row in tokens:
        try:
            _send(credentials.token, project_id, row.token, title, body, data or {})
            frappe.db.set_value(
                "Device Push Token",
                row.name,
                {"last_seen_at": now_datetime(), "last_error": None},
                update_modified=False,
            )
            sent += 1
        except urllib.error.HTTPError as exc:
            raw_error = exc.read().decode("utf-8", errors="replace")
            error = raw_error[:500]
            inactive = _is_unregistered(raw_error)
            frappe.db.set_value(
                "Device Push Token",
                row.name,
                {"active": 0 if inactive else 1, "last_error": error},
                update_modified=False,
            )
            if not inactive:
                errors.append(error)
        except Exception as exc:
            frappe.db.set_value(
                "Device Push Token",
                row.name,
                "last_error",
                str(exc)[:500],
                update_modified=False,
            )
            errors.append(str(exc)[:500])
    return {
        "configured": True,
        "tokens": len(tokens),
        "sent": sent,
        "failed": len(errors),
        "error": errors[0] if errors else None,
    }


def _is_unregistered(raw_error):
    try:
        details = json.loads(raw_error).get("error", {}).get("details", [])
    except (TypeError, ValueError):
        return False
    return any(
        detail.get("errorCode") == "UNREGISTERED"
        for detail in details
        if isinstance(detail, dict)
    )


def _credentials():
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    settings = frappe.get_single("Integration Settings")
    raw = settings.get_password("firebase_service_account_json", raise_exception=False)
    if not raw:
        return None, settings.firebase_project_id
    info = json.loads(raw)
    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/firebase.messaging"],
    )
    credentials.refresh(Request())
    return credentials, settings.firebase_project_id or info.get("project_id")


def _send(access_token, project_id, token, title, body, data):
    payload = json.dumps({
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
            "data": {str(key): str(value) for key, value in data.items() if value is not None},
            "android": {"priority": "high"},
        }
    }).encode("utf-8")
    request = urllib.request.Request(
        f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))
