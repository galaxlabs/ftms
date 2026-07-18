import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from ftms.subscriptions.utils import (
    PERIOD_DAYS,
    MONTHLY_FEE,
    create_subscription_on_link,
)


@frappe.whitelist()
def check_status():
    """Return current subscription status for the logged-in user."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Not authenticated"), frappe.PermissionError)

    company = frappe.get_value("User Company Link",
        {"user": user, "status": "Active"}, "company")

    if not company:
        return {"status": "No Company", "can_create": False}

    sub = frappe.db.get_value("User Subscription",
        {"user": user, "company": company},
        ["name", "status", "trial_end", "current_period_end",
         "active_days_used", "active_days_remaining", "auto_renew"],
        as_dict=True,
    )

    if not sub:
        return {
            "status": "Trial",
            "trial_days_left": 15,
            "can_create": True,
            "message": _("You have 15 days free trial."),
        }

    can_create = sub.status in ("Trial", "Active")
    return {
        "status": sub.status,
        "trial_end": str(sub.trial_end or ""),
        "period_end": str(sub.current_period_end or ""),
        "active_days_used": sub.active_days_used or 0,
        "active_days_remaining": sub.active_days_remaining or 0,
        "auto_renew": sub.auto_renew,
        "can_create": can_create,
    }


@frappe.whitelist()
def get_plans():
    """Return available subscription plans."""
    return {
        "plans": [
            {
                "name": "monthly",
                "label": _("Monthly Active"),
                "price": MONTHLY_FEE,
                "currency": "SAR",
                "duration_days": PERIOD_DAYS,
                "description": _("30 active days of passenger requests. "
                                "Unused days roll forward."),
            }
        ]
    }


@frappe.whitelist()
def subscribe():
    """Create a new subscription period (generates invoice for payment)."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Not authenticated"), frappe.PermissionError)

    company = frappe.get_value("User Company Link",
        {"user": user, "status": "Active"}, "company")

    if not company:
        frappe.throw(_("No active company linked to your account."))

    sub_name = frappe.db.get_value("User Subscription",
        {"user": user, "company": company}, "name")

    if sub_name:
        sub = frappe.get_doc("User Subscription", sub_name)
        sub.renew()
    else:
        sub = frappe.get_doc({
            "doctype": "User Subscription",
            "user": user,
            "company": company,
            "status": "Overdue",
            "trial_start": today(),
            "trial_end": add_days(today(), 15),
        })
        sub.insert(ignore_permissions=True)
        sub.renew()

    return {"subscription": sub.name, "status": sub.status, "amount": MONTHLY_FEE}


@frappe.whitelist()
def mark_paid(subscription_name, invoice=None):
    """Admin endpoint to mark a subscription period as paid."""
    sub = frappe.get_doc("User Subscription", subscription_name)
    sub.mark_paid(invoice=invoice)
    return {"status": sub.status, "message": _("Payment recorded. Subscription activated.")}
