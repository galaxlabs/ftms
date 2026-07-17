from __future__ import annotations

from frappe.utils import flt


def update_trip_counts(doc):
	passenger_count = len(doc.passengers or [])
	doc.passenger_count = passenger_count
	if getattr(doc, "seat_capacity", None):
		doc.available_seats = flt(doc.seat_capacity) - passenger_count
	return passenger_count


def update_trip_title_code(doc):
	if not getattr(doc, "trip_title", None):
		parts = [getattr(doc, "route", None), getattr(doc, "driver", None)]
		doc.trip_title = " - ".join(part for part in parts if part) or getattr(doc, "trip_title", None)
	if not getattr(doc, "trip_code", None) and getattr(doc, "trip_title", None):
		doc.trip_code = doc.trip_title
	return doc.trip_title, doc.trip_code


def update_trip_pricing(doc):
	trip_value = flt(getattr(doc, "trip_value", 0))
	passenger_count = flt(getattr(doc, "passenger_count", 0)) or len(getattr(doc, "passengers", []) or [])
	vat_rate = flt(getattr(doc, "vat_rate", 0))
	driver_commission_rate = flt(getattr(doc, "driver_commission_rate", 0))

	per_passenger_value = flt(getattr(doc, "per_passenger_value", 0))
	if trip_value and passenger_count and not per_passenger_value:
		per_passenger_value = trip_value / passenger_count
		doc.per_passenger_value = per_passenger_value

	driver_commission_amount = flt(trip_value * driver_commission_rate / 100)
	doc.driver_commission_amount = driver_commission_amount
	doc.company_share = flt(trip_value - driver_commission_amount)
	if getattr(doc, "vat_mode", "Included") == "Excluded":
		doc.vat_amount = flt(trip_value * vat_rate / 100)
		doc.net_total = trip_value
		doc.grand_total = flt(trip_value + doc.vat_amount)
	return doc
