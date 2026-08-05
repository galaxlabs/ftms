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
        from ftms.firebase_auth_bridge import resolve_frappe_user, verify_id_token

        claims = verify_id_token(token)
        user = resolve_frappe_user(claims)
    except Exception as exc:
        raise frappe.AuthenticationError("Invalid Firebase authentication token") from exc

    frappe.set_user(user)
