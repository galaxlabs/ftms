from __future__ import annotations

import frappe

from ftms.tenant import company_filters, resolve_company


@frappe.whitelist()
def list_contracts(company=None, limit=50):
	filters = company_filters(company=company)
	return frappe.get_all(
		"Employee Transport Contract",
		filters=filters,
		fields=["name", "company", "contract_title", "route", "shift_type", "is_active", "last_trip_generated"],
		order_by="modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_contract(name, company=None):
	doc = frappe.get_doc("Employee Transport Contract", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and getattr(doc, "company", None) != resolved_company:
		frappe.throw("Not permitted for this company")
	return doc.as_dict()
