from __future__ import annotations

import frappe


def authenticate():
    """Authenticate app requests carrying a verified Firebase ID token."""
    if frappe.session.user not in (None, "", "Guest"):
        return

    authorization = frappe.get_request_header("Authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token:
        return

    try:
        claims = _verify_token(token)
    except Exception as exc:
        raise frappe.AuthenticationError("Invalid Firebase authentication token") from exc

    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise frappe.AuthenticationError("Firebase token does not contain an email")

    user = frappe.db.get_value("User", {"name": email, "enabled": 1}, "name")
    if not user:
        raise frappe.AuthenticationError("No enabled Frappe user matches this Firebase account")

    frappe.set_user(user)


def _verify_token(token):
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    project_id = None
    if frappe.db.exists("DocType", "Integration Settings"):
        project_id = frappe.db.get_single_value("Integration Settings", "firebase_project_id")
    return google_id_token.verify_firebase_token(
        token,
        google_requests.Request(),
        audience=project_id or None,
    )
