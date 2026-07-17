from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import today

from ftms.tenant import company_filters, resolve_company


def _coerce_passengers(value):
	if not value:
		return []
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except Exception:
			return []
	if not isinstance(value, list):
		return []
	return [row for row in value if isinstance(row, dict)]


@frappe.whitelist(allow_guest=True)
def create_booking(**kwargs):
	required_key = frappe.get_site_config().get("transport_hub_api_key")
	sent_key = frappe.get_request_header("X-TransportHub-Key") or frappe.form_dict.get("api_key")

	if required_key and sent_key != required_key:
		frappe.throw(_("Unauthorized"), frappe.PermissionError)

	data = frappe._dict(kwargs)
	trip = data.get("trip")
	route = data.get("route")
	if trip and not route:
		route = frappe.db.get_value("FTMS Trip", trip, "route")
	company = data.get("company")
	if trip and not company:
		company = frappe.db.get_value("FTMS Trip", trip, "company")

	passengers = _coerce_passengers(data.get("passengers"))
	seat_count = data.get("seat_count") or data.get("passenger_count") or len(passengers) or 1
	booking_title = data.get("booking_title") or " - ".join(
		value for value in [data.get("customer_name"), route or trip or "Booking"] if value
	)

	doc = frappe.get_doc(
		{
			"doctype": "FTMS Trip Booking",
			"company": company,
			"booking_title": booking_title,
			"booking_date": data.get("booking_date") or today(),
			"trip": trip,
			"route": route,
			"customer_name": data.get("customer_name"),
			"mobile_no": data.get("mobile_no"),
			"source_channel": data.get("source_channel") or "API",
			"fare_amount": data.get("fare_amount"),
			"payment_status": data.get("payment_status") or "Unpaid",
			"seat_count": seat_count,
			"passenger_count": len(passengers) or data.get("passenger_count") or 0,
			"booking_status": data.get("booking_status") or "Draft",
			"pickup_point": data.get("pickup_point"),
			"drop_point": data.get("drop_point"),
			"notes": data.get("notes"),
			"passengers": passengers,
		}
	)

	doc.insert(ignore_permissions=True)
	return {
		"name": doc.name,
		"booking_title": doc.booking_title,
		"route": doc.route,
		"trip": doc.trip,
		"passenger_count": doc.passenger_count,
	}


@frappe.whitelist()
def list_bookings(company=None, limit=50):
	filters = company_filters(company=company)
	return frappe.get_all(
		"FTMS Trip Booking",
		filters=filters,
		fields=["name", "company", "booking_title", "booking_date", "customer_name", "mobile_no", "trip", "route", "booking_status"],
		order_by="booking_date desc, modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_booking(name, company=None):
	doc = frappe.get_doc("FTMS Trip Booking", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and getattr(doc, "company", None) != resolved_company:
		frappe.throw("Not permitted for this company")
	return doc.as_dict()
