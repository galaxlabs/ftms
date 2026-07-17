from __future__ import annotations

import frappe

from ftms.tenant import company_filters


@frappe.whitelist()
def list_companies(company=None, limit=100):
	filters = company_filters(company=company)
	return frappe.get_all(
		"Transportation Company",
		filters=filters,
		fields=["name", "company_code", "company_name", "domain", "status", "blacklisted"],
		order_by="modified desc",
		limit_page_length=int(limit),
	)
