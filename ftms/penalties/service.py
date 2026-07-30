from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from ftms.wallet.service import debit_wallet
from ftms.notifications.service import emit_event


def _trip_start(booking):
	if booking.trip:
		trip = frappe.get_doc("Trip", booking.trip)
		return trip.departure_datetime or get_datetime(trip.trip_date)
	return get_datetime(booking.booking_date)


def _actor_type(booking, actor_user):
	if actor_user == booking.main_rider_user:
		return "Passenger"
	if booking.trip:
		captain = frappe.db.get_value("Trip", booking.trip, "assigned_captain_user")
		if actor_user == captain:
			return "Driver"
	return "Provider"


def _select_policy(booking, actor_type, hours_before):
	policies = frappe.get_all(
		"Cancellation Policy",
		filters={"status": "Active", "actor_type": actor_type},
		fields="*",
	)
	matches = []
	for policy in policies:
		if policy.company and policy.company != booking.company:
			continue
		if policy.service_type and policy.service_type != booking.service_type:
			continue
		if policy.hours_before_min and hours_before < policy.hours_before_min:
			continue
		if policy.hours_before_max and hours_before > policy.hours_before_max:
			continue
		matches.append(policy)
	if not matches:
		return None
	return sorted(
		matches,
		key=lambda policy: (
			1 if policy.company == booking.company else 0,
			1 if policy.service_type == booking.service_type else 0,
			policy.hours_before_min or 0,
		),
		reverse=True,
	)[0]


def calculate_penalty(booking, actor_user=None, actor_type=None):
	actor_user = actor_user or frappe.session.user
	if not actor_user or actor_user == "Guest":
		frappe.throw(_("An authenticated cancellation actor is required"), frappe.PermissionError)
	actor_type = actor_type or _actor_type(booking, actor_user)
	hours_before = max((_trip_start(booking) - now_datetime()).total_seconds() / 3600, 0)
	policy = _select_policy(booking, actor_type, hours_before)
	if not policy:
		return None
	basis_amount = float(booking.fare_amount or booking.quoted_fare or 0)
	if policy.penalty_type == "Fixed":
		amount = float(policy.penalty_value or 0)
	elif policy.penalty_type == "Percentage":
		amount = basis_amount * float(policy.penalty_value or 0) / 100
	else:
		commission_rate = frappe.db.get_single_value("Platform Settings", "platform_commission_rate") or 0
		amount = basis_amount * float(commission_rate) / 100
	if policy.max_penalty:
		amount = min(amount, float(policy.max_penalty))
	return {
		"policy": policy.name,
		"actor_user": actor_user,
		"actor_type": actor_type,
		"hours_before": round(hours_before, 2),
		"basis_amount": round(basis_amount, 2),
		"penalty_amount": round(max(amount, 0), 2),
		"currency": "SAR",
	}


def record_cancellation_penalty(booking, actor_user=None, actor_type=None, reason=None):
	quote = calculate_penalty(booking, actor_user=actor_user, actor_type=actor_type)
	if not quote or quote["penalty_amount"] <= 0:
		return None
	actor_user = quote["actor_user"]
	idempotency_key = f"{booking.name}:{actor_user}:{quote['actor_type']}"
	existing = frappe.db.get_value("Penalty Entry", {"idempotency_key": idempotency_key}, "name")
	if existing:
		return frappe.db.get_value(
			"Penalty Entry",
			existing,
			["name", "penalty_amount", "status"],
			as_dict=True,
		)
	entry = frappe.get_doc({
		"doctype": "Penalty Entry",
		"idempotency_key": idempotency_key,
		"policy": quote["policy"],
		"booking": booking.name,
		"trip": booking.trip,
		"company": booking.company,
		"actor_user": actor_user,
		"actor_type": quote["actor_type"],
		"basis_amount": quote["basis_amount"],
		"penalty_amount": quote["penalty_amount"],
		"currency": quote["currency"],
		"reason": reason or "Cancellation penalty",
		"created_at": now_datetime(),
	})
	entry.insert(ignore_permissions=True)
	collection = debit_wallet(
		user=actor_user,
		amount=entry.penalty_amount,
		currency=entry.currency,
		external_reference=f"penalty:{entry.name}",
		description=reason or "Cancellation penalty",
	)
	if collection["status"] == "debited":
		entry.db_set("status", "Collected")
		emit_event(
			"Penalty Collected",
			actor_user,
			"Cancellation penalty collected",
			f"A penalty of {entry.penalty_amount} {entry.currency} was collected.",
			company=entry.company,
			reference_doctype="Penalty Entry",
			reference_name=entry.name,
			dedupe_key=f"penalty-notice:{entry.name}",
		)
		return {"name": entry.name, "penalty_amount": entry.penalty_amount, "status": "Collected", "wallet_transaction": collection["transaction"]}
	return {"name": entry.name, "penalty_amount": entry.penalty_amount, "status": "Pending", "collection": collection["status"]}
