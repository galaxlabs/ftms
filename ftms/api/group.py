from __future__ import annotations

import frappe
from frappe import _


def _group_access_filter():
	user = frappe.session.user
	if user == "Administrator":
		return {}
	return {"owner_user": user}


def _require_group_access(group_name):
	user = frappe.session.user
	if user == "Administrator":
		return frappe.get_doc("Trip Group", group_name)
	group = frappe.get_doc("Trip Group", group_name)
	if group.owner_user != user:
		frappe.throw(_("You are not permitted to access this group"), frappe.PermissionError)
	return group


def _coerce_passengers(passengers):
	rows = []
	if not isinstance(passengers, (list, tuple)):
		return rows
	for p in passengers or []:
		if not isinstance(p, dict):
			continue
		name = (p.get("passenger_name") or "").strip()
		if not name:
			continue
		rows.append({
			"passenger_name": name,
			"nationality": (p.get("nationality") or "").strip(),
			"document_type": (p.get("document_type") or "Passport").strip(),
			"document_number": (p.get("document_number") or "").strip(),
			"mobile_no": (p.get("mobile_no") or "").strip(),
			"luggage_qty": int(p.get("luggage_qty") or 0),
			"is_primary_booker": 1 if p.get("is_primary_booker") else 0,
		})
	return rows


@frappe.whitelist()
def save_group(
	group_name=None,
	group_leader_name=None,
	group_leader_mobile=None,
	is_group_leader_self=None,
	default_pickup_point=None,
	default_drop_point=None,
	default_vehicle_type=None,
	company=None,
	passengers=None,
	group=None,
):
	"""Create or update a reusable passenger group owned by the caller."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	group_name = (group_name or "").strip()
	if not group_name:
		frappe.throw(_("Group name is required"))
	passenger_rows = _coerce_passengers(passengers)
	if not passenger_rows:
		frappe.throw(_("At least one passenger is required"))

	if group:
		doc = _require_group_access(group)
	else:
		doc = frappe.new_doc("Trip Group")
		doc.owner_user = user

	doc.group_name = group_name
	if group_leader_name is not None:
		doc.group_leader_name = (group_leader_name or "").strip()
	if group_leader_mobile is not None:
		doc.group_leader_mobile = (group_leader_mobile or "").strip()
	if is_group_leader_self is not None:
		doc.is_group_leader_self = 1 if is_group_leader_self in (1, "1", True) else 0
	if default_pickup_point is not None:
		doc.default_pickup_point = (default_pickup_point or "").strip()
	if default_drop_point is not None:
		doc.default_drop_point = (default_drop_point or "").strip()
	if default_vehicle_type is not None:
		doc.default_vehicle_type = (default_vehicle_type or "").strip()
	if company is not None:
		doc.company = (company or "").strip()
	doc.seat_count = len(passenger_rows)
	doc.passengers = []
	for row in passenger_rows:
		doc.append("passengers", row)
	doc.save(ignore_permissions=True)
	return {
		"name": doc.name,
		"group_name": doc.group_name,
		"seat_count": doc.seat_count,
		"passenger_count": len(doc.passengers),
	}


@frappe.whitelist()
def list_my_groups(limit=50):
	"""Return groups owned by the caller, newest first."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	groups = frappe.get_all(
		"Trip Group",
		filters=_group_access_filter(),
		fields=[
			"name", "group_name", "group_leader_name", "group_leader_mobile",
			"is_group_leader_self", "seat_count", "default_pickup_point",
			"default_drop_point", "default_vehicle_type", "times_used",
			"last_used_on",
		],
		order_by="modified desc",
		limit_page_length=int(limit or 50),
	)
	return groups


@frappe.whitelist()
def get_group(group):
	"""Return a saved group with its passenger rows."""
	doc = _require_group_access(group)
	return {
		"name": doc.name,
		"group_name": doc.group_name,
		"group_leader_name": doc.group_leader_name,
		"group_leader_mobile": doc.group_leader_mobile,
		"is_group_leader_self": doc.is_group_leader_self,
		"seat_count": doc.seat_count,
		"default_pickup_point": doc.default_pickup_point,
		"default_drop_point": doc.default_drop_point,
		"default_vehicle_type": doc.default_vehicle_type,
		"passengers": [
			{
				"passenger_name": p.passenger_name,
				"nationality": p.nationality,
				"document_type": p.document_type,
				"document_number": p.document_number,
				"mobile_no": p.mobile_no,
				"luggage_qty": p.luggage_qty,
			}
			for p in (doc.passengers or [])
		],
	}


@frappe.whitelist()
def delete_group(group):
	"""Delete a saved group owned by the caller."""
	doc = _require_group_access(group)
	frappe.delete_doc("Trip Group", doc.name, ignore_permissions=True)
	return {"status": "ok"}


def apply_group_to_booking(booking_doc, group_name, company=None):
	"""Copy a saved group's passengers/leader onto a Trip Booking."""
	group = _require_group_access(group_name)
	if not booking_doc.get("group_leader_name"):
		booking_doc.group_leader_name = group.group_leader_name
		booking_doc.group_leader_mobile = group.group_leader_mobile
		booking_doc.is_group_leader_self = group.is_group_leader_self or 0
	if not booking_doc.get("customer_name"):
		booking_doc.customer_name = group.group_leader_name
	if not booking_doc.get("mobile_no"):
		booking_doc.mobile_no = group.group_leader_mobile
	for p in (group.passengers or []):
		booking_doc.append("passengers", {
			"passenger_name": p.passenger_name,
			"nationality": p.nationality,
			"document_type": p.document_type,
			"document_number": p.document_number,
			"mobile_no": p.mobile_no,
			"luggage_qty": p.luggage_qty,
			"is_primary_booker": 1 if p.is_primary_booker else 0,
		})
	booking_doc.passenger_count = len(booking_doc.passengers)
	booking_doc.seat_count = booking_doc.seat_count or len(booking_doc.passengers)
	# Track reuse of the group
	group.db_set("times_used", int(group.times_used or 0) + 1)
	group.db_set("last_used_on", frappe.utils.today())
	return group.name
