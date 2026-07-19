from __future__ import annotations

import frappe

from ftms.tenant import resolve_company


@frappe.whitelist()
def list_captains(company=None, limit=50):
	resolved_company = resolve_company(company=company, allow_missing=True)
	filters = {}
	if resolved_company:
		filters["current_company"] = resolved_company
	return frappe.get_all(
		"Captain Profile",
		filters=filters,
		fields=[
			"name", "user", "full_name", "mobile_no", "status", "current_company",
			"id_document_type", "nationality", "iqama_no", "national_id",
			"license_no", "license_expiry_date", "driver_card_no", "driver_card_expiry_date",
			"city", "address", "id_document", "license_document", "driver_card_document",
		],
		order_by="modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_captain(name, company=None):
	doc = frappe.get_doc("Captain Profile", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and doc.current_company != resolved_company:
		frappe.throw("Not permitted for this company")
	return doc.as_dict()
