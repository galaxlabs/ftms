from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, getdate, today, now_datetime
from math import ceil

from ftms.transport_system.doctype.subscription_agreement.subscription_agreement import get_vehicle_count

TRIAL_DAYS = 15
PERIOD_DAYS = 30
MONTHLY_FEE = 100


def subscription_settings():
    try:
        active_days = int(frappe.db.get_single_value("Platform Settings", "subscription_active_days") or PERIOD_DAYS)
        hours_per_day = float(frappe.db.get_single_value("Platform Settings", "subscription_active_hours_per_day") or 8)
        monthly_fee = float(frappe.db.get_single_value("Platform Settings", "subscription_monthly_fee") or MONTHLY_FEE)
    except Exception:
        active_days, hours_per_day, monthly_fee = PERIOD_DAYS, 8, MONTHLY_FEE
    return active_days, max(hours_per_day, 1), monthly_fee


def get_active_subscription_agreement(company):
    if not company or not frappe.db.exists("DocType", "Subscription Agreement"):
        return None
    name = frappe.db.get_value(
        "Subscription Agreement",
        {"company": company, "status": "Active"},
        "name",
        order_by="modified desc",
    )
    return frappe.get_doc("Subscription Agreement", name) if name else None


def get_agreement_terms(company):
    agreement = get_active_subscription_agreement(company)
    if not agreement:
        active_days, hours_per_day, monthly_fee = subscription_settings()
        return frappe._dict({
            "agreement": None,
            "agreement_type": "Monthly",
            "billing_period_months": 1,
            "vehicle_count": 0,
            "amount": monthly_fee,
            "currency": "SAR",
            "active_days": active_days,
            "active_hours_per_day": hours_per_day,
            "payment_mode": "Moyasar",
            "auto_create_moyasar_payment": 1,
        })

    vehicle_count = get_vehicle_count(agreement.company, agreement.vehicle_count_source, agreement.manual_vehicle_count)
    return frappe._dict({
        "agreement": agreement.name,
        "agreement_type": agreement.agreement_type or "Monthly",
        "billing_period_months": int(agreement.billing_period_months or 1),
        "vehicle_count": vehicle_count,
        "amount": float(agreement.calculated_period_amount or 0),
        "currency": agreement.currency or "SAR",
        "active_days": int(agreement.active_days or 30),
        "active_hours_per_day": float(agreement.active_hours_per_day or 8),
        "payment_mode": agreement.payment_mode or "Moyasar",
        "auto_create_moyasar_payment": int(agreement.auto_create_moyasar_payment or 0),
    })


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
        ["status", "name", "trial_end", "current_period_end", "active_hours_limit", "active_hours_remaining", "is_online"],
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

    if sub.status == "Active":
        if sub.active_hours_limit and (sub.active_hours_remaining or 0) <= 0:
            _update_status(sub.name, "Read Only")
            frappe.throw(_("Your active subscription time has been used. Please renew to continue."))
        if sub.is_online is not None and not sub.is_online:
            frappe.throw(_("Your account is offline. Set your subscription online to continue."))
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

        # Active usage, rather than calendar time, consumes the paid period.
        if sub.status == "Active" and sub.active_hours_limit and (sub.active_hours_remaining or 0) <= 0:
            if sub.auto_renew:
                _auto_renew(sub)
            else:
                sub.status = "Read Only"
                sub.save(ignore_permissions=True)

        # Accrue only online heartbeat time; offline time is not billable.
        _sync_active_hours(sub)

    monthly_cycle_sync()
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

    terms = get_agreement_terms(sub.company)
    active_days = terms.active_days
    hours_per_day = terms.active_hours_per_day
    monthly_fee = terms.amount
    new_end = add_days(today_date, active_days)

    sub.append("periods", {
        "period_start": str(today_date),
        "period_end": str(new_end),
        "subscription_agreement": terms.agreement,
        "agreement_type": terms.agreement_type,
        "billing_period_months": terms.billing_period_months,
        "vehicle_count": terms.vehicle_count,
        "active_days": active_days,
        "active_hours_per_day": hours_per_day,
        "amount": monthly_fee,
        "paid": 0,
    })
    sub.subscription_agreement = terms.agreement
    sub.agreement_type = terms.agreement_type
    sub.status = "Overdue"
    sub.active_days_used = 0
    sub.active_days_remaining = 0
    sub.active_hours_used = 0
    sub.active_hours_per_day = hours_per_day
    sub.active_hours_limit = 0
    sub.active_hours_remaining = 0
    sub.rollover_days = 0
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
            "trip_value": subscription_settings()[2],
            "net_total": subscription_settings()[2],
            "vat_amount": 0,
            "grand_total": subscription_settings()[2],
            "enable_zatca": 0,
        })
        inv.insert(ignore_permissions=True)
        sub.db_set("last_invoice", inv.name)
    except Exception as e:
        frappe.log_error(f"Failed to create renewal invoice for {sub.name}: {e}")


def create_subscription_payment(sub):
    """Create Moyasar payment for the first unpaid subscription period."""
    unpaid = next((p for p in sub.periods if not p.paid), None)
    if not unpaid:
        frappe.throw(_("No unpaid subscription period found"))

    if unpaid.payment_transaction or unpaid.payment_url:
        return {
            "payment_url": unpaid.payment_url,
            "payment_id": frappe.db.get_value("Payment Transaction", unpaid.payment_transaction, "gateway_reference") if unpaid.payment_transaction else None,
            "payment_transaction": unpaid.payment_transaction,
        }

    terms = get_agreement_terms(sub.company)
    if terms.payment_mode != "Moyasar" or not terms.auto_create_moyasar_payment:
        return {"payment_url": None, "payment_id": None, "payment_mode": terms.payment_mode}

    from ftms.payments.moyaser import create_payment
    payment = create_payment(
        amount=unpaid.amount,
        currency=terms.currency,
        description=f"FTMS subscription {sub.company} {unpaid.period_start} to {unpaid.period_end}",
        user=sub.user,
        company=sub.company,
        metadata={
            "subscription": sub.name,
            "subscription_period_start": str(unpaid.period_start),
            "subscription_period_end": str(unpaid.period_end),
            "subscription_agreement": unpaid.subscription_agreement or sub.subscription_agreement,
        },
    )
    transaction = frappe.get_doc({
        "doctype": "Payment Transaction",
        "user": sub.user,
        "company": sub.company,
        "provider": "moyasar",
        "currency": terms.currency,
        "amount": unpaid.amount,
        "gateway_reference": payment.get("payment_id"),
        "status": "Initiated",
        "initiated_on": now_datetime(),
    })
    transaction.insert(ignore_permissions=True)
    unpaid.payment_transaction = transaction.name
    unpaid.payment_url = payment.get("payment_url")
    sub.save(ignore_permissions=True)
    return {"payment_url": payment.get("payment_url"), "payment_id": payment.get("payment_id"), "payment_transaction": transaction.name}


def _update_status(name, status):
    frappe.db.set_value("User Subscription", name, "status", status)


def _sync_active_hours(sub, now=None):
    """Accrue only recent online heartbeats; offline time consumes nothing."""
    if sub.status != "Active":
        return
    now = get_datetime(now or now_datetime())
    if not sub.is_online or (sub.offline_until and get_datetime(sub.offline_until) > now):
        return
    last = get_datetime(sub.last_activity_at) if sub.last_activity_at else None
    if last:
        elapsed_seconds = (now - last).total_seconds()
        if 0 < elapsed_seconds <= 900:
            sub.active_hours_used = float(sub.active_hours_used or 0) + elapsed_seconds / 3600
    active_days, hours_per_day, _ = subscription_settings()
    sub.active_hours_per_day = hours_per_day
    sub.active_hours_limit = float(active_days * hours_per_day)
    sub.active_hours_used = min(float(sub.active_hours_used or 0), sub.active_hours_limit)
    sub.active_hours_remaining = max(sub.active_hours_limit - sub.active_hours_used, 0)
    sub.active_days_used = int(ceil(sub.active_hours_used / hours_per_day)) if sub.active_hours_used else 0
    sub.active_days_remaining = max(active_days - sub.active_days_used, 0)
    sub.last_activity_at = now
    if sub.active_hours_remaining <= 0:
        sub.status = "Read Only"
    sub.save(ignore_permissions=True)


def record_activity(user, company):
    name = frappe.db.get_value("User Subscription", {"user": user, "company": company}, "name")
    if not name:
        return {"status": "No Subscription"}
    sub = frappe.get_doc("User Subscription", name)
    if sub.status != "Active":
        return {"status": sub.status, "active_hours_remaining": sub.active_hours_remaining or 0}
    _sync_active_hours(sub)
    return {
        "status": sub.status,
        "is_online": bool(sub.is_online),
        "active_hours_used": round(float(sub.active_hours_used or 0), 4),
        "active_hours_remaining": round(float(sub.active_hours_remaining or 0), 4),
    }


def set_online_status(user, company, online, offline_until=None, reason=None):
    name = frappe.db.get_value("User Subscription", {"user": user, "company": company}, "name")
    if not name:
        frappe.throw(_("Subscription not found"))
    sub = frappe.get_doc("User Subscription", name)
    if online:
        sub.is_online = 1
        sub.offline_until = None
        sub.offline_reason = None
    else:
        _sync_active_hours(sub)
        sub.is_online = 0
        sub.offline_until = offline_until
        sub.offline_reason = reason
    sub.save(ignore_permissions=True)
    return {"status": sub.status, "is_online": bool(sub.is_online), "offline_until": str(sub.offline_until or "")}


def monthly_cycle_sync():
    """Create this month's unpaid period and lock accounts whose month passed its grace."""
    for name in frappe.get_all("User Subscription", filters={"status": ["in", ("Active",)]}, pluck="name"):
        sub = frappe.get_doc("User Subscription", name)
        created = sub.ensure_current_month_period()
        locked = sub.apply_monthly_lock()
        if created or locked:
            sub.save(ignore_permissions=True)
    frappe.db.commit()
