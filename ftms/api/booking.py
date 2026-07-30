from __future__ import annotations

import json
import uuid

import frappe
from frappe import _
from frappe.utils import now_datetime, today

from ftms.tenant import company_filters, get_user_company, has_company_access, resolve_company


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


def _lookup_pricing_rule(vehicle_type, company):
	rules = frappe.get_all(
		"Pricing Rule",
		filters={"vehicle_type": vehicle_type, "company": company, "is_active": 1},
		limit=1,
	)
	return rules[0].name if rules else None


def _require_booking_access(booking, user, *, owner_allowed=True):
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	if owner_allowed and booking.main_rider_user and booking.main_rider_user == user:
		return
	if booking.company and has_company_access(booking.company, user=user):
		return
	frappe.throw(_("You are not permitted to access this booking"), frappe.PermissionError)


def _generate_group_code():
	return uuid.uuid4().hex[:8].upper()


def _create_trip_from_booking(booking, offer):
	"""Convert accepted booking+offer into a Trip."""
	trip_title = f"{booking.customer_name or 'Rider'} - {booking.route or 'Trip'}"
	doc = frappe.get_doc({
		"doctype": "Trip",
		"company": booking.company,
		"trip_title": trip_title,
		"trip_date": booking.booking_date or today(),
		"route": booking.route,
		"vehicle": offer.vehicle,
		"assigned_captain_user": offer.captain_user,
		"trip_status": "Scheduled",
		"trip_value": offer.offered_fare,
		"pickup_point": booking.pickup_point,
		"drop_point": booking.drop_point,
		"group_leader_name": booking.group_leader_name or booking.customer_name,
		"group_leader_mobile": booking.group_leader_mobile or booking.mobile_no,
		"passengers": [{
			"passenger_name": p.get("passenger_name"),
			"nationality": p.get("nationality"),
			"document_type": p.get("document_type"),
			"document_number": p.get("document_number"),
			"mobile_no": p.get("mobile_no"),
			"luggage_qty": p.get("luggage_qty") or 0,
			"seat_no": p.get("seat_no"),
			"booking_group": booking.booking_group_code,
			"is_primary_booker": 1 if i == 0 else 0,
		} for i, p in enumerate(booking.passengers or [])],
	})
	doc.flags.ignore_validate = True
	doc.insert(ignore_permissions=True)

	booking.db_set("trip", doc.name)
	booking.db_set("negotiation_status", "Trip Created")
	booking.db_set("booking_status", "Confirmed")

	offer.db_set("status", "Accepted")
	offer.db_set("responded_at", now_datetime())

	# Reject all other pending offers
	others = frappe.get_all("Booking Offer",
		filters={"booking": booking.name, "name": ("!=", offer.name), "status": "Pending"},
	)
	for o in others:
		frappe.db.set_value("Booking Offer", o.name, "status", "Rejected")
		frappe.db.set_value("Booking Offer", o.name, "responded_at", now_datetime())

	return doc


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
		route = frappe.db.get_value("Trip", trip, "route")
	company = data.get("company") or (frappe.db.get_value("Trip", trip, "company") if trip else None)
	if not company and frappe.session.user != "Guest":
		from ftms.tenant import get_user_company
		company = get_user_company()

	passengers = _coerce_passengers(data.get("passengers"))
	seat_count = data.get("seat_count") or data.get("passenger_count") or len(passengers) or 1
	booking_title = data.get("booking_title") or " - ".join(
		value for value in [data.get("customer_name"), route or trip or "Booking"] if value
	)

	vehicle_type = data.get("vehicle_type")
	pricing_rule = data.get("pricing_rule")
	if vehicle_type and not pricing_rule and company:
		pricing_rule = _lookup_pricing_rule(vehicle_type, company)

	group_code = _generate_group_code()

	doc = frappe.get_doc({
		"doctype": "Trip Booking",
		"company": company,
		"booking_title": booking_title,
		"booking_group_code": group_code,
		"booking_date": data.get("booking_date") or today(),
		"trip": trip,
		"route": route,
		"customer_name": data.get("customer_name"),
		"mobile_no": data.get("mobile_no"),
		"source_channel": data.get("source_channel") or ("Website" if data.get("main_rider_user") else "API"),
		"main_rider_user": data.get("main_rider_user"),
		"group_leader_name": data.get("group_leader_name"),
		"group_leader_mobile": data.get("group_leader_mobile"),
		"is_group_leader_self": data.get("is_group_leader_self") or 0,
		"fare_amount": data.get("fare_amount"),
		"payment_status": data.get("payment_status") or "Unpaid",
		"seat_count": seat_count,
		"passenger_count": len(passengers) or data.get("passenger_count") or 0,
		"booking_status": data.get("booking_status") or "Draft",
		"negotiation_status": "Awaiting Offers",
		"pickup_point": data.get("pickup_point"),
		"drop_point": data.get("drop_point"),
		"pickup_latitude": data.get("pickup_latitude"),
		"pickup_longitude": data.get("pickup_longitude"),
		"dropoff_latitude": data.get("dropoff_latitude"),
		"dropoff_longitude": data.get("dropoff_longitude"),
		"vehicle_type": vehicle_type,
		"pricing_rule": pricing_rule,
		"offer_deadline": data.get("offer_deadline"),
		"notes": data.get("notes"),
		"passengers": passengers,
	})

	doc.insert(ignore_permissions=True)
	return {
		"name": doc.name,
		"booking_title": doc.booking_title,
		"booking_group_code": doc.booking_group_code,
		"route": doc.route,
		"trip": doc.trip,
		"passenger_count": doc.passenger_count,
		"negotiation_status": doc.negotiation_status,
		"vehicle_type": doc.vehicle_type,
	}


@frappe.whitelist()
def list_bookings(company=None, limit=50):
	filters = company_filters(company=company)
	return frappe.get_all(
		"Trip Booking",
		filters=filters,
		fields=[
			"name", "company", "booking_title", "booking_date",
			"customer_name", "mobile_no", "trip", "route",
			"booking_status", "negotiation_status", "vehicle_type",
			"booking_group_code", "main_rider_user",
			"group_leader_name", "group_leader_mobile", "is_group_leader_self",
		],
		order_by="booking_date desc, modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def list_available_bookings(company=None, vehicle_type=None, limit=50):
	"""Captains call this to see bookings awaiting offers."""
	filters = {"negotiation_status": "Awaiting Offers", "booking_status": ("!=", "Cancelled")}
	if company:
		filters["company"] = company
	if vehicle_type:
		filters["vehicle_type"] = vehicle_type
	return frappe.get_all(
		"Trip Booking",
		filters=filters,
		fields=[
			"name", "company", "booking_title", "booking_date",
			"customer_name", "mobile_no", "route",
			"vehicle_type", "pricing_rule", "passenger_count",
			"pickup_point", "drop_point",
			"pickup_latitude", "pickup_longitude",
			"dropoff_latitude", "dropoff_longitude",
			"offer_deadline", "booking_group_code",
		],
		order_by="booking_date asc, modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_booking(name, company=None):
	doc = frappe.get_doc("Trip Booking", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and getattr(doc, "company", None) != resolved_company:
		frappe.throw("Not permitted for this company", frappe.PermissionError)
	_require_booking_access(doc, frappe.session.user)
	data = doc.as_dict()
	data["offers"] = frappe.get_all(
		"Booking Offer",
		filters={"booking": name},
		fields=["name", "captain_user", "vehicle", "offered_fare", "fare_type", "captain_notes", "status", "created_at"],
		order_by="created_at desc",
	)
	return data


@frappe.whitelist()
def make_offer(booking, vehicle, offered_fare, fare_type="Total Trip", captain_notes=None):
	"""Captain makes an offer on a booking."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)

	booking_doc = frappe.get_doc("Trip Booking", booking)
	profile = frappe.db.get_value("Captain Profile", {"user": user}, ["name", "status"], as_dict=True)
	if not profile or profile.status != "Active":
		frappe.throw(_("Only a registered captain can submit an offer"), frappe.PermissionError)
	if booking_doc.negotiation_status != "Awaiting Offers":
		frappe.throw(_("Booking is not accepting offers"))
	if booking_doc.company and not has_company_access(booking_doc.company, user=user):
		frappe.throw(_("You cannot offer on a booking outside your company"), frappe.PermissionError)
	vehicle_doc = frappe.get_doc("Vehicle", vehicle)
	if not vehicle_doc.is_active or vehicle_doc.status != "Active":
		frappe.throw(_("Vehicle is not active"))
	if vehicle_doc.assigned_captain_user and vehicle_doc.assigned_captain_user != user:
		frappe.throw(_("Vehicle is assigned to another captain"), frappe.PermissionError)
	if vehicle_doc.company and booking_doc.company and vehicle_doc.company != booking_doc.company:
		frappe.throw(_("Vehicle belongs to another company"), frappe.PermissionError)
	if frappe.db.exists("Booking Offer", {"booking": booking, "captain_user": user, "status": "Pending"}):
		frappe.throw(_("You already have a pending offer for this booking"))

	doc = frappe.get_doc({
		"doctype": "Booking Offer",
		"booking": booking,
		"captain_user": user,
		"vehicle": vehicle,
		"offered_fare": offered_fare,
		"fare_type": fare_type,
		"captain_notes": captain_notes,
		"status": "Pending",
		"created_at": now_datetime(),
	})
	doc.insert(ignore_permissions=True)
	return {"name": doc.name, "offered_fare": doc.offered_fare, "status": doc.status}


@frappe.whitelist()
def list_offers(booking):
	"""Rider sees all offers on their booking."""
	user = frappe.session.user
	booking_doc = frappe.get_doc("Trip Booking", booking)
	_require_booking_access(booking_doc, user)
	return frappe.get_all(
		"Booking Offer",
		filters={"booking": booking},
		fields=["name", "captain_user", "vehicle", "offered_fare", "fare_type", "captain_notes", "status", "created_at"],
		order_by="created_at desc",
	)


@frappe.whitelist()
def accept_offer(offer_name):
	"""Rider accepts an offer. Creates Trip, rejects all others."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)

	offer = frappe.get_doc("Booking Offer", offer_name)
	if offer.status != "Pending":
		frappe.throw(_("Offer is no longer available"))

	booking = frappe.get_doc("Trip Booking", offer.booking)
	_require_booking_access(booking, user)
	if not booking.main_rider_user and not has_company_access(booking.company, user=user):
		frappe.throw(_("Only the booking owner or company operator can accept offers"), frappe.PermissionError)
	if booking.negotiation_status != "Awaiting Offers":
		frappe.throw(_("Booking is no longer accepting offers"))

	trip = _create_trip_from_booking(booking, offer)
	return {
		"trip": trip.name,
		"trip_title": trip.trip_title,
		"offer": offer.name,
		"offered_fare": offer.offered_fare,
		"captain": offer.captain_user,
		"vehicle": offer.vehicle,
	}


@frappe.whitelist()
def cancel_booking(booking_name):
	"""Rider cancels their booking."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)

	booking = frappe.get_doc("Trip Booking", booking_name)
	_require_booking_access(booking, user)
	if booking.negotiation_status in ("Trip Created", "Cancelled"):
		frappe.throw(_("Booking cannot be cancelled in current state"))

	booking.db_set("negotiation_status", "Cancelled")
	booking.db_set("booking_status", "Cancelled")

	# Withdraw all pending offers
	pending = frappe.get_all("Booking Offer", filters={"booking": booking_name, "status": "Pending"})
	for o in pending:
		frappe.db.set_value("Booking Offer", o.name, "status", "Withdrawn")
		frappe.db.set_value("Booking Offer", o.name, "responded_at", now_datetime())

	return {"status": "Cancelled"}


@frappe.whitelist()
def reactivate_booking(booking_name):
	"""Rider reactivates their cancelled/inactive booking."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)

	booking = frappe.get_doc("Trip Booking", booking_name)
	_require_booking_access(booking, user)
	if booking.negotiation_status not in ("Cancelled", "Inactive"):
		frappe.throw(_("Booking is not cancelled or inactive"))

	booking.db_set("negotiation_status", "Awaiting Offers")
	booking.db_set("booking_status", "Draft")
	return {"status": "Awaiting Offers"}


@frappe.whitelist()
def join_booking_group(group_code, passenger_name, nationality=None, mobile_no=None,
					   document_type=None, document_number=None, luggage_qty=0, user=None):
	"""Co-passenger joins a booking via group code."""
	if not group_code or not passenger_name:
		frappe.throw(_("Group code and passenger name are required"))
	booking_name = frappe.db.get_value(
		"Trip Booking",
		{"booking_group_code": group_code, "negotiation_status": "Awaiting Offers"},
		"name",
	)
	if not booking_name:
		return {"error": "Booking not found or not accepting passengers"}
	booking = frappe.get_doc("Trip Booking", booking_name)

	booking.append("passengers", {
		"passenger_name": passenger_name,
		"nationality": nationality,
		"mobile_no": mobile_no,
		"document_type": document_type,
		"document_number": document_number,
		"luggage_qty": luggage_qty or 0,
		"booking_group": group_code,
		"is_primary_booker": 0,
		"user": frappe.session.user if frappe.session.user != "Guest" else None,
	})
	# Public joins are intentionally recorded as Guest/registered-user actions;
	# never impersonate Administrator or accept a caller-controlled user.
	booking.save(ignore_permissions=True)

	return {
		"booking": booking.name,
		"booking_title": booking.booking_title,
		"passenger_name": passenger_name,
	}
