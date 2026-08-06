from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, today

from ftms.notifications.service import emit_event

from ftms.tenant import company_filters, get_user_company, resolve_company


def _resolve_user_from_firebase_auth():
	"""Resolve a user from the Firebase Authorization bearer token."""
	auth_header = frappe.get_request_header("Authorization") or ""
	if not auth_header.startswith("Bearer "):
		return None
	id_token = auth_header[7:]
	from ftms.firebase_auth_bridge import verify_id_token, resolve_frappe_user
	try:
		claims = verify_id_token(id_token)
		return resolve_frappe_user(claims)
	except Exception:
		return None


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
		filters={"is_active": 1},
		fields=["name", "make_name", "make_name_ar", "is_active"],
		order_by="make_name asc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def list_vehicle_models(make=None, vehicle_type=None, vehicle_category=None, limit=50):
	filters = {"is_active": 1}
	if make:
		filters["vehicle_make"] = make
	if vehicle_type:
		filters["vehicle_type"] = vehicle_type
	if vehicle_category:
		filters["vehicle_category"] = vehicle_category
	return frappe.get_all(
		"Vehicle Model",
		filters=filters,
		fields=["name", "model_name", "model_name_ar", "vehicle_make", "vehicle_type", "vehicle_category", "is_active"],
		order_by="model_name asc",
		limit_page_length=int(limit),
	)


@frappe.whitelist(allow_guest=True)
def list_vehicle_catalog(make=None, vehicle_type=None, vehicle_category=None, limit=100):
	"""Return dependent vehicle options for driver forms."""
	types = list_vehicle_types(limit=limit)
	makes = list_vehicle_makes(limit=limit)
	models = list_vehicle_models(make=make, vehicle_type=vehicle_type, vehicle_category=vehicle_category, limit=limit)
	return {"types": types, "makes": makes, "models": models}


@frappe.whitelist()
def create_vehicle(
	plate_no, vehicle_name=None,
	vehicle_name_ar=None, plate_no_ar=None,
	vehicle_make=None, vehicle_model=None, vehicle_type=None,
	registration_no=None, model_year=None, color=None,
	seat_capacity=None, passenger_capacity=None,
	fuel_type=None, ownership_type=None,
	engine_no=None, chassis_no=None,
	operation_card_no=None, operation_card_expiry_date=None,
	registration_expiry_date=None, insurance_expiry_date=None,
	operation_card_document=None, registration_document=None, insurance_document=None,
	assigned_captain_user=None, owner_captain_user=None,
	max_luggage_qty=0, max_luggage_weight=None, max_weight_per_passenger=None,
):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)

	resolved_company = get_user_company()
	owner_captain_user = owner_captain_user or user
	if not resolved_company and not frappe.db.exists("Captain Profile", {"user": user}):
		frappe.throw(_("Create a captain profile or join a company before registering a vehicle."))

	vehicle_code = plate_no

	doc = frappe.get_doc({
		"doctype": "Vehicle",
		"company": resolved_company,
		"owner_captain_user": owner_captain_user if not resolved_company else None,
		# Vehicle controller generates vehicle_code and vehicle_name from
		# company abbreviation, plate, make, and model.
		"vehicle_name": vehicle_name or "Pending vehicle name",
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
		"max_luggage_qty": max_luggage_qty or 0,
		"max_luggage_weight": max_luggage_weight,
		"max_weight_per_passenger": max_weight_per_passenger,
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
		"max_luggage_qty": doc.max_luggage_qty,
		"max_luggage_weight": doc.max_luggage_weight,
		"max_weight_per_passenger": doc.max_weight_per_passenger,
	}


@frappe.whitelist(allow_guest=True)
def list_my_vehicles(limit=50):
	user = frappe.session.user
	if user == "Guest":
		user = _resolve_user_from_firebase_auth()
		if not user:
			frappe.throw(_("Login is required"), frappe.PermissionError)
	company = get_user_company()
	filters = {"owner_captain_user": user}
	if company:
		filters = [["company", "=", company], ["assigned_captain_user", "=", user]]
	return frappe.get_all(
		"Vehicle",
		filters=filters,
		fields=["name", "company", "owner_captain_user", "vehicle_name", "plate_no", "vehicle_make", "vehicle_model", "vehicle_type", "passenger_capacity", "status"],
		order_by="modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def record_odometer(vehicle, reading, source="Driver", notes=None):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)
	doc = frappe.get_doc("Vehicle", vehicle)
	if not frappe.db.exists("User Company Link", {"user": user, "company": doc.company, "status": "Active"}):
		frappe.throw(_("You are not permitted to update this vehicle"), frappe.PermissionError)
	log = frappe.get_doc({
		"doctype": "Vehicle Odometer Log",
		"vehicle": vehicle,
		"reading": float(reading),
		"reading_at": now_datetime(),
		"source": source,
		"actor_user": user,
		"notes": notes,
	})
	log.insert(ignore_permissions=True)
	doc.db_set("odometer", log.reading)
	return {"name": log.name, "vehicle": vehicle, "odometer": log.reading, "reading_at": log.reading_at}


@frappe.whitelist()
def create_service_record(vehicle, service_category, service_date, odometer=None,
						  next_service_date=None, next_service_odometer=None, vendor=None,
						  cost=None, attachment=None, notes=None, status="Completed"):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)
	vehicle_doc = frappe.get_doc("Vehicle", vehicle)
	if not frappe.db.exists("User Company Link", {"user": user, "company": vehicle_doc.company, "status": "Active"}):
		frappe.throw(_("You are not permitted to update this vehicle"), frappe.PermissionError)
	if next_service_date and getdate(next_service_date) < getdate(service_date):
		frappe.throw(_("Next service date cannot be before the service date"))
	doc = frappe.get_doc({
		"doctype": "Vehicle Service Record",
		"vehicle": vehicle,
		"service_category": service_category,
		"service_date": service_date,
		"odometer": odometer,
		"next_service_date": next_service_date,
		"next_service_odometer": next_service_odometer,
		"vendor": vendor,
		"cost": cost,
		"attachment": attachment,
		"notes": notes,
		"status": status,
	})
	doc.insert(ignore_permissions=True)
	return {"name": doc.name, "vehicle": vehicle, "status": doc.status}


@frappe.whitelist()
def list_service_reminders(company=None, limit=100):
	resolved_company = resolve_company(company=company)
	rows = frappe.db.sql("""
		SELECT service.name, service.vehicle, service.service_category,
		       service.next_service_date, service.next_service_odometer,
		       vehicle.odometer, vehicle.vehicle_name, vehicle.plate_no
		FROM `tabVehicle Service Record` service
		INNER JOIN `tabVehicle` vehicle ON vehicle.name = service.vehicle
		WHERE vehicle.company=%s
		  AND service.status IN ('Planned', 'Due', 'Completed')
		  AND (service.next_service_date IS NOT NULL OR service.next_service_odometer IS NOT NULL)
		ORDER BY service.next_service_date ASC, service.next_service_odometer ASC
		LIMIT %s
	""", (resolved_company, int(limit)), as_dict=True)
	for row in rows:
		row["date_due"] = bool(row.next_service_date and getdate(row.next_service_date) <= getdate(today()))
		row["odometer_due"] = bool(row.next_service_odometer and (row.odometer or 0) >= row.next_service_odometer)
		row["due"] = row["date_due"] or row["odometer_due"]
	return rows


def mark_due_service_records():
	"""Daily scheduler task that turns due service plans into Due status."""
	for row in frappe.get_all(
		"Vehicle Service Record",
		filters={"status": ["in", ("Planned", "Completed")]},
		fields=["name", "vehicle", "next_service_date", "next_service_odometer"],
	):
		odometer = frappe.db.get_value("Vehicle", row.vehicle, "odometer") or 0
		date_due = row.next_service_date and getdate(row.next_service_date) <= getdate(today())
		odometer_due = row.next_service_odometer and odometer >= row.next_service_odometer
		if date_due or odometer_due:
			frappe.db.set_value("Vehicle Service Record", row.name, "status", "Due")
			company = frappe.db.get_value("Vehicle", row.vehicle, "company")
			for owner in frappe.get_all("User Company Link", filters={"company": company, "status": "Active", "is_owner": 1}, pluck="user"):
				emit_event("Vehicle Service Due", owner, "Vehicle service due", f"Service record {row.name} is due for vehicle {row.vehicle}.", company=company, reference_doctype="Vehicle Service Record", reference_name=row.name, dedupe_key=f"service-due:{row.name}:{getdate(today())}")
