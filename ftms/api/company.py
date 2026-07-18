from __future__ import annotations

import frappe

from ftms.tenant import company_filters


@frappe.whitelist(allow_guest=True)
def list_companies(company=None, limit=100):
	if frappe.session.user == "Guest":
		filters = {"status": "Active", "blacklisted": 0}
	else:
		filters = company_filters(company=company)
	return frappe.get_all(
		"Transportation Company",
		filters=filters,
		fields=["name", "company_code", "company_name", "domain", "status", "blacklisted"],
		order_by="modified desc",
		limit_page_length=int(limit),
	)
