from __future__ import annotations

from frappe.model.naming import make_autoname


def route_title(source=None, destination=None):
	if source and destination:
		return f"{source} to {destination}"
	return source or destination or ""


def trip_title(route=None, driver=None):
	parts = [route, driver]
	return " - ".join(part for part in parts if part)


def booking_title(customer_name=None, route=None, trip=None):
	parts = [customer_name, route or trip or "Booking"]
	return " - ".join(part for part in parts if part)


def make_code(prefix):
	return make_autoname(f"{prefix}-.#####")
