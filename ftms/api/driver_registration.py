from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from ftms.api.driver_helpers import get_demo_seed_specs, parse_trip_scan_value
from ftms.api.driver_validation import (
	nearest_city,
	validate_coordinates,
	validate_future_date,
	validate_model_year,
)
from ftms.user_roles import assign_business_role


def _success(**data):
	return {"status": "success", "data": data}


def _require_user():
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)
	return user


def _get_profile(user=None, required=True):
	user = user or _require_user()
	name = frappe.db.get_value("Captain Profile", {"user": user}, "name")
	if not name and required:
		frappe.throw(_("Create a Captain Profile first"), frappe.PermissionError)
	return frappe.get_doc("Captain Profile", name) if name else None


def _ensure_driver_account(user=None):
	"""Repair legacy mobile accounts and provision the driver profile on first login."""
	user = user or _require_user()
	user_doc = frappe.get_doc("User", user)
	roles = {row.role for row in user_doc.roles}
	if user_doc.user_type != "System User":
		frappe.db.set_value("User", user, "user_type", "System User", update_modified=False)
	for role in ("Captain", "Driver"):
		if role not in roles:
			assign_business_role(user, role, onboarded=False)
	profile = _get_profile(user, required=False)
	if not profile:
		profile = frappe.get_doc(
			{
				"doctype": "Captain Profile",
				"user": user,
				"full_name": user_doc.full_name or user,
				"mobile_no": user_doc.mobile_no,
				"status": "Pending",
				"verification_status": "Incomplete",
			}
		)
		profile.insert(ignore_permissions=True)
	return profile


def _clean(value):
	return value.strip() if isinstance(value, str) else value


def _required(values):
	missing = [
		label for label, value in values if value is None or (isinstance(value, str) and not value.strip())
	]
	if missing:
		frappe.throw(_("Required fields: {0}").format(", ".join(missing)))


def _validation_error(callback, *args, **kwargs):
	try:
		return callback(*args, **kwargs)
	except ValueError as exc:
		frappe.throw(_(str(exc)))


def _mask(value, visible=4):
	value = str(value or "")
	return f"{'*' * max(0, len(value) - visible)}{value[-visible:]}" if value else None


def _unique_code(doctype, fieldname, seed, length=24):
	base = re.sub(r"[^A-Z0-9]+", "-", str(seed or "FTMS").upper()).strip("-")[:length] or "FTMS"
	value = base
	counter = 2
	while frappe.db.exists(doctype, {fieldname: value}):
		suffix = f"-{counter}"
		value = f"{base[: length - len(suffix)]}{suffix}"
		counter += 1
	return value


def _default_domain():
	return frappe.db.get_value("Transportation Domain", {"is_active": 1}, "name") or frappe.db.get_value(
		"Transportation Domain", {}, "name"
	)


def _active_company_link(user, company):
	return frappe.db.get_value(
		"User Company Link",
		{"user": user, "company": company, "status": "Active"},
		["name", "role", "is_owner"],
		as_dict=True,
	)


def _my_vehicles(user, limit=200):
	fields = [
		"name",
		"company",
		"owner_captain_user",
		"assigned_captain_user",
		"vehicle_name",
		"plate_no",
		"vehicle_make",
		"vehicle_model",
		"vehicle_type",
		"model_year",
		"passenger_capacity",
		"status",
	]
	owned = frappe.get_all(
		"Vehicle", filters={"owner_captain_user": user}, fields=fields, limit_page_length=limit
	)
	assigned = frappe.get_all(
		"Vehicle", filters={"assigned_captain_user": user}, fields=fields, limit_page_length=limit
	)
	return list({row.name: row for row in owned + assigned}.values())


def _parse_checklist(checklist):
	if isinstance(checklist, str):
		try:
			checklist = json.loads(checklist)
		except json.JSONDecodeError:
			frappe.throw(_("Checklist must be a valid JSON list"))
	if not isinstance(checklist, list) or not checklist:
		frappe.throw(_("Checklist must be a non-empty list"))
	return checklist


def _assigned_trip_from_value(value, user=None):
	user = user or _require_user()
	try:
		token = parse_trip_scan_value(value)
	except ValueError as exc:
		frappe.throw(_(str(exc)))
	filters = {"assigned_captain_user": user}
	if token["kind"] == "public_uuid":
		filters["public_uuid"] = token["value"]
		name = frappe.db.get_value("Trip", filters, "name")
	else:
		name = frappe.db.get_value("Trip", {**filters, "name": token["value"]}, "name")
		if not name:
			name = frappe.db.get_value("Trip", {**filters, "trip_code": token["value"]}, "name")
	if not name:
		frappe.throw(_("Assigned trip not found"), frappe.PermissionError)
	return frappe.get_doc("Trip", name)


def _trip_actions(doc):
	from ftms.ride_machine.state_machine import TripStateMachine

	machine = TripStateMachine(doc)
	allowed_states = machine.transitions.get(doc.trip_status, [])
	return [action for action, state in machine.actions.items() if state in allowed_states]


def _driver_safe_trip(doc):
	company = (
		frappe.db.get_value(
			"Company",
			doc.company,
			["name", "company_code", "company_name", "company_name_ar", "phone", "logo"],
			as_dict=True,
		)
		if doc.company
		else None
	)
	route = (
		frappe.db.get_value(
			"Route",
			doc.route,
			[
				"name",
				"route_title",
				"route_name",
				"route_code",
				"source",
				"destination",
				"from_place_full",
				"to_place_full",
				"distance_km",
				"estimated_duration_minutes",
			],
			as_dict=True,
		)
		if doc.route
		else None
	)
	vehicle = (
		frappe.db.get_value(
			"Vehicle",
			doc.vehicle,
			[
				"name",
				"vehicle_code",
				"vehicle_name",
				"plate_no",
				"vehicle_make",
				"vehicle_model",
				"vehicle_type",
				"model_year",
				"color",
				"passenger_capacity",
			],
			as_dict=True,
		)
		if doc.vehicle
		else None
	)
	return {
		"name": doc.name,
		"trip_code": doc.trip_code,
		"trip_title": doc.trip_title,
		"trip_date": doc.trip_date,
		"trip_status": doc.trip_status,
		"departure_datetime": doc.departure_datetime,
		"planned_arrival_datetime": doc.planned_arrival_datetime,
		"actual_departure_datetime": doc.actual_departure_datetime,
		"actual_arrival_datetime": doc.actual_arrival_datetime,
		"from_location": doc.from_location,
		"to_location": doc.to_location,
		"distance_km": doc.distance_km,
		"duration_minutes": doc.duration_minutes,
		"public_uuid": doc.public_uuid,
		"public_url": doc.public_url,
		"company": company,
		"route": route,
		"vehicle": vehicle,
		"allowed_actions": _trip_actions(doc),
	}


def _driver_safe_kashf(doc):
	company = (
		frappe.db.get_value(
			"Company", doc.company, ["name", "company_code", "company_name", "company_name_ar", "phone", "logo"], as_dict=True
		)
		if doc.company
		else None
	)
	vehicle = (
		frappe.db.get_value(
			"Vehicle",
			doc.vehicle,
			["name", "vehicle_code", "vehicle_name", "plate_no", "vehicle_make", "vehicle_model", "vehicle_type"],
			as_dict=True,
		)
		if doc.vehicle
		else None
	)
	trip = _driver_safe_trip(_assigned_trip_from_value(doc.trip, doc.captain_user)) if doc.trip else None
	return {
		"name": doc.name,
		"inspection_no": doc.inspection_no or doc.name,
		"inspection_date": doc.inspection_date,
		"captain_user": doc.captain_user,
		"company": company,
		"trip": trip,
		"route": doc.route,
		"vehicle": vehicle,
		"current_city": doc.current_city,
		"target_city": doc.target_city,
		"latitude": doc.latitude,
		"longitude": doc.longitude,
		"detected_address": doc.detected_address,
		"odometer": doc.odometer,
		"overall_result": doc.overall_result,
		"status": doc.status,
		"submitted_on": doc.submitted_on,
		"front_photo": doc.front_photo,
		"rear_photo": doc.rear_photo,
		"interior_photo": doc.interior_photo,
		"overall_notes": doc.overall_notes,
		"items": [
			{
				"item_en": row.item_en,
				"category": row.category,
				"item": row.item,
				"status": row.status,
				"notes": row.notes,
				"photo": row.photo,
				"sort_order": row.sort_order,
			}
			for row in doc.items
		],
	}


@frappe.whitelist(methods=["GET"])
def bootstrap():
	user = _require_user()
	profile = _get_profile(user, required=False)
	profile_data = None
	join_requests = []
	if profile:
		profile_data = profile.as_dict(no_nulls=False)
		for fieldname in ("national_id", "iqama_no", "license_no", "driver_card_no"):
			profile_data[fieldname] = _mask(profile_data.get(fieldname))
		join_requests = frappe.get_all(
			"Captain Join Request",
			filters={"captain_profile": profile.name},
			fields=["name", "company", "requested_on", "status", "notes"],
			order_by="requested_on desc",
			limit_page_length=20,
		)
	memberships = frappe.get_all(
		"User Company Link",
		filters={"user": user, "status": ("in", ["Pending", "Active"])},
		fields=["name", "company", "role", "is_owner", "joined_via", "status"],
		order_by="modified desc",
	)
	companies = frappe.get_all(
		"Company",
		filters={"provider_enabled": 1, "status": "Active", "blacklisted": 0},
		fields=["name", "company_name", "legal_name", "address"],
		order_by="company_name asc",
		limit_page_length=500,
	)
	cities = frappe.get_all(
		"KSA City",
		filters={"is_active": 1},
		fields=["name", "city_name", "city_name_ar", "region", "latitude", "longitude"],
		order_by="city_name asc",
		limit_page_length=1000,
	)
	makes = frappe.get_all(
		"Vehicle Make",
		filters={"is_active": 1},
		fields=["name", "make_name", "make_name_ar", "make_code"],
		order_by="make_name asc",
		limit_page_length=500,
	)
	types = frappe.get_all(
		"Vehicle Type",
		filters={"is_active": 1},
		fields=["name", "type_name", "type_name_ar", "vehicle_category", "default_seating_capacity"],
		order_by="type_name asc",
		limit_page_length=500,
	)
	models = frappe.get_all(
		"Vehicle Model",
		filters={"is_active": 1},
		fields=[
			"name",
			"model_name",
			"model_name_ar",
			"vehicle_make",
			"vehicle_type",
			"vehicle_category",
			"model_year_from",
			"model_year_to",
			"seat_capacity",
			"fuel_type",
		],
		order_by="model_name asc",
		limit_page_length=1000,
	)
	checklist = frappe.get_all(
		"Vehicle Inspection Checklist Item",
		filters={"is_active": 1},
		fields=["name", "category", "item", "sort_order"],
		order_by="category asc, sort_order asc, creation asc",
		limit_page_length=500,
	)
	return _success(
		profile=profile_data,
		companies=companies,
		memberships=memberships,
		join_requests=join_requests,
		vehicles=_my_vehicles(user),
		cities=cities,
		vehicle_catalog={"makes": makes, "types": types, "models": models},
		checklist=checklist,
	)


@frappe.whitelist(methods=["POST"])
def ensure_driver_account():
	"""Provision or repair the authenticated account used by the driver app."""
	user = _require_user()
	profile = _ensure_driver_account(user)
	frappe.db.commit()
	return _success(
		user=user,
		user_type="System User",
		roles=sorted({"Captain", "Driver"}.intersection(frappe.get_roles(user))),
		captain_profile=profile.name,
	)


@frappe.whitelist(methods=["GET"])
def list_my_trips(limit=50, status=None):
	user = _require_user()
	filters = {"assigned_captain_user": user}
	if status:
		valid_statuses = {"Draft", "Scheduled", "Departed", "Arrived", "Completed", "Cancelled"}
		if status not in valid_statuses:
			frappe.throw(_("Invalid trip status"))
		filters["trip_status"] = status
	names = frappe.get_all(
		"Trip",
		filters=filters,
		pluck="name",
		order_by="trip_date desc, modified desc",
		limit_page_length=min(max(cint(limit), 1), 200),
	)
	return _success(trips=[_driver_safe_trip(frappe.get_doc("Trip", name)) for name in names])


@frappe.whitelist(methods=["GET", "POST"])
def resolve_scanned_trip(value):
	doc = _assigned_trip_from_value(value)
	return _success(trip=_driver_safe_trip(doc))


@frappe.whitelist(methods=["POST"])
def transition_my_trip(value, action):
	user = _require_user()
	doc = _assigned_trip_from_value(value, user)
	if action not in {"schedule", "depart", "arrive", "complete", "cancel"}:
		frappe.throw(_("Invalid trip action"))
	locked = frappe.db.sql(
		"SELECT name FROM `tabTrip` WHERE name = %s AND assigned_captain_user = %s FOR UPDATE",
		(doc.name, user),
	)
	if not locked:
		frappe.throw(_("Assigned trip not found"), frappe.PermissionError)
	doc.reload()
	from ftms.ride_machine.state_machine import TripStateMachine

	TripStateMachine(doc).action(action)
	# Ownership was checked above; normal Trip write permission may intentionally exclude mobile captains.
	doc.flags.ignore_company_validation = True
	doc.save(ignore_permissions=True)
	return _success(trip=_driver_safe_trip(doc))


@frappe.whitelist(methods=["POST"])
def submit_identity(
	full_name=None,
	mobile_no=None,
	id_document_type=None,
	identity_no=None,
	id_expiry_date=None,
	license_no=None,
	license_expiry_date=None,
	nationality=None,
	city=None,
	address=None,
	id_document=None,
	license_document=None,
	driver_card_no=None,
	driver_card_expiry_date=None,
):
	user = _require_user()
	values = {key: _clean(value) for key, value in locals().copy().items() if key != "user"}
	_required(
		[
			("Full name", values["full_name"]),
			("Mobile number", values["mobile_no"]),
			("ID document type", values["id_document_type"]),
			("Identity number", values["identity_no"]),
			("ID expiry date", values["id_expiry_date"]),
			("License number", values["license_no"]),
			("License expiry date", values["license_expiry_date"]),
			("Nationality", values["nationality"]),
			("City", values["city"]),
			("Address", values["address"]),
			("ID attachment", values["id_document"]),
			("License attachment", values["license_document"]),
		]
	)
	# Identity format enforcement is intentionally deferred during the driver pilot.
	identity_no = str(values["identity_no"]).strip()
	if len(identity_no) > 140:
		frappe.throw(_("Identity number is too long"))
	_validation_error(validate_future_date, values["id_expiry_date"], "ID expiry date")
	_validation_error(validate_future_date, values["license_expiry_date"], "License expiry date")
	if values["driver_card_expiry_date"]:
		_validation_error(validate_future_date, values["driver_card_expiry_date"], "Driver card expiry date")
	if not frappe.db.exists("KSA City", {"name": values["city"], "is_active": 1}):
		frappe.throw(_("Select an active KSA city"))

	existing_name = frappe.db.get_value("Captain Profile", {"user": user}, "name")
	for fieldname, value, label in (
		("national_id", identity_no, "Identity number"),
		("iqama_no", identity_no if values["id_document_type"] == "Iqama" else None, "Iqama number"),
		("license_no", values["license_no"], "License number"),
	):
		if value and frappe.db.exists(
			"Captain Profile", {fieldname: value, "name": ("!=", existing_name or "")}
		):
			frappe.throw(_("{0} is already registered").format(label))
	doc = (
		frappe.get_doc("Captain Profile", existing_name)
		if existing_name
		else frappe.get_doc({"doctype": "Captain Profile", "user": user, "status": "Pending"})
	)
	doc.update(
		{
			"full_name": values["full_name"],
			"mobile_no": values["mobile_no"],
			"id_document_type": values["id_document_type"],
			"national_id": identity_no,
			"iqama_no": identity_no if values["id_document_type"] == "Iqama" else None,
			"iqama_expiry_date": values["id_expiry_date"] if values["id_document_type"] == "Iqama" else None,
			"id_expiry_date": values["id_expiry_date"],
			"license_no": values["license_no"],
			"license_expiry_date": values["license_expiry_date"],
			"nationality": values["nationality"],
			"city": values["city"],
			"address": values["address"],
			"id_document": values["id_document"],
			"license_document": values["license_document"],
			"driver_card_no": values["driver_card_no"],
			"driver_card_expiry_date": values["driver_card_expiry_date"],
			"verification_status": "Under Review",
			"rejection_reason": None,
		}
	)
	doc.save(ignore_permissions=True)
	assign_business_role(user, "Captain", onboarded=True)
	assign_business_role(user, "Driver", onboarded=True)
	frappe.db.commit()
	return _success(
		captain_profile=doc.name, verification_status=doc.verification_status, created=not bool(existing_name)
	)


@frappe.whitelist(methods=["POST"])
def register_company(
	company_name=None,
	legal_name=None,
	vat_no=None,
	cr_no=None,
	address=None,
	cr_document=None,
	vat_certificate=None,
	transport_license_document=None,
):
	user = _require_user()
	profile = _get_profile(user)
	company_name = _clean(company_name)
	legal_name = _clean(legal_name)
	vat_no = _clean(vat_no)
	cr_no = _clean(cr_no)
	_required(
		[
			("Company name", company_name),
			("Legal name", legal_name),
			("VAT number", vat_no),
			("CR number", cr_no),
			("Address", address),
			("CR document", cr_document),
			("VAT certificate", vat_certificate),
			("Transport license document", transport_license_document),
		]
	)
	for fieldname, value, label in (
		("company_name", company_name, "Company name"),
		("vat_no", vat_no, "VAT number"),
		("cr_no", cr_no, "CR number"),
	):
		if frappe.db.exists("Company", {fieldname: value}):
			frappe.throw(_("{0} is already registered").format(label))
	domain = _default_domain()
	if not domain:
		frappe.throw(_("No Transportation Domain is configured"))
	company = frappe.get_doc(
		{
			"doctype": "Company",
			"company_code": _unique_code("Company", "company_code", cr_no),
			"company_name": company_name,
			"legal_name": legal_name,
			"vat_no": vat_no,
			"cr_no": cr_no,
			"domain": domain,
			"organization_type": "Transport Provider",
			"provider_enabled": 1,
			"customer_enabled": 0,
			"owner_user": user,
			"address": _clean(address),
			"email": user,
			"onboarding_status": "Draft",
			"status": "Inactive",
			"cr_document": cr_document,
			"vat_certificate": vat_certificate,
			"transport_license_document": transport_license_document,
			"documents_status": "Under Review",
		}
	)
	company.insert(ignore_permissions=True)
	link = frappe.get_doc(
		{
			"doctype": "User Company Link",
			"link_code": _unique_code("User Company Link", "link_code", f"{company.name}-{user}", 140),
			"user": user,
			"company": company.name,
			"role": "Company Admin",
			"is_owner": 1,
			"joined_via": "Signup",
			"status": "Active",
			"approved_by": user,
			"approved_on": now_datetime(),
		}
	)
	link.insert(ignore_permissions=True)
	profile.current_company = company.name
	profile.save(ignore_permissions=True)
	frappe.db.commit()
	return _success(company=company.name, membership=link.name, documents_status=company.documents_status)


@frappe.whitelist(methods=["POST"])
def request_company(company):
	user = _require_user()
	profile = _get_profile(user)
	if not frappe.db.exists(
		"Company", {"name": company, "provider_enabled": 1, "status": "Active", "blacklisted": 0}
	):
		frappe.throw(_("Select an active transport provider company"))
	if _active_company_link(user, company):
		frappe.throw(_("You already have an active membership in this company"))
	if frappe.db.exists(
		"Captain Join Request", {"captain_profile": profile.name, "company": company, "status": "Pending"}
	):
		frappe.throw(_("A pending request already exists for this company"))
	doc = frappe.get_doc(
		{
			"doctype": "Captain Join Request",
			"captain_profile": profile.name,
			"company": company,
			"requested_by": user,
			"requested_on": now_datetime(),
			"status": "Pending",
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return _success(join_request=doc.name, company=company)


@frappe.whitelist(methods=["POST"])
def register_vehicle(
	vehicle_make=None,
	vehicle_model=None,
	vehicle_type=None,
	plate_no=None,
	model_year=None,
	passenger_capacity=None,
	company=None,
	registration_no=None,
	registration_expiry_date=None,
	insurance_expiry_date=None,
	operation_card_no=None,
	operation_card_expiry_date=None,
	registration_document=None,
	insurance_document=None,
	operation_card_document=None,
	vehicle_ownership_document=None,
	color=None,
	chassis_no=None,
	fuel_type=None,
	owner_captain_user=None,
	assigned_captain_user=None,
):
	user = _require_user()
	profile = _get_profile(user)
	_required(
		[
			("Make", vehicle_make),
			("Model", vehicle_model),
			("Vehicle type", vehicle_type),
			("Plate number", plate_no),
			("Model year", model_year),
			("Passenger capacity", passenger_capacity),
			("Registration expiry", registration_expiry_date),
			("Insurance expiry", insurance_expiry_date),
			("Registration document", registration_document),
			("Insurance document", insurance_document),
		]
	)
	if owner_captain_user and owner_captain_user != user:
		frappe.throw(_("A captain may only register a vehicle they own"), frappe.PermissionError)
	if assigned_captain_user and assigned_captain_user != user:
		frappe.throw(_("A captain may only assign the vehicle to themselves"), frappe.PermissionError)
	company_doc = None
	if company:
		if not _active_company_link(user, company):
			frappe.throw(_("No active membership in the selected company"), frappe.PermissionError)
		company_doc = frappe.db.get_value(
			"Company", company, ["name", "status", "documents_status"], as_dict=True
		)
		if not company_doc:
			frappe.throw(_("Selected company does not exist"))
	model = frappe.db.get_value(
		"Vehicle Model",
		{"name": vehicle_model, "is_active": 1},
		["vehicle_make", "vehicle_type", "model_year_from", "model_year_to", "seat_capacity", "fuel_type"],
		as_dict=True,
	)
	if not model or model.vehicle_make != vehicle_make or model.vehicle_type != vehicle_type:
		frappe.throw(_("Selected make, model, and vehicle type do not match"))
	year = _validation_error(validate_model_year, model_year, model.model_year_from, model.model_year_to)
	capacity = cint(passenger_capacity)
	seat_capacity = cint(model.seat_capacity) or cint(
		frappe.db.get_value("Vehicle Type", vehicle_type, "default_seating_capacity")
	)
	if capacity <= 0:
		frappe.throw(_("Passenger capacity must be positive"))
	if seat_capacity and capacity > seat_capacity:
		frappe.throw(
			_("Passenger capacity cannot exceed the catalog seat capacity of {0}").format(seat_capacity)
		)
	_validation_error(validate_future_date, registration_expiry_date, "Registration expiry date")
	_validation_error(validate_future_date, insurance_expiry_date, "Insurance expiry date")
	if operation_card_expiry_date:
		_validation_error(validate_future_date, operation_card_expiry_date, "Operation card expiry date")
	if any((operation_card_no, operation_card_expiry_date, operation_card_document)):
		_required(
			[
				("Operation card number", operation_card_no),
				("Operation card expiry date", operation_card_expiry_date),
				("Operation card document", operation_card_document),
			]
		)
	status = (
		"Active"
		if profile.status == "Active"
		and (
			not company_doc or (company_doc.status == "Active" and company_doc.documents_status == "Verified")
		)
		else "Draft"
	)
	doc = frappe.get_doc(
		{
			"doctype": "Vehicle",
			"company": company,
			"owner_captain_user": user,
			"assigned_captain_user": user,
			"vehicle_name": "Pending vehicle name",
			"plate_no": _clean(plate_no),
			"vehicle_make": vehicle_make,
			"vehicle_model": vehicle_model,
			"vehicle_type": vehicle_type,
			"model_year": year,
			"seat_capacity": seat_capacity or capacity,
			"passenger_capacity": capacity,
			"registration_no": _clean(registration_no),
			"registration_expiry_date": registration_expiry_date,
			"insurance_expiry_date": insurance_expiry_date,
			"operation_card_no": _clean(operation_card_no),
			"operation_card_expiry_date": operation_card_expiry_date,
			"registration_document": registration_document,
			"insurance_document": insurance_document,
			"operation_card_document": operation_card_document,
			"vehicle_ownership_document": vehicle_ownership_document,
			"color": _clean(color),
			"chassis_no": _clean(chassis_no),
			"fuel_type": fuel_type or model.fuel_type or "Petrol",
			"ownership_type": "Owned",
			"status": status,
			"is_active": int(status == "Active"),
		}
	)
	doc.flags.ignore_company_validation = True
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return _success(vehicle=doc.name, vehicle_code=doc.vehicle_code, status=doc.status)


@frappe.whitelist(methods=["POST"])
def create_kashf(
	vehicle,
	target_city,
	latitude,
	longitude,
	checklist,
	detected_address=None,
	odometer=None,
	front_photo=None,
	rear_photo=None,
	interior_photo=None,
	overall_notes=None,
	trip=None,
):
	user = _require_user()
	profile = _get_profile(user)
	if profile.status != "Active":
		frappe.throw(_("Only an Active Captain can submit Kashf"), frappe.PermissionError)
	vehicle_doc = frappe.db.get_value(
		"Vehicle",
		vehicle,
		["name", "company", "owner_captain_user", "assigned_captain_user", "vehicle_type", "odometer"],
		as_dict=True,
	)
	if not vehicle_doc or user not in (vehicle_doc.owner_captain_user, vehicle_doc.assigned_captain_user):
		frappe.throw(_("Vehicle is not owned by or assigned to the current captain"), frappe.PermissionError)
	if vehicle_doc.company and not _active_company_link(user, vehicle_doc.company):
		frappe.throw(_("No active membership in the vehicle company"), frappe.PermissionError)
	trip_doc = None
	if trip:
		trip_doc = _assigned_trip_from_value(trip, user)
		if trip_doc.company != vehicle_doc.company:
			frappe.throw(_("Trip and vehicle must belong to the same company"), frappe.PermissionError)
		if trip_doc.vehicle != vehicle_doc.name:
			frappe.throw(_("Kashf vehicle must match the assigned trip vehicle"), frappe.PermissionError)
	if not frappe.db.exists("KSA City", {"name": target_city, "is_active": 1}):
		frappe.throw(_("Select an active target city"))
	latitude, longitude = _validation_error(validate_coordinates, latitude, longitude)
	cities = frappe.get_all(
		"KSA City", filters={"is_active": 1}, fields=["name", "latitude", "longitude"], limit_page_length=1000
	)
	current_city, distance_km = _validation_error(nearest_city, latitude, longitude, cities)
	if current_city.name == target_city:
		frappe.throw(_("Target city must differ from the detected current city"))
	rows = _parse_checklist(checklist)
	master_items = set(
		frappe.get_all(
			"Vehicle Inspection Checklist Item", filters={"is_active": 1}, pluck="name", limit_page_length=500
		)
	)
	inspection_items = []
	seen = set()
	unsound = False
	for row in rows:
		if not isinstance(row, dict):
			frappe.throw(_("Each checklist item must be an object"))
		item_name = row.get("item_en") or row.get("item") or row.get("name")
		if item_name not in master_items or item_name in seen:
			frappe.throw(
				_("Checklist contains an invalid or duplicate item: {0}").format(item_name or "(missing)")
			)
		seen.add(item_name)
		status = row.get("status")
		status = {"Passed": "Sound | سليم", "Failed": "Unsound | غير سليم"}.get(status, status)
		if status not in ("Sound | سليم", "Unsound | غير سليم"):
			frappe.throw(_("Invalid checklist status for {0}").format(item_name))
		master = frappe.db.get_value(
			"Vehicle Inspection Checklist Item", item_name, ["category", "item", "sort_order"], as_dict=True
		)
		inspection_items.append(
			{
				"item_en": item_name,
				"section": master.category,
				"category": master.category,
				"item": master.item,
				"sort_order": master.sort_order,
				"status": status,
				"notes": _clean(row.get("notes")),
				"photo": row.get("photo"),
			}
		)
		unsound = unsound or status == "Unsound | غير سليم"
	missing_items = master_items - seen
	if missing_items:
		frappe.throw(_("Checklist is incomplete; {0} active item(s) are missing").format(len(missing_items)))
	if odometer is not None and flt(odometer) < flt(vehicle_doc.odometer):
		frappe.throw(_("Odometer cannot be lower than the vehicle's current reading"))
	driver = frappe.db.get_value("Employee", {"email": user}, "name") or frappe.db.get_value(
		"Employee", {"user_id": user}, "name"
	)
	doc = frappe.get_doc(
		{
			"doctype": "Vehicle Inspection Log",
			"inspection_date": frappe.utils.today(),
			"driver": driver,
			"captain_user": user,
			"company": vehicle_doc.company,
			"trip": trip_doc.name if trip_doc else None,
			"route": trip_doc.route if trip_doc else None,
			"vehicle": vehicle,
			"vehicle_type": vehicle_doc.vehicle_type,
			"current_city": current_city.name,
			"target_city": target_city,
			"latitude": latitude,
			"longitude": longitude,
			"detected_address": _clean(detected_address),
			"odometer": odometer,
			"overall_result": "Requires Attention" if unsound else "Passed",
			"status": "Submitted",
			"submitted_on": now_datetime(),
			"front_photo": front_photo,
			"rear_photo": rear_photo,
			"interior_photo": interior_photo,
			"overall_notes": _clean(overall_notes),
			"auto_fill_checklist": 0,
			"items": inspection_items,
		}
	)
	doc.insert(ignore_permissions=True)
	if odometer is not None and flt(odometer) > flt(vehicle_doc.odometer):
		frappe.db.set_value("Vehicle", vehicle, "odometer", flt(odometer), update_modified=False)
	frappe.db.commit()
	return _success(
		kashf=doc.name,
		inspection_no=doc.inspection_no or doc.name,
		current_city=current_city.name,
		nearest_city_distance_km=round(distance_km, 2),
		overall_result=doc.overall_result,
		trip=doc.trip,
		route=doc.route,
		company=doc.company,
		vehicle=doc.vehicle,
	)


@frappe.whitelist(methods=["GET"])
def list_my_kashf(limit=50):
	user = _require_user()
	rows = frappe.get_all(
		"Vehicle Inspection Log",
		filters={"captain_user": user},
		fields=[
			"name",
			"inspection_no",
			"inspection_date",
			"company",
			"trip",
			"route",
			"vehicle",
			"vehicle_type",
			"current_city",
			"target_city",
			"odometer",
			"overall_result",
			"status",
			"submitted_on",
			"creation",
			"modified",
		],
		order_by="creation desc",
		limit_page_length=min(max(cint(limit), 1), 200),
	)
	for row in rows:
		row["items"] = frappe.get_all(
			"Vehicle Inspection Item",
			filters={"parent": row.name, "parenttype": "Vehicle Inspection Log", "parentfield": "items"},
			fields=["item_en", "category", "item", "status", "notes", "photo", "sort_order"],
			order_by="idx asc",
		)
	return _success(kashf=rows)


@frappe.whitelist(methods=["GET"])
def get_my_kashf(name):
	user = _require_user()
	name = frappe.db.get_value("Vehicle Inspection Log", {"name": name, "captain_user": user}, "name")
	if not name:
		frappe.throw(_("Kashf not found"), frappe.PermissionError)
	return _success(kashf=_driver_safe_kashf(frappe.get_doc("Vehicle Inspection Log", name)))


@frappe.whitelist(methods=["GET"])
def get_my_kashf_pdf(name):
	user = _require_user()
	name = frappe.db.get_value("Vehicle Inspection Log", {"name": name, "captain_user": user}, "name")
	if not name:
		frappe.throw(_("Kashf not found"), frappe.PermissionError)
	from frappe.utils.pdf import get_pdf

	html = frappe.get_print("Vehicle Inspection Log", name, print_format="Kashf Driver")
	frappe.response.filename = f"{name}-kashf.pdf"
	frappe.response.filecontent = get_pdf(html)
	frappe.response.type = "download"
	return None


@frappe.whitelist(methods=["POST"])
def seed_demo_data(password=None):
	"""Seed an idempotent, Administrator-only RideKSA driver test fleet."""
	if frappe.session.user != "Administrator":
		frappe.throw(_("Only Administrator can seed demo data"), frappe.PermissionError)
	domain = _default_domain()
	if not domain:
		frappe.throw(_("No Transportation Domain is configured"))
	created = []

	def ensure(doctype, name, values):
		if frappe.db.exists(doctype, name):
			frappe.db.set_value(doctype, name, values, update_modified=False)
			return name
		doc = frappe.get_doc({"doctype": doctype, **values})
		doc.insert(ignore_permissions=True)
		created.append(f"{doctype}:{doc.name}")
		return doc.name

	category = ensure(
		"Vehicle Category",
		"TEST RideKSA Category",
		{
			"category_name": "TEST RideKSA Category",
			"status": "Active",
			"is_active": 1,
		},
	)
	vehicle_type = ensure(
		"Vehicle Type",
		"TEST RideKSA Sedan",
		{
			"type_name": "TEST RideKSA Sedan",
			"type_code": "TEST-RKS",
			"vehicle_category": category,
			"default_seating_capacity": 5,
			"status": "Active",
			"is_active": 1,
		},
	)
	make = ensure(
		"Vehicle Make",
		"TEST RideKSA Motors",
		{
			"make_name": "TEST RideKSA Motors",
			"make_code": "TEST-RKS",
			"status": "Active",
			"is_active": 1,
		},
	)
	model = ensure(
		"Vehicle Model",
		"TEST RideKSA Model",
		{
			"model_name": "TEST RideKSA Model",
			"model_code": "TEST-RKS",
			"vehicle_make": make,
			"vehicle_type": vehicle_type,
			"vehicle_category": category,
			"model_year_from": 2020,
			"seat_capacity": 5,
			"fuel_type": "Petrol",
			"status": "Active",
			"is_active": 1,
		},
	)
	seed_specs = get_demo_seed_specs()
	company_specs = seed_specs["companies"]
	companies = []
	for company_index, (code, company_name, legal_name, color, footer) in enumerate(
		company_specs, start=1
	):
		vat_no = f"3100000000000{company_index:02d}"
		cr_no = f"10100000{company_index:02d}"
		phone = f"+9661155500{company_index:02d}"
		email = f"test.company.{company_index}@example.com"
		company = frappe.db.get_value("Company", {"company_code": code}, "name") or frappe.db.get_value(
			"Company", {"company_name": company_name}, "name"
		)
		if not company:
			doc = frappe.get_doc(
				{
					"doctype": "Company",
					"company_code": code,
					"company_name": company_name,
					"legal_name": legal_name,
					"domain": domain,
					"organization_type": "Transport Provider",
					"provider_enabled": 1,
					"customer_enabled": 0,
					"address": f"{company_name} TEST address",
					"vat_no": vat_no,
					"cr_no": cr_no,
					"phone": phone,
					"email": email,
					"onboarding_status": "Active",
					"documents_status": "Verified",
					"primary_color": color,
					"footer_text": footer,
					"enable_kashf": 1,
					"status": "Active",
				}
			)
			doc.insert(ignore_permissions=True)
			company = doc.name
			created.append(f"Company:{company}")
		else:
			frappe.db.set_value(
				"Company",
				company,
				{
					"company_code": code,
					"company_name": company_name,
					"legal_name": legal_name,
					"vat_no": vat_no,
					"cr_no": cr_no,
					"address": f"{company_name} TEST address",
					"phone": phone,
					"email": email,
					"primary_color": color,
					"footer_text": footer,
					"provider_enabled": 1,
					"documents_status": "Verified",
					"onboarding_status": "Active",
					"enable_kashf": 1,
					"status": "Active",
				},
			)
		companies.append(company)

	user_specs = tuple(
		(email, full_name, companies[company_index], role, is_owner)
		for email, full_name, company_index, role, is_owner in seed_specs["users"]
	)
	users = []
	for index, (email, full_name, company, membership_role, is_owner) in enumerate(user_specs, start=1):
		user_exists = frappe.db.exists("User", email)
		if user_exists:
			user_doc = frappe.get_doc("User", email)
			if password:
				user_doc.new_password = password
				user_doc.save(ignore_permissions=True)
		else:
			user_doc = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": full_name,
					"mobile_no": f"+9665500000{index:02d}",
					"enabled": 1,
					"user_type": "System User",
					"send_welcome_email": 0,
					"new_password": password or frappe.generate_hash(length=32),
				}
			)
			user_doc.insert(ignore_permissions=True)
			created.append(f"User:{email}")
		assign_business_role(email, "Captain", onboarded=True)
		assign_business_role(email, "Driver", onboarded=True)
		if membership_role == "Company Admin":
			assign_business_role(email, "Company Admin", onboarded=True)
		profile_name = frappe.db.get_value("Captain Profile", {"user": email}, "name")
		profile_values = {
			"full_name": full_name,
			"mobile_no": f"+9665500000{index:02d}",
			"id_document_type": "National ID",
			"nationality": "Saudi Arabia",
			"national_id": f"1{index:09d}",
			"id_expiry_date": "2035-12-31",
			"license_no": f"TEST-LIC-{index:04d}",
			"license_expiry_date": "2035-12-31",
			"driver_card_no": f"TEST-DRV-{index:04d}",
			"driver_card_expiry_date": "2035-12-31",
			"current_company": company,
			"verification_status": "Verified",
			"status": "Active",
		}
		if profile_name:
			profile = frappe.get_doc("Captain Profile", profile_name)
			profile.update(profile_values)
			profile.save(ignore_permissions=True)
		else:
			profile = frappe.get_doc({"doctype": "Captain Profile", "user": email, **profile_values})
			profile.insert(ignore_permissions=True)
			created.append(f"Captain Profile:{profile.name}")
		link_name = frappe.db.get_value(
			"User Company Link", {"user": email, "company": company, "role": membership_role}, "name"
		)
		if not link_name:
			link = frappe.get_doc(
				{
					"doctype": "User Company Link",
					"link_code": _unique_code("User Company Link", "link_code", f"TEST-{company}-{email}", 140),
					"user": email,
					"company": company,
					"role": membership_role,
					"is_owner": is_owner,
					"joined_via": "Admin",
					"status": "Active",
					"approved_by": "Administrator",
					"approved_on": now_datetime(),
				}
			)
			link.insert(ignore_permissions=True)
			created.append(f"User Company Link:{link.name}")
		else:
			frappe.db.set_value(
				"User Company Link",
				link_name,
				{"status": "Active", "is_owner": is_owner, "approved_by": "Administrator", "approved_on": now_datetime()},
			)
		users.append({"email": email, "company": company, "role": membership_role})

	vehicle_specs = (
		(companies[0], user_specs[1][0], user_specs[1][0], "TEST-A-1001", "TEST-CHASSIS-A-1001"),
		(companies[0], user_specs[0][0], user_specs[1][0], "TEST-A-1002", "TEST-CHASSIS-A-1002"),
		(companies[1], user_specs[3][0], user_specs[3][0], "TEST-B-2001", "TEST-CHASSIS-B-2001"),
		(companies[2], user_specs[4][0], user_specs[4][0], "TEST-C-3001", "TEST-CHASSIS-C-3001"),
	)
	vehicles = []
	for vehicle_index, (company, owner, captain, plate_no, chassis_no) in enumerate(
		vehicle_specs, start=1
	):
		vehicle_code = f"TEST-RKS-VEH-{vehicle_index}"
		vehicle_name = frappe.db.get_value("Vehicle", {"company": company, "plate_no": plate_no}, "name")
		if not vehicle_name:
			vehicle = frappe.get_doc(
				{
					"doctype": "Vehicle",
					"company": company,
					"vehicle_code": vehicle_code,
					"owner_captain_user": owner,
					"assigned_captain_user": captain,
					"vehicle_name": plate_no,
					"plate_no": plate_no,
					"vehicle_make": make,
					"vehicle_model": model,
					"vehicle_type": vehicle_type,
					"model_year": 2024,
					"seat_capacity": 5,
					"passenger_capacity": 4,
					"fuel_type": "Petrol",
					"ownership_type": "Owned",
					"chassis_no": chassis_no,
					"status": "Active",
					"is_active": 1,
				}
			)
			vehicle.insert(ignore_permissions=True)
			vehicle_name = vehicle.name
			created.append(f"Vehicle:{vehicle_name}")
		else:
			frappe.db.set_value(
				"Vehicle",
				vehicle_name,
				{
					"vehicle_code": vehicle_code,
					"owner_captain_user": owner,
					"assigned_captain_user": captain,
					"status": "Active",
					"is_active": 1,
				},
			)
		vehicles.append(vehicle_name)
		assignment = frappe.db.get_value(
			"Vehicle Assignment",
			{"company": company, "vehicle": vehicle_name, "captain_user": captain},
			"name",
		)
		if not assignment:
			assignment_doc = frappe.get_doc(
				{
					"doctype": "Vehicle Assignment",
					"company": company,
					"vehicle": vehicle_name,
					"captain_user": captain,
					"from_date": frappe.utils.today(),
					"status": "Active",
					"notes": "TEST RideKSA seed assignment",
				}
			)
			assignment_doc.insert(ignore_permissions=True)
			created.append(f"Vehicle Assignment:{assignment_doc.name}")
		else:
			frappe.db.set_value("Vehicle Assignment", assignment, "status", "Active")

	ensure(
		"Vehicle Inspection Checklist Item",
		"TEST RideKSA Basic Safety Check",
		{
			"item": "TEST RideKSA Basic Safety Check",
			"category": "Safety & Security Tools | أدوات ومتطلبات السلامة",
			"sort_order": 999,
			"is_active": 1,
		},
	)
	for city_name, latitude, longitude in (
		("TEST RideKSA Origin", 24.7136, 46.6753),
		("TEST RideKSA Destination", 21.4858, 39.1925),
	):
		ensure(
			"KSA City",
			city_name,
			{
				"city_name": city_name,
				"city_name_ar": city_name,
				"region": "TEST Region",
				"latitude": latitude,
				"longitude": longitude,
				"is_active": 1,
			},
		)

	captains = {
		company: next(user[0] for user in user_specs if user[2] == company and user[3] == "Captain")
		for company in companies
	}
	driver_vehicles = {
		company: next(
			name
			for name in vehicles
			if frappe.db.get_value("Vehicle", name, "company") == company
			and frappe.db.get_value("Vehicle", name, "assigned_captain_user") == captains[company]
		)
		for company in companies
	}
	routes = []
	trips = []
	for index, company in enumerate(companies, start=1):
		route_title = f"TEST RideKSA Route {index}"
		route = ensure(
			"Route",
			route_title,
			{
				"company": company,
				"route_title": route_title,
				"route_name": route_title,
				"route_code": f"TEST-RKS-ROUTE-{index}",
				"source": "TEST RideKSA Origin",
				"destination": "TEST RideKSA Destination",
				"route_type": "Intercity",
				"status": "Active",
				"is_active": 1,
			},
		)
		routes.append(route)
		trip_code = f"TEST-RKS-TRIP-{index}"
		trip = frappe.db.get_value("Trip", {"trip_code": trip_code}, "name")
		trip_values = {
			"company": company,
			"trip_title": f"TEST RideKSA Trip {index}",
			"trip_code": trip_code,
			"trip_date": frappe.utils.today(),
			"trip_status": "Scheduled",
			"route": route,
			"vehicle": driver_vehicles[company],
			"assigned_captain_user": captains[company],
		}
		if trip:
			frappe.db.set_value("Trip", trip, trip_values, update_modified=False)
		else:
			trip_doc = frappe.get_doc({"doctype": "Trip", **trip_values})
			trip_doc.flags.ignore_company_validation = True
			trip_doc.insert(ignore_permissions=True)
			trip = trip_doc.name
			created.append(f"Trip:{trip}")
		trips.append(trip)

	checklist = frappe.get_all(
		"Vehicle Inspection Checklist Item",
		filters={"is_active": 1},
		fields=["name", "category", "item", "sort_order"],
		order_by="category asc, sort_order asc, creation asc",
	)
	inspections = []
	if checklist:
		for index, company in enumerate(companies):
			marker = f"TEST RideKSA seed inspection:{company}"
			inspection = frappe.db.get_value("Vehicle Inspection Log", {"company": company, "overall_notes": marker}, "name")
			if not inspection:
				vehicle_name = driver_vehicles[company]
				captain = captains[company]
				inspection_doc = frappe.get_doc(
					{
						"doctype": "Vehicle Inspection Log",
						"inspection_date": frappe.utils.today(),
						"captain_user": captain,
						"company": company,
						"trip": trips[index],
						"route": routes[index],
						"vehicle": vehicle_name,
						"overall_result": "Passed",
						"status": "Submitted",
						"submitted_on": now_datetime(),
						"auto_fill_checklist": 0,
						"overall_notes": marker,
						"items": [
							{
								"item_en": row.name,
								"section": row.category,
								"category": row.category,
								"item": row.item,
								"sort_order": row.sort_order,
								"status": "Sound | سليم",
							}
							for row in checklist
						],
					}
				)
				inspection_doc.insert(ignore_permissions=True)
				inspection = inspection_doc.name
				created.append(f"Vehicle Inspection Log:{inspection}")
			else:
				frappe.db.set_value(
					"Vehicle Inspection Log",
					inspection,
					{
						"captain_user": captains[company],
						"trip": trips[index],
						"route": routes[index],
						"vehicle": driver_vehicles[company],
					},
					update_modified=False,
				)
			inspections.append(inspection)
	frappe.db.commit()
	return _success(
		companies=companies,
		users=users,
		vehicles=vehicles,
		routes=routes,
		trips=trips,
		inspections=inspections,
		catalog={"category": category, "type": vehicle_type, "make": make, "model": model},
		created=created,
		credential_setup_note=(
			"The supplied password was applied to all TEST users; no password is returned."
			if password
			else "Random passwords were generated but not returned or logged. Use the standard reset-password workflow before login."
		),
	)
