import frappe

from ftms.tenant import company_filters, get_user_company, has_company_access, resolve_company
from ftms.config.service import get_public_frontend_url


@frappe.whitelist()
def list_trips(company=None, limit=50):
	filters = company_filters(company=company)
	return frappe.get_all(
		"Trip",
		filters=filters,
		fields=["name", "company", "trip_title", "trip_code", "trip_date", "trip_status", "route", "vehicle", "assigned_captain_user", "seat_capacity", "available_seats"],
		order_by="trip_date desc, modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_trip(name, company=None):
	doc = frappe.get_doc("Trip", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and doc.company != resolved_company:
		frappe.throw("Not permitted for this company", frappe.PermissionError)
	if not resolved_company and frappe.session.user != "Administrator":
		frappe.throw("Company access is required", frappe.PermissionError)
	return doc.as_dict()


@frappe.whitelist()
def create_trip(route, trip_date, vehicle=None, trip_title=None, trip_code=None, company=None, status="Scheduled"):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw("Login is required", frappe.PermissionError)

	resolved_company = resolve_company(company=company)
	if not resolved_company:
		frappe.throw("Company is required")
	if status not in ("Draft", "Scheduled"):
		frappe.throw("New trips must start as Draft or Scheduled")
	if not frappe.db.exists("Route", {"name": route, "company": resolved_company}):
		frappe.throw("Route does not belong to the selected company", frappe.PermissionError)
	if vehicle:
		vehicle_company = frappe.db.get_value("Vehicle", vehicle, "company")
		if vehicle_company != resolved_company:
			frappe.throw("Vehicle does not belong to the selected company", frappe.PermissionError)

	doc = frappe.get_doc({
		"doctype": "Trip",
		"company": resolved_company,
		"trip_title": trip_title or f"Trip-{trip_date}",
		"trip_code": trip_code,
		"trip_date": trip_date,
		"route": route,
		"vehicle": vehicle,
		"trip_status": status,
	})
	doc.insert(ignore_permissions=True)
	return {"name": doc.name, "company": doc.company, "trip_status": doc.trip_status}


@frappe.whitelist()
def update_trip_status(name, status):
	doc = frappe.get_doc("Trip", name)
	if frappe.session.user != "Administrator" and not has_company_access(doc.company):
		frappe.throw("Not permitted for this trip", frappe.PermissionError)
	from ftms.ride_machine.state_machine import TripStateMachine
	machine = TripStateMachine(doc)
	action = next((name for name, target in machine.actions.items() if target == status), None)
	if not action:
		frappe.throw("Invalid trip transition")
	machine.action(action)
	doc.save(ignore_permissions=False)
	return {"name": doc.name, "trip_status": doc.trip_status}


@frappe.whitelist()
def generate_qr(trip_name):
	"""Generate QR code for public trip page."""
	trip = frappe.get_doc("Trip", trip_name)
	if not trip.public_uuid:
		import uuid
		trip.db_set("public_uuid", str(uuid.uuid4()))
		trip.reload()

	import pyqrcode
	public_url = f"{get_public_frontend_url()}/trip/{trip.public_uuid.lstrip('/')}"
	qr = pyqrcode.create(public_url)
	data_uri = "data:image/png;base64," + qr.png_as_base64_str(scale=6)
	trip.db_set("qr_code", data_uri)

	return {"qr_code": data_uri, "public_url": public_url, "uuid": trip.public_uuid}


@frappe.whitelist()
def get_public_url(trip_name):
	"""Get the public trip page URL for a trip."""
	uuid = frappe.db.get_value("Trip", trip_name, "public_uuid")
	if not uuid:
		import uuid as _uuid
		uuid = str(_uuid.uuid4())
		frappe.db.set_value("Trip", trip_name, "public_uuid", uuid)
	return {"url": f"{get_public_frontend_url()}/trip/{uuid.lstrip('/')}"}


@frappe.whitelist(allow_guest=True)
def get_public_trip(uuid):
	"""Get trip details by public UUID (no auth required)."""
	if not uuid:
		frappe.throw("Trip UUID is required")

	trip = frappe.db.get_value("Trip", {"public_uuid": uuid}, [
		"name", "trip_title", "trip_code", "trip_date", "trip_status",
		"route", "from_location", "to_location",
		"distance_km", "duration_minutes",
		"departure_datetime", "planned_arrival_datetime",
		"vehicle", "driver", "assigned_captain_user",
		"trip_value", "billing_mode", "vat_mode", "vat_rate",
		"passenger_count", "seat_capacity", "available_seats",
		"group_leader_name", "group_leader_mobile",
		"hijri_date", "qr_code", "public_uuid",
		"company", "notes",
	], as_dict=True)

	if not trip:
		frappe.throw("Trip not found")

	passengers = frappe.db.get_all("Trip Passenger", filters={"parent": trip.name},
		fields=["passenger_name", "nationality", "document_number", "document_type", "luggage_qty", "seat_number"],
		order_by="idx asc")

	driver_name = ""
	if trip.driver:
		driver_name = frappe.db.get_value("Employee", trip.driver, "employee_name") or trip.assigned_captain_user or ""
	captain_name = ""
	if trip.assigned_captain_user:
		cap = frappe.db.get_value("Captain Profile", {"user": trip.assigned_captain_user}, "full_name")
		if cap:
			captain_name = cap

	vehicle_name = ""
	vehicle_plate = ""
	if trip.vehicle:
		v = frappe.db.get_value("Vehicle", trip.vehicle, ["vehicle_name", "plate_no"], as_dict=True)
		if v:
			vehicle_name = v.vehicle_name or ""
			vehicle_plate = v.plate_no or ""

	company_name = ""
	company_name_ar = ""
	company_logo = ""
	company_phone = ""
	if trip.company:
		c = frappe.db.get_value("Company", trip.company, ["company_name", "company_name_ar", "logo", "phone"], as_dict=True)
		if c:
			company_name = c.company_name or ""
			company_name_ar = c.company_name_ar or ""
			company_logo = c.logo or ""
			company_phone = c.phone or ""

	return {
		"trip": {
			"name": trip.name,
			"title": trip.trip_title or trip.name,
			"code": trip.trip_code or "",
			"date": str(trip.trip_date or ""),
			"hijri_date": trip.hijri_date or "",
			"status": trip.trip_status or "Scheduled",
			"from_location": trip.from_location or "",
			"to_location": trip.to_location or "",
			"distance_km": trip.distance_km or 0,
			"duration_minutes": trip.duration_minutes or 0,
			"departure": str(trip.departure_datetime or "")[:19],
			"arrival": str(trip.planned_arrival_datetime or "")[:19],
			"value": float(trip.trip_value or 0),
			"billing_mode": trip.billing_mode or "",
			"vat_mode": trip.vat_mode or "",
			"vat_rate": float(trip.vat_rate or 0),
			"passenger_count": trip.passenger_count or len(passengers),
			"seat_capacity": trip.seat_capacity or 0,
			"available_seats": trip.available_seats or 0,
			"group_leader": trip.group_leader_name or "",
			"group_leader_mobile": trip.group_leader_mobile or "",
			"qr_code": trip.qr_code or "",
			"notes": trip.notes or "",
		},
		"passengers": passengers,
		"driver": {"name": driver_name, "captain": captain_name},
		"vehicle": {"name": vehicle_name, "plate": vehicle_plate},
		"company": {
			"name": company_name,
			"name_ar": company_name_ar,
			"logo": company_logo,
			"phone": company_phone,
		},
	}
