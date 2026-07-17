from __future__ import annotations

import frappe


def _ensure_doc(doctype, name, values):
	existing = frappe.db.exists(doctype, name)
	if existing:
		return existing
	doc = frappe.get_doc({"doctype": doctype, **values})
	doc.insert(ignore_permissions=True)
	return doc.name


def seed_demo_transport_cycle(company, route=None):
	"""Create a tiny end-to-end demo cycle for one tenant.

	This is intentionally small: one company, one route, one vehicle, one trip,
	one booking, and one invoice snapshot.
	"""
	if not company:
		frappe.throw("company is required")

	company_doc = frappe.get_doc("Transportation Company", company)

	if not route:
		route = frappe.db.exists("FTMS Route", {"company": company, "route_title": "Demo Route"})
		if not route:
			route_doc = frappe.get_doc(
				{
					"doctype": "FTMS Route",
					"company": company,
					"route_title": "Demo Route",
					"source": "Demo Origin",
					"destination": "Demo Destination",
					"status": "Active",
				}
			)
			route_doc.insert(ignore_permissions=True)
			route = route_doc.name

	vehicle_category = frappe.db.exists("FTMS Vehicle Category", "Passenger") or _ensure_doc(
		"FTMS Vehicle Category", "Passenger", {"category_name": "Passenger", "status": "Active"}
	)
	vehicle_type = frappe.db.exists("FTMS Vehicle Type", "Bus") or _ensure_doc(
		"FTMS Vehicle Type", "Bus", {"type_name": "Bus", "vehicle_category": vehicle_category, "default_seating_capacity": 30, "status": "Active"}
	)
	vehicle_make = frappe.db.exists("FTMS Vehicle Make", "Toyota") or _ensure_doc(
		"FTMS Vehicle Make", "Toyota", {"make_name": "Toyota", "country_of_origin": "Japan", "status": "Active"}
	)
	vehicle_model = frappe.db.exists("FTMS Vehicle Model", "Coaster") or _ensure_doc(
		"FTMS Vehicle Model",
		"Coaster",
		{"model_name": "Coaster", "vehicle_make": vehicle_make, "vehicle_type": vehicle_type, "vehicle_category": vehicle_category, "seat_capacity": 30, "status": "Active"},
	)

	vehicle = frappe.db.exists("FTMS Vehicle", {"company": company, "vehicle_name": "Demo Bus"})
	if not vehicle:
		vehicle_doc = frappe.get_doc(
			{
				"doctype": "FTMS Vehicle",
				"company": company,
				"vehicle_name": "Demo Bus",
				"vehicle_make": vehicle_make,
				"vehicle_model": vehicle_model,
				"vehicle_type": vehicle_type,
				"vehicle_category": vehicle_category,
				"plate_no": "DEMO-1234",
				"status": "Active",
			}
		)
		vehicle_doc.insert(ignore_permissions=True)
		vehicle = vehicle_doc.name

	customer = frappe.db.exists("Customer", {"company": company, "customer_name": company_doc.company_name})
	if not customer:
		customer_doc = frappe.get_doc(
			{
				"doctype": "Customer",
				"company": company,
				"customer_name": company_doc.company_name,
				"mobile_no": "0500000000",
				"email": f"demo@{company_doc.company_name.lower().replace(' ', '')}.com",
				"status": "Active",
			}
		)
		customer_doc.insert(ignore_permissions=True)
		customer = customer_doc.name

	trip = frappe.get_doc(
		{
			"doctype": "FTMS Trip",
			"company": company,
			"route": route,
			"vehicle": vehicle,
			"trip_title": f"{company_doc.company_name} Demo Trip",
			"trip_value": 100,
			"vat_rate": 15,
			"trip_status": "Scheduled",
			"passengers": [
				{"passenger_name": "Demo Passenger 1", "mobile_no": "0500000001", "source": "Manual"},
				{"passenger_name": "Demo Passenger 2", "mobile_no": "0500000002", "source": "Manual"},
			],
		}
	)
	trip.insert(ignore_permissions=True)

	booking = frappe.get_doc(
		{
			"doctype": "FTMS Trip Booking",
			"company": company,
			"trip": trip.name,
			"booking_title": f"{company_doc.company_name} Demo Booking",
			"customer_name": company_doc.company_name,
			"mobile_no": "0500000000",
			"source_channel": "Website",
			"booking_status": "Confirmed",
			"seat_count": 2,
			"passengers": trip.passengers,
		}
	)
	booking.insert(ignore_permissions=True)

	invoice = frappe.get_doc(
		{
			"doctype": "FTMS Trip Invoice",
			"company": company,
			"trip": trip.name,
			"customer": customer,
			"trip_value": 100,
			"vat_rate": 15,
			"status": "Draft",
		}
	)
	invoice.insert(ignore_permissions=True)

	return {
		"company": company,
		"route": route,
		"vehicle": vehicle,
		"trip": trip.name,
		"booking": booking.name,
		"invoice": invoice.name,
	}
