from __future__ import annotations

import frappe
from frappe import _

from ftms.tenant import get_user_company


@frappe.whitelist(allow_guest=True)
def list_companies(company=None, limit=100):
	if frappe.session.user == "Guest":
		filters = {"status": "Active", "blacklisted": 0}
	else:
		active_company = get_user_company()
		if not active_company:
			return []
		if company and company != active_company:
			frappe.throw(_("Not permitted for this company"), frappe.PermissionError)
		filters = {"name": active_company}
	return frappe.get_all(
		"Company",
		filters=filters,
		fields=["name", "company_code", "company_name", "legal_name", "company_name_ar", "vat_no", "tax_id", "cr_no", "domain", "phone", "email", "status", "blacklisted"],
		order_by="modified desc",
		limit_page_length=int(limit),
	)
