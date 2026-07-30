from __future__ import annotations

from decimal import Decimal

import frappe
from frappe.utils import now_datetime


def _money(value):
    amount = Decimal(str(value or 0))
    if amount <= 0:
        frappe.throw("Amount must be greater than zero")
    return amount.quantize(Decimal("0.01"))


def get_or_create_wallet(user, company=None, currency="SAR"):
    if not user or user == "Guest":
        frappe.throw("A wallet requires an authenticated user", frappe.PermissionError)
    name = frappe.db.get_value("Wallet", {"user": user}, "name")
    if name:
        return frappe.get_doc("Wallet", name)
    wallet = frappe.get_doc({
        "doctype": "Wallet",
        "user": user,
        "company": company,
        "currency": currency or "SAR",
        "balance": 0,
        "reserved_balance": 0,
        "status": "Active",
    })
    wallet.insert(ignore_permissions=True)
    return wallet


def credit_wallet(user, amount, currency="SAR", external_reference=None, payment_transaction=None, description=None):
    amount = _money(amount)
    if external_reference:
        existing = frappe.db.get_value("Wallet Transaction", {"external_reference": external_reference}, "name")
        if existing:
            return {"status": "already_processed", "transaction": existing}

    wallet_name = frappe.db.get_value("Wallet", {"user": user}, "name")
    if not wallet_name:
        wallet = get_or_create_wallet(user=user, currency=currency)
        wallet_name = wallet.name

    row = frappe.db.sql(
        "select name, balance, currency, status from `tabWallet` where name=%s for update",
        (wallet_name,),
        as_dict=True,
    )
    if not row:
        frappe.throw("Wallet not found")
    wallet = row[0]
    if wallet.status != "Active":
        frappe.throw("Wallet is not active")
    if wallet.currency and currency and wallet.currency != currency:
        frappe.throw("Wallet currency does not match payment currency")

    balance_after = Decimal(str(wallet.balance or 0)) + amount
    transaction = frappe.get_doc({
        "doctype": "Wallet Transaction",
        "wallet": wallet_name,
        "user": user,
        "transaction_type": "Credit",
        "status": "Completed",
        "currency": currency or wallet.currency,
        "amount": float(amount),
        "balance_after": float(balance_after),
        "payment_transaction": payment_transaction,
        "external_reference": external_reference,
        "description": description or "Payment wallet credit",
        "created_on": now_datetime(),
    })
    transaction.insert(ignore_permissions=True)
    frappe.db.set_value("Wallet", wallet_name, {
        "balance": float(balance_after),
        "last_transaction_on": now_datetime(),
    }, update_modified=False)
    return {"status": "credited", "wallet": wallet_name, "transaction": transaction.name, "balance": float(balance_after)}


def get_wallet_summary(user):
    wallet = get_or_create_wallet(user=user)
    return {
        "wallet": wallet.name,
        "currency": wallet.currency,
        "balance": float(wallet.balance or 0),
        "reserved_balance": float(wallet.reserved_balance or 0),
        "status": wallet.status,
    }
