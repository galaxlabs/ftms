from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime, today

from ftms.api.pricing_rule import calculate_quote
from ftms.penalties.service import calculate_penalty, record_cancellation_penalty
from ftms.notifications.service import emit_event
from ftms.api.partnership import create_agreement_for_booking
from ftms.tenant import get_user_company, has_company_access
from ftms.security import rate_limit


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


def _can_create_booking(user, company=None):
	"""Passengers and operator roles (Company Admin / Dispatcher / owner) may create bookings."""
	if user in ("Guest", "Administrator"):
		return True
	roles = frappe.get_roles()
	if "Passenger" in roles:
		return True
	link = _booking_operator_link(user, company)
	return bool(link)


def _booking_operator_link(user, company=None):
	filters = {"user": user, "status": "Active"}
	if company:
		filters["company"] = company
	links = frappe.get_all(
		"User Company Link",
		filters=filters,
		fields=["company", "role", "is_owner"],
		order_by="modified desc",
	)
	return next(
		(link for link in links if link.is_owner or link.role in ("Company Admin", "Dispatcher")),
		None,
	)


def _booking_detail_access(booking, user):
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	if user == "Administrator" or booking.main_rider_user == user or booking.owner == user:
		return "owner"

	if _booking_operator_link(user, booking.company):
		return "company"

	captain_status = frappe.db.get_value("Captain Profile", {"user": user}, "status")
	if (
		captain_status == "Active"
		and booking.negotiation_status == "Awaiting Offers"
		and booking.booking_status != "Cancelled"
	):
		return "captain"

	frappe.throw(_("You are not permitted to access this booking"), frappe.PermissionError)


def _require_booking_change_access(booking, user):
	if _booking_detail_access(booking, user) not in ("owner", "company"):
		frappe.throw(_("Only the booking owner or company operator can change this booking"), frappe.PermissionError)


def _captain_booking_view(booking, user):
	fields = (
		"name", "company", "booking_date", "route",
		"booking_status", "negotiation_status", "vehicle_type", "passenger_count",
		"seat_count", "pickup_point", "drop_point", "pickup_latitude",
		"pickup_longitude", "dropoff_latitude", "dropoff_longitude", "quoted_fare",
		"minimum_offer_fare", "maximum_offer_fare", "offer_deadline", "demand_index",
		"supply_index",
	)
	data = frappe._dict({field: booking.get(field) for field in fields})
	data.update({"access_level": "captain", "can_cancel": False})
	data["offers"] = frappe.get_all(
		"Booking Offer",
		filters={"booking": booking.name, "captain_user": user},
		fields=["name", "vehicle", "offered_fare", "fare_type", "captain_notes", "status", "created_at"],
		order_by="created_at desc",
	)
	return data


def _generate_group_code():
	return uuid.uuid4().hex[:8].upper()


def _invite_secret():
	secret = frappe.get_site_config().get("secret_key")
	if not secret:
		frappe.throw(_("Public group invitations are not configured"))
	return secret.encode("utf-8")


def _group_invite_token(booking_name, expires_at):
	payload = {
		"v": 1,
		"booking": booking_name,
		"expires_at": int(get_datetime(expires_at).timestamp()),
		"nonce": uuid.uuid4().hex,
	}
	encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
	signature = hmac.new(_invite_secret(), encoded.encode("ascii"), hashlib.sha256).hexdigest()
	return f"{encoded}.{signature}", payload["expires_at"]


def _decode_group_invite(token):
	try:
		encoded, signature = token.split(".", 1)
		valid_signature = hmac.new(_invite_secret(), encoded.encode("ascii"), hashlib.sha256).hexdigest()
		if not hmac.compare_digest(signature, valid_signature):
			raise ValueError
		padding = "=" * (-len(encoded) % 4)
		payload = json.loads(base64.urlsafe_b64decode(f"{encoded}{padding}"))
		if payload.get("v") != 1 or int(payload["expires_at"]) < int(time.time()):
			raise ValueError
		return payload
	except (TypeError, ValueError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
		frappe.throw(_("This group invitation is invalid or expired"), frappe.PermissionError)


def _group_invite_expiry(hours=None):
	configured = frappe.db.get_single_value("Platform Settings", "default_group_invite_expiry_hours")
	try:
		hours = float(hours if hours is not None else configured or 24)
	except (TypeError, ValueError):
		hours = 24
	return max(1, min(hours, 168))


def _create_trip_from_booking(booking, offer):
	"""Convert accepted booking+offer into a Trip."""
	trip_title = f"{booking.customer_name or 'Rider'} - {booking.route or 'Trip'}"
	doc = frappe.get_doc({
		"doctype": "Trip",
		"company": booking.company,
		"trip_title": trip_title,
		"trip_date": booking.booking_date or today(),
		"route": booking.route,
		"from_location": booking.pickup_point,
		"to_location": booking.drop_point,
		"trip_booking": booking.name,
		"booking_ref": booking.name,
		"has_booking": 1,
		"vehicle": offer.vehicle,
		"vehicle_ref": offer.vehicle,
		"has_vehicle": 1,
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
	provider_company = booking.provider_company or frappe.db.get_value("Vehicle", offer.vehicle, "company")
	if provider_company and not frappe.db.exists("Settlement", {"trip": doc.name}):
		platform_fee = float(booking.platform_fee_amount or 0)
		gross_amount = float(offer.offered_fare or 0)
		frappe.get_doc({
			"doctype": "Settlement",
			"company": booking.company,
			"provider_company": provider_company,
			"trip": doc.name,
			"status": "Draft",
			"currency": "SAR",
			"gross_amount": gross_amount,
			"platform_commission": platform_fee,
			"partner_commission": 0,
			"net_amount": max(gross_amount - platform_fee, 0),
		}).insert(ignore_permissions=True)

	booking.db_set("trip", doc.name)
	booking.db_set("trip_ref", doc.name)
	booking.db_set("has_trip", 1)
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
	rate_limit("create_booking", limit=20, seconds=60)
	required_key = frappe.get_site_config().get("transport_hub_api_key")
	sent_key = frappe.get_request_header("X-TransportHub-Key") or frappe.form_dict.get("api_key")
	if required_key and sent_key != required_key:
		frappe.throw(_("Unauthorized"), frappe.PermissionError)

	data = frappe._dict(kwargs)
	if frappe.session.user != "Guest" and not _can_create_booking(frappe.session.user, data.get("company")):
		frappe.throw(
			_("You are not permitted to create bookings"),
			frappe.PermissionError,
		)
	main_rider_user = data.get("main_rider_user")
	if not main_rider_user and frappe.session.user != "Guest":
		main_rider_user = frappe.session.user
	external_reference = data.get("external_reference")
	if external_reference:
		requested_company = data.get("company")
		if frappe.session.user == "Guest" and not main_rider_user and not requested_company:
			frappe.throw(
				_("Company or authenticated rider is required with an external reference"),
				frappe.PermissionError,
			)
		existing = frappe.db.get_value(
			"Trip Booking",
			{"external_reference": external_reference},
			["name", "main_rider_user", "company"],
			as_dict=True,
		)
		if existing:
			if existing.main_rider_user != main_rider_user or (
				requested_company and existing.company != requested_company
			):
				frappe.throw(_("External booking reference belongs to another user"), frappe.PermissionError)
			return _booking_response(frappe.get_doc("Trip Booking", existing.name))
	trip = data.get("trip")
	route = data.get("route")
	if trip and not route:
		route = frappe.db.get_value("Trip", trip, "route")
	company = data.get("company") or (frappe.db.get_value("Trip", trip, "company") if trip else None)
	if not company and frappe.session.user != "Guest":
		from ftms.tenant import get_user_company
		company = get_user_company()

	passengers = _coerce_passengers(data.get("passengers"))
	group_code = _generate_group_code()

	# Reuse a saved passenger group for a new trip/route
	saved_group = data.get("group") or data.get("group_name")
	if saved_group and frappe.session.user != "Guest":
		from ftms.api.group import apply_group_to_booking
		group_passengers = frappe.get_all(
			"Trip Group Passenger",
			filters={"parent": saved_group},
			fields=["passenger_name", "nationality", "document_type", "document_number",
					"mobile_no", "luggage_qty", "is_primary_booker"],
			order_by="idx",
		)
		if group_passengers:
			passengers = _coerce_passengers(group_passengers)

	seat_count = data.get("seat_count") or data.get("passenger_count") or len(passengers) or 1
	booking_title = data.get("booking_title") or " - ".join(
		value for value in [data.get("customer_name"), route or trip or "Booking", group_code] if value
	)

	vehicle_type = data.get("vehicle_type")
	pricing_rule = data.get("pricing_rule")
	quote = None
	if vehicle_type and company:
		quote = calculate_quote(
			company,
			vehicle_type,
			route=route,
			distance_km=data.get("distance_km"),
			passenger_count=seat_count,
			vehicle=data.get("selected_vehicle") or data.get("vehicle"),
			rule_name=pricing_rule,
		)
	if quote:
		pricing_rule = quote["pricing_rule"]
	platform_fee_rate = float(frappe.db.get_single_value("Platform Settings", "platform_fee_rate") or 5)
	quoted_amount = float(quote["final_fare"] if quote else data.get("fare_amount") or 0)

	group_name = data.get("group") or data.get("group_name")
	group_leader_name = data.get("group_leader_name")
	group_leader_mobile = data.get("group_leader_mobile")
	if group_name and frappe.session.user != "Guest":
		group_meta = frappe.db.get_value(
			"Trip Group", group_name, ["group_leader_name", "group_leader_mobile", "is_group_leader_self"],
			as_dict=True,
		)
		if group_meta:
			group_leader_name = group_leader_name or group_meta.get("group_leader_name")
			group_leader_mobile = group_leader_mobile or group_meta.get("group_leader_mobile")

	doc = frappe.get_doc({
		"doctype": "Trip Booking",
		"company": company,
		"booking_title": booking_title,
		"booking_group_code": group_code,
		"external_reference": external_reference,
		"booking_date": data.get("booking_date") or today(),
		"trip": trip,
		"route": route,
		"customer_name": data.get("customer_name") or group_leader_name,
		"mobile_no": data.get("mobile_no") or group_leader_mobile,
		"source_channel": data.get("source_channel") or ("Website" if data.get("main_rider_user") else "API"),
		"main_rider_user": main_rider_user,
		"group_leader_name": group_leader_name,
		"group_leader_mobile": group_leader_mobile,
		"is_group_leader_self": data.get("is_group_leader_self") or 0,
		"fare_amount": quote["final_fare"] if quote else data.get("fare_amount"),
		"quoted_fare": quote["final_fare"] if quote else data.get("fare_amount"),
		"platform_fee_rate": platform_fee_rate,
		"platform_fee_amount": round(quoted_amount * platform_fee_rate / 100, 2),
		"minimum_offer_fare": quote["minimum_fare"] if quote else None,
		"maximum_offer_fare": quote["maximum_fare"] if quote else None,
		"demand_index": quote["demand_index"] if quote else None,
		"supply_index": quote["supply_index"] if quote else None,
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
		"selected_vehicle": data.get("selected_vehicle") or data.get("vehicle"),
		"pricing_rule": pricing_rule,
		"offer_deadline": data.get("offer_deadline"),
		"notes": data.get("notes"),
		"passengers": passengers,
	})

	if saved_group and frappe.session.user != "Guest":
		frappe.db.set_value("Trip Group", saved_group, "times_used", (frappe.db.get_value("Trip Group", saved_group, "times_used") or 0) + 1)
		frappe.db.set_value("Trip Group", saved_group, "last_used_on", today())

	try:
		doc.insert(ignore_permissions=True)
	except frappe.UniqueValidationError:
		if not external_reference:
			raise
		existing_rows = frappe.db.sql(
			"""
			SELECT name, main_rider_user, company
			FROM `tabTrip Booking`
			WHERE external_reference=%s
			FOR UPDATE
			""",
			(external_reference,),
			as_dict=True,
		)
		if not existing_rows:
			raise
		existing_row = existing_rows[0]
		if existing_row.main_rider_user != main_rider_user or (
			data.get("company") and existing_row.company != data.get("company")
		):
			frappe.throw(_("External booking reference belongs to another user"), frappe.PermissionError)
		existing = frappe.get_doc("Trip Booking", existing_row.name)
		return _booking_response(existing)
	return _booking_response(doc)


def _booking_response(doc):
	return {
		"name": doc.name,
		"booking_title": doc.booking_title,
		"booking_group_code": doc.booking_group_code,
		"route": doc.route,
		"trip": doc.trip,
		"passenger_count": doc.passenger_count,
		"negotiation_status": doc.negotiation_status,
		"vehicle_type": doc.vehicle_type,
		"quoted_fare": doc.quoted_fare,
		"minimum_offer_fare": doc.minimum_offer_fare,
		"maximum_offer_fare": doc.maximum_offer_fare,
		"platform_fee_rate": doc.platform_fee_rate,
		"platform_fee_amount": doc.platform_fee_amount,
	}


@frappe.whitelist()
def create_group_invite(booking_name, expires_in_hours=None):
	"""Issue a signed, expiring invite for passengers to join a booking."""
	booking = frappe.get_doc("Trip Booking", booking_name)
	_require_booking_change_access(booking, frappe.session.user)
	if booking.negotiation_status != "Awaiting Offers" or booking.booking_status == "Cancelled":
		frappe.throw(_("This booking is not accepting passengers"))
	expires_at = add_to_date(now_datetime(), hours=_group_invite_expiry(expires_in_hours))
	token, expires_timestamp = _group_invite_token(booking.name, expires_at)
	return {"booking": booking.name, "token": token, "expires_at": expires_timestamp}


@frappe.whitelist()
def list_bookings(company=None, limit=50, mine=None):
	"""List bookings visible to the caller.

	- mine=True (default for app users): only bookings owned by the caller
	  (as main rider or as a joined group passenger).
	- Otherwise: company-scoped bookings (used by ops/admin/captains).
	"""
	user = frappe.session.user if frappe.session.user != "Guest" else None
	if mine and user:
		filters = {"main_rider_user": user}
	elif mine:
		filters = {"name": ("in", [])}
	else:
		if user == "Administrator":
			filters = {"company": company} if company else {}
		else:
			operator_link = _booking_operator_link(user, company)
			if not operator_link:
				frappe.throw(_("Only a company owner, admin, or dispatcher can list company bookings"), frappe.PermissionError)
			filters = {"company": operator_link.company}
	return frappe.get_all(
		"Trip Booking",
		filters=filters,
		fields=[
			"name", "company", "booking_title", "booking_date",
			"customer_name", "mobile_no", "trip", "route",
			"booking_status", "negotiation_status", "vehicle_type",
			"booking_group_code", "main_rider_user",
			"group_leader_name", "group_leader_mobile", "is_group_leader_self",
			"pickup_point", "drop_point",
			"pickup_latitude", "pickup_longitude",
			"dropoff_latitude", "dropoff_longitude",
			"quoted_fare", "minimum_offer_fare", "maximum_offer_fare",
			"passenger_count", "seat_count",
		],
		order_by="booking_date desc, modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def list_available_bookings(company=None, vehicle_type=None, limit=50):
	"""Captains call this to see bookings awaiting offers."""
	user = frappe.session.user
	if frappe.db.get_value("Captain Profile", {"user": user}, "status") != "Active":
		frappe.throw(_("Only an approved captain can view available bookings"), frappe.PermissionError)
	filters = {"negotiation_status": "Awaiting Offers", "booking_status": ("!=", "Cancelled")}
	if company:
		filters["company"] = company
	if vehicle_type:
		filters["vehicle_type"] = vehicle_type
	return frappe.get_all(
		"Trip Booking",
		filters=filters,
		fields=[
			"name", "company", "booking_date", "route",
			"vehicle_type", "pricing_rule", "passenger_count", "quoted_fare",
			"minimum_offer_fare", "maximum_offer_fare", "demand_index", "supply_index",
			"pickup_point", "drop_point",
			"pickup_latitude", "pickup_longitude",
			"dropoff_latitude", "dropoff_longitude",
			"offer_deadline",
		],
		order_by="booking_date asc, modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_booking(name=None, company=None):
	if not name or not frappe.db.exists("Trip Booking", name):
		return None
	doc = frappe.get_doc("Trip Booking", name)
	if company and doc.company != company:
		frappe.throw("Not permitted for this company", frappe.PermissionError)
	access_level = _booking_detail_access(doc, frappe.session.user)
	if access_level == "captain":
		return _captain_booking_view(doc, frappe.session.user)
	data = doc.as_dict()
	data.update({"access_level": access_level, "can_cancel": access_level == "owner"})
	data["offers"] = frappe.get_all(
		"Booking Offer",
		filters={"booking": name},
		fields=["name", "captain_user", "vehicle", "offered_fare", "pricing_rule", "minimum_allowed_fare", "maximum_allowed_fare", "fare_type", "captain_notes", "status", "created_at"],
		order_by="offered_fare desc, created_at asc",
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
	try:
		offered_fare = float(offered_fare)
	except (TypeError, ValueError):
		frappe.throw(_("Offer fare must be a valid amount"))
	vehicle_quote = calculate_quote(
		booking_doc.company,
		booking_doc.vehicle_type,
		route=booking_doc.route,
		passenger_count=booking_doc.seat_count or booking_doc.passenger_count or 1,
		vehicle=vehicle,
	)
	minimum_offer = float((vehicle_quote or {}).get("minimum_fare") or booking_doc.minimum_offer_fare or 0)
	maximum_offer = float((vehicle_quote or {}).get("maximum_fare") or booking_doc.maximum_offer_fare or 0)
	if minimum_offer and offered_fare < minimum_offer:
		frappe.throw(_("Offer is below the configured minimum fare of {0}").format(minimum_offer))
	if maximum_offer and offered_fare > maximum_offer:
		frappe.throw(_("Offer exceeds the configured maximum fare of {0}").format(maximum_offer))
	vehicle_doc = frappe.get_doc("Vehicle", vehicle)
	if not vehicle_doc.is_active or vehicle_doc.status != "Active":
		frappe.throw(_("Vehicle is not active"))
	vehicle_doc.validate_required_documents()
	if vehicle_doc.assigned_captain_user and vehicle_doc.assigned_captain_user != user:
		frappe.throw(_("Vehicle is assigned to another captain"), frappe.PermissionError)
	if vehicle_doc.owner_captain_user and vehicle_doc.owner_captain_user != user:
		frappe.throw(_("Vehicle belongs to another captain"), frappe.PermissionError)
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
		"pricing_rule": (vehicle_quote or {}).get("pricing_rule") or booking_doc.pricing_rule,
		"minimum_allowed_fare": minimum_offer or None,
		"maximum_allowed_fare": maximum_offer or None,
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
	_require_booking_change_access(booking_doc, user)
	return frappe.get_all(
		"Booking Offer",
		filters={"booking": booking},
		fields=["name", "captain_user", "vehicle", "offered_fare", "pricing_rule", "minimum_allowed_fare", "maximum_allowed_fare", "fare_type", "captain_notes", "status", "created_at"],
		order_by="offered_fare desc, created_at asc",
	)


@frappe.whitelist()
def accept_offer(offer_name):
	"""Rider accepts an offer. Creates Trip, rejects all others."""
	from ftms.matching import check_schedule_availability

	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)

	offer = frappe.get_doc("Booking Offer", offer_name)
	if offer.status != "Pending":
		frappe.throw(_("Offer is no longer available"))

	frappe.db.sql("SELECT name FROM `tabTrip Booking` WHERE name=%s FOR UPDATE", offer.booking)
	booking = frappe.get_doc("Trip Booking", offer.booking)
	_require_booking_change_access(booking, user)
	if booking.negotiation_status != "Awaiting Offers":
		frappe.throw(_("Booking is no longer accepting offers"))
	can_accept, reason = check_schedule_availability(offer.captain_user, offer.booking)
	if not can_accept:
		frappe.throw(reason)
	return _accept_offer_for_booking(offer, booking)


@frappe.whitelist()
def accept_booking_as_captain(booking_name, offered_fare, vehicle=None):
	"""Accept an open booking using the authenticated captain's active vehicle."""
	from ftms.matching import check_schedule_availability

	user = frappe.session.user
	profile = frappe.db.get_value("Captain Profile", {"user": user}, ["name", "status"], as_dict=True)
	if user == "Guest" or not profile or profile.status != "Active":
		frappe.throw(_("Only a registered captain can accept a booking"), frappe.PermissionError)

	frappe.db.sql("SELECT name FROM `tabTrip Booking` WHERE name=%s FOR UPDATE", booking_name)
	booking = frappe.get_doc("Trip Booking", booking_name)
	if booking.negotiation_status != "Awaiting Offers":
		if booking.trip and booking.negotiation_status == "Trip Created":
			trip = frappe.get_doc("Trip", booking.trip)
			if trip.assigned_captain_user == user:
				return {"trip": trip.name, "booking": booking.name, "already_accepted": True}
		frappe.throw(_("Booking is no longer accepting offers"))
	active_captain_link = frappe.db.exists(
		"User Company Link",
		{"user": user, "company": booking.company, "role": "Captain", "status": "Active"},
	)
	if booking.company and not active_captain_link:
		frappe.throw(_("You cannot accept a booking outside your company"), frappe.PermissionError)

	vehicle_name = vehicle
	if vehicle_name and not frappe.db.exists("Vehicle", vehicle_name):
		vehicle_name = frappe.db.get_value(
			"Vehicle",
			{"plate_no": vehicle_name, "company": booking.company, "assigned_captain_user": user},
			"name",
		)
	if not vehicle_name:
		vehicle_name = frappe.db.get_value(
			"Vehicle",
			{"company": booking.company, "assigned_captain_user": user, "is_active": 1, "status": "Active"},
			"name",
		)
	if not vehicle_name:
		frappe.throw(_("Assign an active vehicle to this captain before accepting rides"))

	can_accept, reason = check_schedule_availability(user, booking_name)
	if not can_accept:
		frappe.throw(reason)

	offer_result = make_offer(booking.name, vehicle_name, offered_fare)
	offer = frappe.get_doc("Booking Offer", offer_result["name"])
	return _accept_offer_for_booking(offer, booking)


def _accept_offer_for_booking(offer, booking):

	booking.fare_amount = offer.offered_fare
	booking.platform_fee_amount = round(float(offer.offered_fare or 0) * float(booking.platform_fee_rate or 0) / 100, 2)
	booking.save(ignore_permissions=True)
	trip = _create_trip_from_booking(booking, offer)
	provider_company = booking.provider_company or frappe.db.get_value("Vehicle", offer.vehicle, "company")
	create_agreement_for_booking(booking, trip, provider_company)
	emit_event(
		"Offer Accepted",
		booking.main_rider_user,
		"Offer accepted",
		f"Your transport booking has been assigned to {offer.captain_user}.",
		company=booking.company,
		reference_doctype="Trip",
		reference_name=trip.name,
		dedupe_key=f"offer-accepted:{offer.name}",
	)
	emit_event(
		"Trip Assigned",
		offer.captain_user,
		"Trip assignment received",
		f"You have been assigned trip {trip.name}.",
		company=booking.company,
		reference_doctype="Trip",
		reference_name=trip.name,
		dedupe_key=f"trip-assigned:{trip.name}",
	)
	return {
		"trip": trip.name,
		"booking": booking.name,
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
	_require_booking_change_access(booking, user)
	if booking.negotiation_status in ("Trip Created", "Cancelled"):
		frappe.throw(_("Booking cannot be cancelled in current state"))

	penalty = record_cancellation_penalty(
		booking,
		actor_user=user,
		reason="Passenger booking cancellation",
	)
	booking.db_set("negotiation_status", "Cancelled")
	booking.db_set("booking_status", "Cancelled")

	# Withdraw all pending offers
	pending = frappe.get_all("Booking Offer", filters={"booking": booking_name, "status": "Pending"})
	for o in pending:
		frappe.db.set_value("Booking Offer", o.name, "status", "Withdrawn")
		frappe.db.set_value("Booking Offer", o.name, "responded_at", now_datetime())

	return {"status": "Cancelled", "penalty": penalty}


@frappe.whitelist()
def preview_cancellation_penalty(booking_name):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	booking = frappe.get_doc("Trip Booking", booking_name)
	_require_booking_change_access(booking, user)
	return calculate_penalty(booking, actor_user=user) or {"penalty_amount": 0, "currency": "SAR"}


@frappe.whitelist()
def reactivate_booking(booking_name):
	"""Rider reactivates their cancelled/inactive booking."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)

	booking = frappe.get_doc("Trip Booking", booking_name)
	_require_booking_change_access(booking, user)
	if booking.negotiation_status not in ("Cancelled", "Inactive"):
		frappe.throw(_("Booking is not cancelled or inactive"))

	booking.db_set("negotiation_status", "Awaiting Offers")
	booking.db_set("booking_status", "Draft")
	return {"status": "Awaiting Offers"}


@frappe.whitelist()
def start_booking(booking_name):
	"""Passenger owner confirms the ride started / departed for pickup."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	booking = frappe.get_doc("Trip Booking", booking_name)
	access = _booking_detail_access(booking, user)
	if access not in ("owner", "company"):
		frappe.throw(_("Only the booking owner or company operator can start this ride"), frappe.PermissionError)
	if booking.booking_status == "Cancelled" or booking.negotiation_status == "Cancelled":
		frappe.throw(_("A cancelled booking cannot be started"))
	if booking.negotiation_status not in ("Awaiting Offers", "Trip Created", "Confirmed"):
		frappe.throw(_("Booking cannot be started in current state"))
	from ftms.ride_machine.state_machine import BookingStateMachine
	from ftms.ride_machine.state_machine import TripStateMachine

	if booking.trip:
		trip_doc = frappe.get_doc("Trip", booking.trip)
		_try_trip_action(trip_doc, "depart", "Scheduled")
		trip_doc.save(ignore_permissions=True)
	try:
		BookingStateMachine(booking, "booking_status").action("check_in")
		booking.save(ignore_permissions=True)
	except Exception:
		pass
	return {"status": booking.booking_status, "negotiation_status": booking.negotiation_status, "name": booking.name}


def _try_trip_action(trip_doc, action, expected):
	from ftms.ride_machine.state_machine import TripStateMachine
	if trip_doc.trip_status == expected:
		TripStateMachine(trip_doc).action(action)


@frappe.whitelist()
def complete_booking(booking_name):
	"""Assigned captain completes the trip after the ride finishes."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	booking = frappe.get_doc("Trip Booking", booking_name)
	if booking.trip:
		from ftms.api.ride import complete_assigned_trip
		return complete_assigned_trip(name=booking.trip, booking=booking_name)
	frappe.throw(_("No trip is linked to this booking"))


@frappe.whitelist(allow_guest=True)
def join_booking_group(token, passenger_name, nationality=None, mobile_no=None,
					   document_type=None, document_number=None, luggage_qty=0):
	"""Join a booking with a signed, expiring group invitation."""
	rate_limit("join_booking_group", limit=30, seconds=60)
	passenger_name = (passenger_name or "").strip()
	mobile_no = (mobile_no or "").strip()
	nationality = (nationality or "").strip()
	document_type = (document_type or "").strip()
	document_number = (document_number or "").strip()
	if not token or not passenger_name or not mobile_no or not nationality or not document_number:
		frappe.throw(_("Invitation token, full name, mobile, nationality and document number are required"))
	payload = _decode_group_invite(token)
	booking = frappe.get_doc("Trip Booking", payload["booking"])
	frappe.db.sql("SELECT name FROM `tabTrip Booking` WHERE name=%s FOR UPDATE", booking.name)
	booking.reload()
	if booking.negotiation_status != "Awaiting Offers" or booking.booking_status == "Cancelled":
		return {"error": "Booking not found or not accepting passengers"}
	passengers = list(booking.passengers or [])
	seat_count = int(booking.seat_count or 0)
	if seat_count and len(passengers) >= seat_count:
		frappe.throw(_("This booking has no available passenger seats"))
	current_user = frappe.session.user if frappe.session.user != "Guest" else None
	normalized_name = passenger_name.strip().casefold()
	normalized_mobile = (mobile_no or "").strip()
	for existing in passengers:
		if current_user and existing.user == current_user:
			frappe.throw(_("You have already joined this booking"))
		if normalized_mobile and existing.mobile_no == normalized_mobile and (existing.passenger_name or "").strip().casefold() == normalized_name:
			frappe.throw(_("This passenger has already joined the booking"))

	booking.append("passengers", {
		"passenger_name": passenger_name,
		"nationality": nationality,
		"mobile_no": mobile_no,
		"document_type": document_type,
		"document_number": document_number,
		"luggage_qty": luggage_qty or 0,
		"booking_group": booking.booking_group_code,
		"is_primary_booker": 0,
		"user": current_user,
	})
	booking.passenger_count = len(passengers) + 1
	booking.save(ignore_permissions=True)

	return {
		"booking": booking.name,
		"booking_title": booking.booking_title,
		"passenger_name": passenger_name,
		"passenger_count": len(passengers) + 1,
	}
