from __future__ import annotations

import math

import frappe
from frappe import _


def _haversine_km(lat1, lon1, lat2, lon2):
	"""Haversine distance in kilometres."""
	R = 6371
	dLat = math.radians(float(lat2) - float(lat1))
	dLon = math.radians(float(lon2) - float(lon1))
	a = (math.sin(dLat / 2) ** 2 +
		 math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) *
		 math.sin(dLon / 2) ** 2)
	return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def _destination_distance_km(booking, dest_lat, dest_lon):
	"""Shortest distance from booking drop-off to a driver's target point."""
	return _haversine_km(
		booking.get("dropoff_latitude"),
		booking.get("dropoff_longitude"),
		dest_lat,
		dest_lon,
	)


def _pickup_distance_km(booking, driver_lat, driver_lon):
	return _haversine_km(
		booking.get("pickup_latitude"),
		booking.get("pickup_longitude"),
		driver_lat,
		driver_lon,
	)


def get_driver_schedule_count(captain_user):
	"""Number of accepted scheduled (future) rides for this driver."""
	return frappe.db.count("Trip Booking", {
		"selected_captain": captain_user,
		"booking_status": ("in", ["Confirmed", "Checked In", "Boarded"]),
		"booking_date": (">=", frappe.utils.today()),
	})


def get_driver_active_ride(captain_user):
	"""Return the active (non-cancelled, non-closed) trip booking for this driver."""
	return frappe.db.get_value("Trip Booking", {
		"selected_captain": captain_user,
		"booking_status": ("in", ["Confirmed", "Checked In", "Boarded"]),
		"booking_date": frappe.utils.today(),
	}, "name")


def match_bookings_for_driver(
	captain_user,
	latitude=None,
	longitude=None,
	max_radius_km=None,
	vehicle_type=None,
	limit=50,
):
	"""
	Rank open Trip Bookings for a driver by:
	  1. Pickup proximity (within configurable radius)
	  2. Fare amount descending
	  3. Booking date ascending

	Excludes bookings with assigned captains, cancelled/closed statuses,
	or where the driver is blocked/restricted.
	"""
	max_radius = float(max_radius_km or _default_radius_km())

	filters = {
		"negotiation_status": "Awaiting Offers",
		"booking_status": ("not in", ["Cancelled", "Closed"]),
		"selected_captain": ("is", "not set"),
		"main_rider_user": ("!=", captain_user),
	}

	if vehicle_type:
		filters["vehicle_type"] = vehicle_type

	bookings = frappe.get_all(
		"Trip Booking",
		filters=filters,
		fields=[
			"name", "booking_title", "pickup_point", "drop_point", "route",
			"pickup_latitude", "pickup_longitude", "dropoff_latitude", "dropoff_longitude",
			"vehicle_type", "seat_count", "quoted_fare", "fare_amount", "booking_date",
			"booking_group_code", "passenger_count", "negotiation_status",
		],
		order_by="booking_date asc, quoted_fare desc",
		limit_page_length=limit * 3,
	)

	scored = []
	for b in bookings:
		if b.pickup_latitude is None or b.pickup_longitude is None:
			continue
		dist = _pickup_distance_km(b, latitude or 0, longitude or 0) if latitude is not None else 0
		if dist > max_radius:
			continue
		fare = float(b.quoted_fare or b.fare_amount or 0)
		scored.append((dist, fare, b))

	scored.sort(key=lambda x: (x[0], -x[1]))
	return [item[2] for item in scored[:limit]]


def match_offers_for_booking(booking_name, limit=50):
	"""Return accepted offers for a booking, ordered by lowest fare."""
	offers = frappe.get_all(
		"Booking Offer",
		filters={
			"booking": booking_name,
			"status": "Pending",
		},
		fields=[
			"name", "vehicle", "captain_user", "offered_fare", "fare_type",
			"captain_notes", "created_at",
		],
		order_by="offered_fare asc, created_at asc",
		limit_page_length=limit,
	)
	return offers


def _default_radius_km():
	configured = frappe.db.get_single_value("Platform Settings", "driver_match_radius_km")
	try:
		return max(1, min(float(configured or 5), 200))
	except (TypeError, ValueError):
		return 5


def check_schedule_availability(captain_user, booking_name):
	"""
	Return (can_accept, reason) for whether a driver can accept this booking
	based on schedule limits and overlap checks.
	"""
	MAX_SCHEDULED = 3

	active = get_driver_active_ride(captain_user)
	if active:
		return False, _("You have an active ride that must be completed first")

	count = get_driver_schedule_count(captain_user)
	if count >= MAX_SCHEDULED:
		return False, _("You cannot have more than {0} scheduled rides").format(MAX_SCHEDULED)

	booking = frappe.get_doc("Trip Booking", booking_name)
	if not booking.booking_date:
		return True, None

	booking_date = str(booking.booking_date)
	existing = frappe.get_all(
		"Trip Booking",
		filters={
			"selected_captain": captain_user,
			"booking_date": booking_date,
			"booking_status": ("in", ["Confirmed", "Checked In", "Boarded"]),
		},
		fields=["name", "booking_title"],
	)
	if existing:
		return False, _("You already have a booking on {0}").format(booking_date)

	return True, None


@frappe.whitelist()
def driver_matched_bookings(vehicle_type=None, latitude=None, longitude=None, limit=50):
	"""API: return ranked open bookings for the currently logged-in driver."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	captain = frappe.db.get_value("Captain Profile", {"user": user, "status": "Active"}, "name")
	if not captain:
		frappe.throw(_("Only active captains can browse ride orders"), frappe.PermissionError)

	results = match_bookings_for_driver(
		captain_user=user,
		latitude=float(latitude) if latitude is not None else None,
		longitude=float(longitude) if longitude is not None else None,
		vehicle_type=vehicle_type,
		limit=int(limit or 50),
	)
	return [{f: b.get(f) for f in b if b.get(f) is not None} for b in results]


@frappe.whitelist()
def booking_matched_offers(booking_name, limit=50):
	"""API: return pending offers for a booking, ranked by lowest fare first."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	offers = match_offers_for_booking(booking_name, limit=int(limit or 50))
	return [{
		"name": o.name, "vehicle": o.vehicle, "captain_user": o.captain_user,
		"offered_fare": o.offered_fare, "fare_type": o.fare_type,
		"captain_notes": o.captain_notes, "created_at": str(o.created_at),
	} for o in offers]
