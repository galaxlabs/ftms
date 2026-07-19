from __future__ import annotations

import frappe

from ftms.tenant import company_filters, resolve_company


@frappe.whitelist(allow_guest=True)
def list_vehicles(company=None, limit=50):
	filters = company_filters(company=company)
	return frappe.get_all(
		"Vehicle",
		filters=filters,
		fields=["name", "company", "vehicle_code", "vehicle_name", "plate_no", "vehicle_type", "passenger_capacity", "assigned_captain_user", "status"],
		order_by="modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_vehicle(name, company=None):
	doc = frappe.get_doc("Vehicle", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and doc.company != resolved_company:
		frappe.throw("Not permitted for this company")
	return doc.as_dict()
