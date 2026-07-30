from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime

from ftms.tenant import has_company_access


RATING_TYPES = {
	"Passenger to Driver": ("main_rider_user", "assigned_captain_user"),
	"Driver to Passenger": ("assigned_captain_user", "main_rider_user"),
}


def _trip_context(trip_name):
	trip = frappe.get_doc("Trip", trip_name)
	if trip.trip_status != "Completed":
		frappe.throw(_("Ratings are available only after trip completion"))
	window_days = int(frappe.db.get_single_value("Platform Settings", "rating_window_days") or 7)
	completed_at = trip.actual_arrival_datetime or get_datetime(trip.trip_date)
	if completed_at and now_datetime() > add_to_date(completed_at, days=window_days):
		frappe.throw(_("The rating window for this trip has expired"))
	booking = frappe.get_doc("Trip Booking", trip.trip_booking) if trip.trip_booking else None
	passenger_user = booking.main_rider_user if booking else None
	return trip, booking, passenger_user, trip.assigned_captain_user


def _require_trip_rating_access(trip, passenger_user, driver_user):
	user = frappe.session.user
	if user in (passenger_user, driver_user):
		return
	if trip.company and has_company_access(trip.company, user=user):
		return
	frappe.throw(_("You are not permitted to access ratings for this trip"), frappe.PermissionError)


def _publish_pair(trip_name):
	ratings = frappe.get_all(
		"Trip Rating",
		filters={"trip": trip_name, "status": "Pending"},
		fields=["name", "rating_type"],
	)
	types = {row.rating_type for row in ratings}
	if {"Passenger to Driver", "Driver to Passenger"}.issubset(types):
		for row in ratings:
			frappe.db.set_value("Trip Rating", row.name, "status", "Published")


@frappe.whitelist()
def submit_rating(trip, rating, rating_type, comment=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	if rating_type not in RATING_TYPES:
		frappe.throw(_("Invalid rating type"))
	trip_doc, booking, passenger_user, driver_user = _trip_context(trip)
	rater_field, rated_field = RATING_TYPES[rating_type]
	if not booking or not getattr(booking, "main_rider_user", None) or not driver_user:
		frappe.throw(_("This trip does not have the required rating participants"))
	if frappe.session.user != getattr(booking, rater_field, None) and frappe.session.user != getattr(trip_doc, rater_field, None):
		frappe.throw(_("You are not the authorized rater for this rating type"), frappe.PermissionError)
	rater = frappe.session.user
	rated = getattr(booking, rated_field, None) if hasattr(booking, rated_field) else getattr(trip_doc, rated_field, None)
	if not rated:
		frappe.throw(_("The rated participant is not available"))
	if frappe.db.exists("Trip Rating", {"trip": trip, "rater_user": rater, "rating_type": rating_type}):
		frappe.throw(_("You have already rated this trip"))
	doc = frappe.get_doc({
		"doctype": "Trip Rating",
		"trip": trip,
		"booking": booking.name,
		"rating_key": f"{trip}:{rater}:{rating_type}",
		"rater_user": rater,
		"rated_user": rated,
		"rating_type": rating_type,
		"rating": int(rating),
		"comment": comment,
		"status": "Pending",
		"submitted_at": now_datetime(),
	})
	doc.insert(ignore_permissions=True)
	_publish_pair(trip)
	doc.reload()
	return {"name": doc.name, "status": doc.status, "rating": doc.rating}


@frappe.whitelist()
def list_trip_ratings(trip):
	trip_doc, _, passenger_user, driver_user = _trip_context(trip)
	_require_trip_rating_access(trip_doc, passenger_user, driver_user)
	return frappe.get_all(
		"Trip Rating",
		filters={"trip": trip, "status": "Published"},
		fields=["name", "rated_user", "rating_type", "rating", "comment", "submitted_at"],
		order_by="submitted_at desc",
	)


@frappe.whitelist()
def get_rating_summary(user, rating_type=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	filters = {"rated_user": user, "status": "Published"}
	if rating_type:
		if rating_type not in RATING_TYPES:
			frappe.throw(_("Invalid rating type"))
		filters["rating_type"] = rating_type
	rows = frappe.get_all("Trip Rating", filters=filters, fields=["rating"], limit_page_length=0)
	count = len(rows)
	average = sum(float(row.rating or 0) for row in rows) / count if count else 0
	return {"user": user, "rating_type": rating_type, "count": count, "average": round(average, 2)}
