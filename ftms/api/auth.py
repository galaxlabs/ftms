import frappe
from frappe.utils import add_days, getdate


@frappe.whitelist()
def get_user_api_key():
    """Return the current user's API key and secret for frontend auth."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Not authenticated", frappe.PermissionError)

    user_doc = frappe.get_doc("User", user)
    api_key = user_doc.api_key
    api_secret = user_doc.get_password("api_secret") if user_doc.api_secret else None

    if not api_key or not api_secret:
        frappe.throw("No API key configured for this user. Contact your administrator.")

    return {"api_key": api_key, "api_secret": api_secret}


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
        company = frappe.get_doc("Transportation Company", link.company)
        company_data = {f: company.get(f) for f in _COMPANY_FIELDS}

    subscription = _get_subscription_status(user, link.company if link else None)

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
        "roles": roles,
        "portal_role": link.role if link else None,
        "company": link.company if link else None,
        "company_data": company_data,
        "subscription": subscription,
        "permissions": _get_permissions(link),
    }


@frappe.whitelist()
def update_profile(first_name=None, last_name=None, mobile_no=None):
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
