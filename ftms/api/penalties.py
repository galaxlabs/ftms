from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime

from ftms.api.membership import _require_company_admin
from ftms.wallet.service import credit_wallet


@frappe.whitelist()
def list_penalties(company=None, status=None, limit=100):
	if company:
		_require_company_admin(company)
	else:
		company = frappe.db.get_value("User Company Link", {"user": frappe.session.user, "status": "Active"}, "company")
		if not company:
			frappe.throw(_("Company is required"))
	filters = {"company": company}
	if status:
		filters["status"] = status
	return frappe.get_all("Penalty Entry", filters=filters, fields=["name", "booking", "trip", "actor_user", "actor_type", "basis_amount", "penalty_amount", "currency", "status", "reason", "created_at"], order_by="created_at desc", limit_page_length=int(limit))


@frappe.whitelist()
def waive_penalty(name, reason):
	entry = frappe.get_doc("Penalty Entry", name)
	_require_company_admin(entry.company)
	if entry.status not in ("Pending", "Collected"):
		frappe.throw(_("Only pending or collected penalties can be waived"))
	if entry.status == "Collected":
		refund = credit_wallet(
			user=entry.actor_user,
			amount=entry.penalty_amount,
			currency=entry.currency,
			external_reference=f"penalty-waiver:{entry.name}",
			description=f"Penalty waiver: {reason}",
		)
		entry.db_set("reason", f"{entry.reason or ''}\nWaived: {reason}".strip())
		entry.db_set("status", "Waived")
		return {"name": entry.name, "status": "Waived", "refund_transaction": refund.get("transaction")}
	entry.db_set("reason", f"{entry.reason or ''}\nWaived: {reason}".strip())
	entry.db_set("status", "Waived")
	return {"name": entry.name, "status": "Waived"}
