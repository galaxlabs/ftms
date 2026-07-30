from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime

from ftms.api.membership import _require_company_admin
from ftms.wallet.service import credit_wallet


@frappe.whitelist()
def refund_payment(payment_transaction, amount=None, reason=None):
	payment = frappe.get_doc("Payment Transaction", payment_transaction)
	_require_company_admin(payment.company)
	if payment.status not in ("Paid", "Partially Refunded"):
		frappe.throw(_("Only paid transactions can be refunded"))
	refund_amount = float(amount or payment.amount or 0)
	if refund_amount <= 0 or refund_amount > float(payment.amount or 0):
		frappe.throw(_("Refund amount is invalid"))
	result = credit_wallet(
		user=payment.user,
		amount=refund_amount,
		currency=payment.currency,
		external_reference=f"refund:{payment.name}:{refund_amount:.2f}",
		payment_transaction=payment.name,
		description=reason or "Payment refund",
	)
	if result["status"] not in ("credited", "already_processed"):
		frappe.throw(_("Refund could not be credited"))
	total_refunded = frappe.db.sql("""
		SELECT COALESCE(SUM(amount), 0) FROM `tabWallet Transaction`
		WHERE payment_transaction=%s AND transaction_type='Credit'
		  AND external_reference LIKE 'refund:%%'
	""", payment.name)[0][0]
	payment.status = "Refunded" if float(total_refunded or 0) >= float(payment.amount or 0) else "Partially Refunded"
	payment.refunded_on = now_datetime()
	payment.failure_reason = reason
	payment.save(ignore_permissions=True)
	return {"payment_transaction": payment.name, "status": payment.status, "amount": refund_amount, "transaction": result.get("transaction")}


@frappe.whitelist()
def dispute_payment(payment_transaction, reason):
	payment = frappe.get_doc("Payment Transaction", payment_transaction)
	_require_company_admin(payment.company)
	if payment.status in ("Refunded", "Failed"):
		frappe.throw(_("This payment cannot be disputed"))
	payment.status = "Disputed"
	payment.failure_reason = reason
	payment.save(ignore_permissions=True)
	return {"payment_transaction": payment.name, "status": payment.status}
