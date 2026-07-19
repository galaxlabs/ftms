from __future__ import annotations

import frappe

from ftms.tenant import company_filters, resolve_company


@frappe.whitelist(allow_guest=True)
def list_vehicles(company=None, limit=50):
	filters = company_filters(company=company)
	return frappe.get_all(
		"Vehicle",
		filters=filters,
		fields=[
			"name", "company", "vehicle_code", "vehicle_name", "vehicle_name_ar", "plate_no", "plate_no_ar",
			"registration_no", "vehicle_make", "vehicle_model", "vehicle_type", "passenger_capacity",
			"assigned_captain_user", "operation_card_no", "operation_card_expiry_date",
			"registration_expiry_date", "insurance_expiry_date", "status",
		],
		order_by="modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist(allow_guest=True)
def list_vehicle_types(limit=50):
	return frappe.get_all(
		"Vehicle Type",
		filters={"is_active": 1},
		fields=["name", "type_name", "type_name_ar", "vehicle_category", "default_seating_capacity", "is_active"],
		order_by="type_name asc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_vehicle(name, company=None):
	doc = frappe.get_doc("Vehicle", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and doc.company != resolved_company:
		frappe.throw("Not permitted for this company")
	return doc.as_dict()
