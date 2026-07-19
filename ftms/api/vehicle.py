from __future__ import annotations

import frappe
from frappe import _

from ftms.tenant import company_filters, get_user_company, resolve_company


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


@frappe.whitelist()
def list_vehicle_makes(limit=50):
	return frappe.get_all(
		"Vehicle Make",
		fields=["name", "make_name", "make_name_ar", "is_active"],
		order_by="make_name asc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def list_vehicle_models(make=None, limit=50):
	filters = {}
	if make:
		filters["vehicle_make"] = make
	return frappe.get_all(
		"Vehicle Model",
		filters=filters,
		fields=["name", "model_name", "model_name_ar", "vehicle_make", "vehicle_category", "is_active"],
		order_by="model_name asc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def create_vehicle(
	vehicle_name, plate_no,
	vehicle_name_ar=None, plate_no_ar=None,
	vehicle_make=None, vehicle_model=None, vehicle_type=None,
	registration_no=None, model_year=None, color=None,
	seat_capacity=None, passenger_capacity=None,
	fuel_type=None, ownership_type=None,
	engine_no=None, chassis_no=None,
	operation_card_no=None, operation_card_expiry_date=None,
	registration_expiry_date=None, insurance_expiry_date=None,
	operation_card_document=None, registration_document=None, insurance_document=None,
	assigned_captain_user=None,
):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)

	resolved_company = get_user_company()
	if not resolved_company:
		frappe.throw(_("Company is required. You must be linked to a company."))

	vehicle_code = plate_no

	doc = frappe.get_doc({
		"doctype": "Vehicle",
		"company": resolved_company,
		"vehicle_name": vehicle_name,
		"vehicle_name_ar": vehicle_name_ar,
		"plate_no": plate_no,
		"vehicle_code": vehicle_code,
		"plate_no_ar": plate_no_ar,
		"vehicle_make": vehicle_make,
		"vehicle_model": vehicle_model,
		"vehicle_type": vehicle_type,
		"registration_no": registration_no,
		"model_year": model_year,
		"color": color,
		"seat_capacity": seat_capacity,
		"passenger_capacity": passenger_capacity,
		"fuel_type": fuel_type or "Petrol",
		"ownership_type": ownership_type or "Owned",
		"engine_no": engine_no,
		"chassis_no": chassis_no,
		"operation_card_no": operation_card_no,
		"operation_card_expiry_date": operation_card_expiry_date,
		"registration_expiry_date": registration_expiry_date,
		"insurance_expiry_date": insurance_expiry_date,
		"operation_card_document": operation_card_document,
		"registration_document": registration_document,
		"insurance_document": insurance_document,
		"assigned_captain_user": assigned_captain_user,
		"status": "Active",
	})
	doc.insert(ignore_permissions=True)
	return {
		"name": doc.name,
		"vehicle_code": doc.vehicle_code,
		"vehicle_name": doc.vehicle_name,
		"vehicle_name_ar": doc.vehicle_name_ar,
		"plate_no": doc.plate_no,
		"company": doc.company,
		"status": doc.status,
	}
