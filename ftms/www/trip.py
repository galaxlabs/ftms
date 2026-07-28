import frappe


def get_context(context):
	uuid = frappe.form_dict.get("uuid") or ""
	if not uuid:
		path = frappe.local.request.path.rstrip("/")
		if "/trip/" in path:
			uuid = path.split("/trip/")[-1]

	context.uuid = uuid
	context.trip = None
	context.passengers = []
	context.company = {}
	context.error = ""

	if not uuid:
		context.error = "No trip ID provided"
		return

	try:
		trip_data = frappe.db.get_value(
			"Trip", {"public_uuid": uuid},
			["name", "trip_title", "trip_status", "trip_code",
			 "from_location", "to_location",
			 "distance_km", "duration_minutes",
			 "trip_value", "passenger_count",
			 "group_leader_name", "group_leader_mobile",
			 "hijri_date", "trip_date", "company",
			 "qr_code", "public_uuid",
			 "driver", "co_driver", "vehicle",
			 "departure_datetime", "planned_arrival_datetime",
			 "seat_capacity", "available_seats",
			 "billing_mode", "vat_mode", "vat_rate",
			 "trip_booking"],
			as_dict=True
		)
	except Exception:
		context.error = "Trip not found"
		return

	if not trip_data:
		context.error = "Trip not found"
		return

	try:
		passengers = frappe.db.get_all(
			"Trip Passenger",
			filters={"parent": trip_data.name},
			fields=["passenger_name", "nationality", "document_number", "document_type", "luggage_qty"],
			order_by="idx asc"
		)
	except Exception:
		passengers = []

	driver_name = ""
	co_driver_name = ""
	if trip_data.driver:
		try:
			driver_name = frappe.db.get_value("Employee", trip_data.driver, "employee_name") or ""
		except Exception:
			pass
	if trip_data.co_driver:
		try:
			co_driver_name = frappe.db.get_value("Employee", trip_data.co_driver, "employee_name") or ""
		except Exception:
			pass

	vehicle_name = ""
	vehicle_plate = ""
	if trip_data.vehicle:
		try:
			v_data = frappe.db.get_value("Vehicle", trip_data.vehicle, ["make", "model", "license_plate"], as_dict=True)
			if v_data:
				vehicle_name = f"{v_data.make or ''} {v_data.model or ''}".strip()
				vehicle_plate = v_data.license_plate or ""
		except Exception:
			pass

	company_name = ""
	company_name_ar = ""
	company_logo = ""
	phone_no = ""
	company_reg_no = ""
	if trip_data.company:
		try:
			company_name = frappe.db.get_value("Company", trip_data.company, "company_name") or ""
		except Exception:
			pass
		try:
			company_name_ar = frappe.db.get_value("Company", trip_data.company, "company_name_ar") or ""
		except Exception:
			pass
		if not company_name_ar:
			try:
				company_name_ar = frappe.db.get_value("Company", trip_data.company, "custom_company_name_arabic") or ""
			except Exception:
				pass
		try:
			company_logo = frappe.db.get_value("Company", trip_data.company, "company_logo") or ""
		except Exception:
			pass
		try:
			phone_no = frappe.db.get_value("Company", trip_data.company, "phone_no") or ""
		except Exception:
			pass
		try:
			company_reg_no = frappe.db.get_value("Company", trip_data.company, "company_registration") or ""
		except Exception:
			pass
		if not company_reg_no:
			try:
				company_reg_no = frappe.db.get_value("Company", trip_data.company, "tax_id") or ""
			except Exception:
				pass

	hijri_display = trip_data.hijri_date or ""
	if hijri_display and len(hijri_display) >= 10:
		try:
			parts = hijri_display.split("-")
			hijri_display = f"{parts[2]}-{parts[1]}-{parts[0]}"
		except Exception:
			pass

	gregorian_display = ""
	if trip_data.trip_date:
		gregorian_display = frappe.utils.formatdate(trip_data.trip_date, "dd-MM-yyyy")

	departure_display = ""
	if trip_data.departure_datetime:
		departure_display = str(trip_data.departure_datetime)[:19]
	arrival_display = ""
	if trip_data.planned_arrival_datetime:
		arrival_display = str(trip_data.planned_arrival_datetime)[:19]

	context.trip = {
		"name": trip_data.name,
		"title": trip_data.trip_title or trip_data.name,
		"trip_code": trip_data.trip_code or "",
		"status": trip_data.trip_status or "Scheduled",
		"from_location": trip_data.from_location or "-",
		"to_location": trip_data.to_location or "-",
		"from_ar": trip_data.from_location or "-",
		"to_ar": trip_data.to_location or "-",
		"distance_km": trip_data.distance_km or 0,
		"duration_minutes": trip_data.duration_minutes or 0,
		"passenger_count": trip_data.passenger_count or (len(passengers) if passengers else 0),
		"seat_capacity": trip_data.seat_capacity or 0,
		"available_seats": trip_data.available_seats or 0,
		"value": frappe.utils.fmt_money(trip_data.trip_value, currency="SAR") if trip_data.trip_value else "-",
		"hijri": hijri_display,
		"gregorian": gregorian_display,
		"departure": departure_display,
		"arrival": arrival_display,
		"qr_code": trip_data.qr_code or "",
		"public_uuid": trip_data.public_uuid or "",
		"driver_name": driver_name or "-",
		"co_driver": co_driver_name or "-",
		"vehicle_name": vehicle_name or "-",
		"vehicle_plate": vehicle_plate or "-",
		"group_leader": trip_data.group_leader_name or "",
		"group_leader_mobile": trip_data.group_leader_mobile or "",
	}
	context.passengers = passengers
	context.org = {
		"name": company_name,
		"name_ar": company_name_ar,
		"logo": company_logo,
		"phone": phone_no,
		"reg_no": company_reg_no,
	}
