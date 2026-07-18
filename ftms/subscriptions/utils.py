from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today, now_datetime

TRIAL_DAYS = 15
PERIOD_DAYS = 30
MONTHLY_FEE = 100


def create_subscription_on_link(doc, method):
    """When a User Company Link is created, auto-create a trial subscription."""
    if doc.status != "Active":
        return
    existing = frappe.db.exists("User Subscription", {
        "user": doc.user,
        "company": doc.company,
    })
    if existing:
        return
    sub = frappe.get_doc({
        "doctype": "User Subscription",
        "user": doc.user,
        "company": doc.company,
        "status": "Trial",
        "trial_start": today(),
        "trial_end": add_days(today(), TRIAL_DAYS),
        "trial_days_left": TRIAL_DAYS,
    })
    sub.insert(ignore_permissions=True)


def enforce_subscription(doc, method):
    """Validate that user has active subscription before creating/updating trips."""
    user = frappe.session.user
    if user in ("Administrator", "Guest"):
        return
    company = doc.get("company")
    if not company:
        return

    sub = frappe.db.get_value("User Subscription",
        {"user": user, "company": company},
        ["status", "name", "trial_end", "current_period_end"],
        as_dict=True,
    )

    if not sub:
        return  # No subscription record yet = trial eligible

    today_date = getdate()

    if sub.status == "Trial":
        if sub.trial_end and getdate(sub.trial_end) < today_date:
            _update_status(sub.name, "Read Only")
            frappe.throw(_("Your 15-day trial has ended. Please subscribe to continue."))
        return

    if sub.status == "Read Only":
        frappe.throw(_("Subscription expired. Please renew to use the service."))

    if sub.status == "Overdue":
        frappe.throw(_("Subscription overdue. Make a payment to reactivate."))

    if sub.status == "Inactive":
        frappe.throw(_("Account is inactive. Contact your company admin."))


def daily_subscription_sync():
    """Daily job: update statuses, count active days, handle renewals."""
    subscriptions = frappe.get_all("User Subscription",
        filters={"status": ["in", ("Trial", "Active", "Overdue")]},
        fields=["name", "user", "company", "status", "trial_end", "current_period_end", "auto_renew"],
    )

    for sub_data in subscriptions:
        sub = frappe.get_doc("User Subscription", sub_data.name)
        today_date = getdate()

        # Trial expired → Read Only
        if sub.status == "Trial" and sub.trial_end:
            if getdate(sub.trial_end) < today_date:
                sub.status = "Read Only"
                sub.save(ignore_permissions=True)
                continue

        # Active → check if period expired
        if sub.status == "Active":
            period_end = sub.current_period_end
            if period_end and getdate(period_end) < today_date:
                if sub.auto_renew:
                    _auto_renew(sub)
                else:
                    sub.status = "Overdue"
                    sub.save(ignore_permissions=True)

        # Count active days (days with completed trips)
        _update_active_days(sub)

    frappe.db.commit()


def hourly_trial_check():
    """Hourly: mark expired trials as Read Only."""
    expired = frappe.get_all("User Subscription",
        filters={"status": "Trial", "trial_end": ["<", today()]},
        fields=["name"],
    )
    for sub in expired:
        _update_status(sub.name, "Read Only")
    if expired:
        frappe.db.commit()


def _auto_renew(sub):
    """Auto-create a new period when auto_renew is enabled."""
    today_date = getdate()

    # Carry forward unused active days
    unused = PERIOD_DAYS - (sub.active_days_used or 0)
    rollover = max(unused, 0)
    new_end = add_days(today_date, PERIOD_DAYS + rollover)

    sub.append("periods", {
        "period_start": str(today_date),
        "period_end": str(new_end),
        "amount": MONTHLY_FEE,
        "paid": 0,
    })
    sub.status = "Overdue"
    sub.active_days_used = 0
    sub.rollover_days = rollover
    sub.save(ignore_permissions=True)

    # Generate invoice for auto-renewal
    _create_renewal_invoice(sub)


def _create_renewal_invoice(sub):
    """Create a Trip Invoice for the renewal amount."""
    try:
        inv = frappe.get_doc({
            "doctype": "Trip Invoice",
            "company": sub.company,
            "customer": sub.user,
            "invoice_date": today(),
            "billing_mode": "Manual",
            "vat_mode": "Excluded",
            "trip_value": MONTHLY_FEE,
            "net_total": MONTHLY_FEE,
            "vat_amount": 0,
            "grand_total": MONTHLY_FEE,
            "enable_zatca": 0,
        })
        inv.insert(ignore_permissions=True)
        sub.db_set("last_invoice", inv.name)
    except Exception as e:
        frappe.log_error(f"Failed to create renewal invoice for {sub.name}: {e}")


def _update_status(name, status):
    frappe.db.set_value("User Subscription", name, "status", status)


def _update_active_days(sub):
    """Count days where user had completed trips in current period."""
    if not sub.current_period_start:
        return

    trip_count = frappe.db.count("Trip", filters={
        "company": sub.company,
        "owner": sub.user,
        "docstatus": 1,
        "creation": [">=", sub.current_period_start],
    })

    active_days = frappe.db.sql("""
        SELECT COUNT(DISTINCT DATE(creation))
        FROM `tabTrip`
        WHERE company=%s
          AND owner=%s
          AND docstatus=1
          AND DATE(creation) BETWEEN %s AND %s
    """, (sub.company, sub.user, sub.current_period_start, sub.current_period_end or today()))

    days = active_days[0][0] if active_days else 0
    if days != sub.active_days_used:
        sub.db_set("active_days_used", days)
        remaining = max(PERIOD_DAYS - days + (sub.rollover_days or 0), 0)
        sub.db_set("active_days_remaining", remaining)
