import frappe
from frappe import _
from frappe.utils import add_days, getdate
from frappe.utils.oauth import get_oauth2_authorize_url
from ftms.security import rate_limit


@frappe.whitelist()
def get_user_api_key():
    """Deprecated: browser clients must use the session cookie, not API secrets."""
    frappe.throw("User API secrets cannot be returned to clients", frappe.PermissionError)


@frappe.whitelist(allow_guest=True)
def get_current_user():
    """SPA-safe auth endpoint. Works with both session auth and API key auth."""
    user = frappe.session.user
    if not user or user == "Guest":
        return {"is_authenticated": False, "message": "Not authenticated"}

    user_doc = frappe.get_doc("User", user)
    roles = frappe.get_roles()

    link = _find_active_link(user)
    company_data = None
    if link:
        company = frappe.get_doc("Company", link.company)
        company_data = {f: company.get(f) for f in _COMPANY_FIELDS}

    subscription = _get_subscription_status(user, link.company if link else None)
    captain_profile = _get_captain_profile(user)

    return {
        "is_authenticated": True,
        "message": "Authenticated",
        "user": user,
        "name": user_doc.name,
        "email": user_doc.email,
        "first_name": user_doc.first_name,
        "last_name": user_doc.last_name,
        "full_name": user_doc.full_name,
        "mobile_no": user_doc.mobile_no,
        "id_document_type": _user_field(user_doc, "ftms_id_document_type"),
        "id_no": _user_field(user_doc, "ftms_id_no"),
        "nationality": _user_field(user_doc, "ftms_nationality"),
        "id_expiry_date": str(_user_field(user_doc, "ftms_id_expiry_date") or ""),
        "id_document": _user_field(user_doc, "ftms_id_document"),
        "roles": roles,
        "portal_role": link.role if link else None,
        "company": link.company if link else None,
        "company_data": company_data,
        "captain_profile": captain_profile,
        "onboarding": {
            "has_company_link": bool(link),
            "has_captain_profile": bool(captain_profile),
            "can_register_company": not link and not captain_profile,
            "can_become_captain": not link and not captain_profile,
        },
        "subscription": subscription,
        "permissions": _get_permissions(link),
    }


@frappe.whitelist(allow_guest=True)
def get_google_login_url(redirect_to=None):
    """Return the Google OAuth authorization URL (redirect user's browser to this)."""
    if not redirect_to:
        redirect_to = frappe.utils.get_url() + "/app"
    return get_oauth2_authorize_url("google", redirect_to)


@frappe.whitelist(allow_guest=True)
def login_with_firebase(id_token=None, firebase_uid=None):
    """Verify a Firebase Auth ID token, find or create the matching Frappe user,
    and log them in. Returns the session cookie (sid) via Set-Cookie.
    """
    rate_limit("login_with_firebase", limit=20, seconds=60)
    if not id_token:
        frappe.throw(_("id_token is required"))

    claims = _verify_firebase_id_token(id_token)
    email = (claims.get("email") or "").strip().lower()
    uid = claims.get("uid") or claims.get("sub") or firebase_uid
    name = (claims.get("name") or "").strip()
    email_verified = claims.get("email_verified", False)

    if not email:
        frappe.throw(_("A verified email is required for Firebase login"))

    user = _find_or_create_firebase_user(email, uid=uid, name=name, email_verified=email_verified)
    _login_as(user)

    return {
        "status": "ok",
        "user": user.name,
        "email": user.email,
        "full_name": user.full_name,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "mobile_no": user.mobile_no,
        "roles": frappe.get_roles(),
        "uid": uid,
    }


def _verify_firebase_id_token(token):
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    try:
        request = google_requests.Request()
        return google_id_token.verify_firebase_token(token, request, audience=None)
    except Exception as exc:
        frappe.log_error(frappe.get_traceback(), "FTMS Firebase token verification failed")
        frappe.throw(_("Invalid or expired Firebase ID token: {0}").format(str(exc)))


def _find_or_create_firebase_user(email, uid=None, name=None, email_verified=False):
    email = (email or "").strip().lower()
    existing = frappe.db.exists("User", email)
    if existing:
        user_doc = frappe.get_doc("User", email)
        changed = False
        if name and not user_doc.full_name:
            parts = name.strip().split(" ", 1)
            user_doc.first_name = parts[0][:140]
            user_doc.last_name = parts[1].strip() if len(parts) > 1 else ""
            changed = True
        if uid and user_doc.meta.has_field("ftms_firebase_uid") and not user_doc.ftms_firebase_uid:
            user_doc.ftms_firebase_uid = uid
            changed = True
        if changed:
            user_doc.save(ignore_permissions=True)
            frappe.db.commit()
        return user_doc

    from frappe.exceptions import DuplicateEntryError
    from frappe.utils import random_string

    first_name = email.split("@")[0][:140]
    last_name = ""
    if name:
        parts = name.strip().split(" ", 1)
        first_name = parts[0][:140]
        last_name = parts[1].strip() if len(parts) > 1 else ""

    try:
        user_doc = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "username": email.split("@")[0],
            "first_name": first_name,
            "last_name": last_name,
            "enabled": 1,
            "send_welcome_email": 0,
            "new_password": random_string(24),
            "user_type": "Website User",
        })
        user_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return user_doc
    except DuplicateEntryError:
        # Concurrent sign-in from another device created the user first.
        frappe.db.rollback()
        user_doc = frappe.get_doc("User", email)
        frappe.db.commit()
        return user_doc


@frappe.whitelist(allow_guest=True)
def verify_play_integrity(integrity_token=None):
    """Decode and verify a Play Integrity API token using a linked service account.

    Returns verdicts (app/device/account) plus a status:
      - "verified"   token decodes and app is PLAY_RECOGNIZED
      - "failed"     token decoded but verdicts are not trustworthy
      - "not_configured" service account not set up on the server yet
      - "error"      unexpected failure

    Server config (site_config.json):
      "play_integrity_service_account": "path-or-JSON to the GCP service account key"
      "play_integrity_package": "com.galaxylabs.ftms"
    """
    if not integrity_token:
        frappe.throw(_("integrity_token is required"))

    service_account = frappe.get_site_config().get("play_integrity_service_account")
    package = frappe.get_site_config().get("play_integrity_package", "com.galaxylabs.ftms")
    if not service_account:
        return {"status": "not_configured", "message": "Play Integrity service account not configured on server"}

    try:
        verdict = _decode_play_integrity_token(integrity_token, service_account, package)
    except Exception as exc:
        frappe.log_error(frappe.get_traceback(), "FTMS Play Integrity verification failed")
        return {"status": "error", "message": str(exc)}

    app_verdict = (verdict.get("appIntegrity") or {}).get("appRecognitionVerdict", "")
    device_verdict = (verdict.get("deviceIntegrity") or {}).get("deviceRecognitionVerdict", [])
    account_verdict = (verdict.get("accountDetails") or {}).get("appLicensingVerdict", "")
    request_details = verdict.get("requestDetails") or {}
    response_package = request_details.get("requestPackageName", "")

    passed = bool(
        response_package == package
        and app_verdict == "PLAY_RECOGNIZED"
        and device_verdict
        and any(v in ("MEETS_DEVICE_INTEGRITY", "MEETS_STRONG_INTEGRITY") for v in device_verdict)
    )

    return {
        "status": "verified" if passed else "failed",
        "message": None if passed else "App or device integrity check failed",
        "app_verdict": app_verdict,
        "device_verdict": ",".join(device_verdict),
        "account_verdict": account_verdict,
        "package": response_package,
        "timestamp_ms": request_details.get("timestampMillis"),
    }


def _decode_play_integrity_token(token, service_account, package):
    import json
    from google.oauth2 import service_account as sa
    from google.auth.transport.requests import Request as GoogleRequest

    try:
        sa_dict = json.loads(service_account)
    except (TypeError, ValueError):
        with open(service_account) as f:
            sa_dict = json.load(f)

    credentials = sa.Credentials.from_service_account_info(
        sa_dict,
        scopes=["https://www.googleapis.com/auth/playintegrity"],
    )
    if credentials.token is None:
        credentials.refresh(GoogleRequest())

    import http.client
    body = json.dumps({"integrityToken": token}).encode("utf-8")
    conn = http.client.HTTPSConnection("playintegrity.googleapis.com")
    conn.request(
        "POST",
        f"/v1/{package}:decodeIntegrityToken",
        body=body,
        headers={
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json",
        },
    )
    response = conn.getresponse()
    raw = response.read().decode("utf-8")
    conn.close()
    if response.status != 200:
        raise RuntimeError(f"Play Integrity API returned {response.status}: {raw}")
    return json.loads(raw)


def _login_as(user):
    from frappe.auth import LoginManager

    login_manager = LoginManager()
    login_manager.user = user.name
    login_manager.post_login()
    frappe.db.commit()
    return frappe.session.sid


@frappe.whitelist()
def update_profile(first_name=None, last_name=None, mobile_no=None, id_document_type=None, id_no=None, nationality=None, id_expiry_date=None, id_document=None):
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Not authenticated", frappe.PermissionError)

    user_doc = frappe.get_doc("User", user)
    if first_name is not None:
        user_doc.first_name = (first_name or "").strip()
    if last_name is not None:
        user_doc.last_name = (last_name or "").strip()
    if mobile_no is not None:
        user_doc.mobile_no = (mobile_no or "").strip()
    identity_fields = {
        "ftms_id_document_type": id_document_type,
        "ftms_id_no": id_no,
        "ftms_nationality": nationality,
        "ftms_id_expiry_date": id_expiry_date,
        "ftms_id_document": id_document,
    }
    for fieldname, value in identity_fields.items():
        if value is not None and user_doc.meta.has_field(fieldname):
            user_doc.set(fieldname, value.strip() if isinstance(value, str) else value)
    user_doc.save(ignore_permissions=True)
    return get_current_user()


def _find_active_link(user=None):
    user = user or frappe.session.user
    if not user:
        return None
    links = frappe.get_all(
        "User Company Link",
        filters={"user": user, "status": "Active"},
        fields=["*"],
        order_by="modified desc",
        limit=1,
    )
    return links[0] if links else None


def _user_field(user_doc, fieldname):
    if user_doc.meta.has_field(fieldname):
        return user_doc.get(fieldname)
    return None


def _get_subscription_status(user, company):
    if not company:
        return {"status": "Unknown", "trial_days_left": 0, "active_days_left": 0}
    subs = frappe.get_all(
        "User Subscription",
        filters={"user": user, "company": company},
        fields=["status", "trial_start", "trial_end", "trial_days_left",
                "current_period_start", "current_period_end",
                "active_days_used", "active_days_remaining", "rollover_days",
                "last_payment_date", "auto_renew"],
        order_by="creation desc",
        limit=1,
    )
    if not subs:
        now = getdate()
        return {"status": "Trial", "trial_days_left": 15, "active_days_left": 0,
                "trial_start": str(now), "trial_end": str(add_days(now, 15))}
    s = subs[0]
    return {
        "status": s.get("status", "Unknown"),
        "trial_start": str(s.get("trial_start") or ""),
        "trial_end": str(s.get("trial_end") or ""),
        "trial_days_left": s.get("trial_days_left", 0),
        "period_start": str(s.get("current_period_start") or ""),
        "period_end": str(s.get("current_period_end") or ""),
        "active_days_used": s.get("active_days_used", 0),
        "active_days_remaining": s.get("active_days_remaining", 0),
        "rollover_days": s.get("rollover_days", 0),
        "auto_renew": s.get("auto_renew", 1),
        "last_payment_date": str(s.get("last_payment_date") or ""),
    }


def _get_captain_profile(user):
    profiles = frappe.get_all(
        "Captain Profile",
        filters={"user": user},
        fields=["name", "status", "current_company", "license_no", "license_expiry_date", "driver_card_no", "driver_card_expiry_date", "mobile_no"],
        limit=1,
    )
    return profiles[0] if profiles else None

def _get_permissions(link):
    if not link:
        return {"can_create": False, "can_edit": False, "can_delete": False}

    role = link.role
    base = {"company": link.company}

    perms = {
        "Company Admin": {"can_create": True, "can_edit": True, "can_delete": True},
        "Dispatcher": {"can_create": True, "can_edit": True, "can_delete": False},
        "Captain": {"can_create": False, "can_edit": False, "can_delete": False},
        "Accountant": {"can_create": True, "can_edit": True, "can_delete": False},
        "Viewer": {"can_create": False, "can_edit": False, "can_delete": False},
        "Passenger": {"can_create": False, "can_edit": False, "can_delete": False},
    }

    return {**base, **perms.get(role, {"can_create": False, "can_edit": False, "can_delete": False})}


_COMPANY_FIELDS = [
    "company_code", "company_name", "legal_name", "company_name_ar",
    "vat_no", "tax_id", "cr_no", "address", "phone", "email",
    "default_currency", "enable_zatca_e_invoicing", "zatca_phase",
    "enable_kashf", "status",
]
