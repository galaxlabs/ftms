from __future__ import annotations

import hashlib
import hmac
import json

import frappe
from frappe.utils import now_datetime

from ftms.config.service import get_integration_settings
from ftms.wallet.service import credit_wallet, get_wallet_summary
from ftms.notifications.service import emit_event
from ftms.security import rate_limit


def _request_payload():
    raw = frappe.request.get_data() or b""
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else dict(frappe.form_dict)
    except Exception:
        payload = dict(frappe.form_dict)
    payload.pop("cmd", None)
    return raw, payload


def _verify_signature(raw):
    secret = get_integration_settings(include_private=True).get("payment_webhook_secret")
    signature = frappe.get_request_header("X-Payment-Signature") or frappe.get_request_header("X-Webhook-Signature")
    if not secret or not signature:
        frappe.throw("Payment webhook is not configured", frappe.PermissionError)
    expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        frappe.throw("Invalid payment signature", frappe.PermissionError)


@frappe.whitelist(allow_guest=True)
def payment_webhook():
    """Verify a gateway callback and credit the user's Frappe wallet exactly once."""
    rate_limit("payment_webhook", limit=120, seconds=60)
    raw, payload = _request_payload()
    _verify_signature(raw)

    status = str(payload.get("status") or payload.get("payment_status") or "").lower()
    if status not in {"paid", "succeeded", "success", "authorized"}:
        return {"status": "ignored", "payment_status": status}
    user = payload.get("user") or payload.get("customer_user")
    amount = payload.get("amount")
    currency = payload.get("currency") or "SAR"
    event_id = payload.get("event_id") or payload.get("payment_id") or payload.get("reference")
    if not user or not amount or not event_id:
        frappe.throw("Payment webhook requires user, amount, and event_id")
    company = payload.get("company") or frappe.db.get_value(
        "User Company Link", {"user": user, "status": "Active"}, "company"
    )
    if not company:
        frappe.throw("Payment webhook requires a company")

    existing = frappe.db.get_value("Payment Transaction", {"webhook_event_id": event_id}, "name")
    if existing:
        return {"status": "already_processed", "payment_transaction": existing}

    payment = frappe.get_doc({
        "doctype": "Payment Transaction",
        "user": user,
        "company": company,
        "order": payload.get("order") or payload.get("booking"),
        "provider": payload.get("provider") or get_integration_settings().get("payment_provider"),
        "currency": currency,
        "amount": amount,
        "gateway_reference": payload.get("gateway_reference") or event_id,
        "webhook_event_id": event_id,
        "status": "Paid",
        "initiated_on": now_datetime(),
        "paid_on": now_datetime(),
    })
    payment.insert(ignore_permissions=True)
    subscription_name = payload.get("subscription")
    if subscription_name:
        subscription = frappe.get_doc("User Subscription", subscription_name)
        if subscription.user != user or subscription.company != company:
            frappe.throw("Payment subscription ownership mismatch", frappe.PermissionError)
        if subscription.status == "Overdue":
            subscription.mark_paid(invoice=payment.name)
    result = credit_wallet(
        user=user,
        amount=amount,
        currency=currency,
        external_reference=event_id,
        payment_transaction=payment.name,
        description=payload.get("description") or "Verified payment wallet credit",
    )
    emit_event(
        "Payment Received",
        user,
        "Payment received",
        f"Your payment of {amount} {currency} was received.",
        company=company,
        reference_doctype="Payment Transaction",
        reference_name=payment.name,
        dedupe_key=f"payment-notice:{event_id}",
    )
    frappe.db.commit()
    return {"status": "credited", "payment_transaction": payment.name, **result}


@frappe.whitelist()
def get_wallet():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)
    return get_wallet_summary(frappe.session.user)
