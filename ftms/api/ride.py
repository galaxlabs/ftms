from __future__ import annotations

import frappe
from frappe import _

from ftms.tenant import has_company_access


def _require_company_doc_access(doc):
    if frappe.session.user == "Administrator":
        return
    if not doc.get("company") or not has_company_access(doc.get("company")):
        frappe.throw(_("Not permitted for this record"), frappe.PermissionError)


def _require_trip_actor_access(doc):
    user = frappe.session.user
    if user == "Administrator":
        return
    active_captain = frappe.db.exists(
        "Captain Profile",
        {"user": user, "status": "Active"},
    ) and frappe.db.exists(
        "User Company Link",
        {"user": user, "company": doc.company, "role": "Captain", "status": "Active"},
    )
    if doc.assigned_captain_user == user and active_captain:
        return
    frappe.throw(_("Only the assigned captain can complete this trip"), frappe.PermissionError)


@frappe.whitelist()
def transition_trip(name, action):
    """Transition trip state via named action: schedule, depart, arrive, complete, cancel."""
    doc = frappe.get_doc("Trip", name)
    _require_company_doc_access(doc)
    allowed_actions = {"schedule", "depart", "arrive", "complete", "cancel"}
    if action not in allowed_actions:
        frappe.throw(_("Invalid action: {0}").format(action))
    from ftms.ride_machine.state_machine import TripStateMachine
    TripStateMachine(doc).action(action)
    doc.save(ignore_permissions=False)
    return {"status": doc.trip_status, "name": doc.name}


@frappe.whitelist()
def complete_assigned_trip(name=None, booking=None, operation_id=None):
    """Idempotently complete a captain's canonical Frappe trip."""
    if not name and booking:
        name = frappe.db.get_value("Trip Booking", booking, "trip")
    if not name:
        frappe.throw(_("Trip is required"))

    frappe.db.sql("SELECT name FROM `tabTrip` WHERE name=%s FOR UPDATE", name)
    doc = frappe.get_doc("Trip", name)
    _require_trip_actor_access(doc)
    if doc.trip_status == "Completed":
        return {"status": doc.trip_status, "name": doc.name, "already_completed": True}
    if doc.trip_status == "Cancelled":
        frappe.throw(_("A cancelled trip cannot be completed"))

    from ftms.ride_machine.state_machine import BookingStateMachine, TripStateMachine

    for booking_row in frappe.get_all("Trip Booking", filters={"trip": doc.name}, fields=["name"]):
        booking_doc = frappe.get_doc("Trip Booking", booking_row.name)
        booking_machine = BookingStateMachine(booking_doc, "booking_status")
        for action, expected in (
            ("confirm", "Draft"),
            ("check_in", "Confirmed"),
            ("board", "Checked In"),
            ("close", "Boarded"),
        ):
            if booking_doc.booking_status == expected:
                booking_machine.action(action)
        booking_doc.flags.ignore_company_validation = True
        booking_doc.save(ignore_permissions=True)

    machine = TripStateMachine(doc)
    for action, expected in (
        ("schedule", "Draft"),
        ("depart", "Scheduled"),
        ("arrive", "Departed"),
        ("complete", "Arrived"),
    ):
        if doc.trip_status == expected:
            machine.action(action)
    doc.flags.ignore_company_validation = True
    doc.save(ignore_permissions=True)

    frappe.db.set_value(
        "Settlement",
        {"trip": doc.name, "status": "Draft"},
        "status",
        "Approved",
    )
    return {
        "status": doc.trip_status,
        "name": doc.name,
        "booking": doc.trip_booking,
        "operation_id": operation_id,
    }


@frappe.whitelist()
def transition_booking(name, action):
    """Transition booking state via named action: confirm, check_in, board, close, cancel."""
    doc = frappe.get_doc("Trip Booking", name)
    _require_company_doc_access(doc)
    allowed_actions = {"confirm", "check_in", "board", "close", "cancel"}
    if action not in allowed_actions:
        frappe.throw(_("Invalid action: {0}").format(action))
    from ftms.ride_machine.state_machine import BookingStateMachine
    BookingStateMachine(doc, "booking_status").action(action)
    doc.save(ignore_permissions=False)
    return {"status": doc.booking_status, "name": doc.name}


@frappe.whitelist()
def get_trip_state(name):
    """Return current trip state and available transitions."""
    doc = frappe.get_doc("Trip", name)
    _require_company_doc_access(doc)
    from ftms.ride_machine.state_machine import TripStateMachine

    machine = TripStateMachine(doc)
    return {
        "current": doc.trip_status,
        "allowed": machine.transitions.get(doc.trip_status, []),
        "actions": [k for k, v in machine.actions.items() if v in machine.transitions.get(doc.trip_status, [])],
    }


@frappe.whitelist()
def get_booking_state(name):
    """Return current booking state and available transitions."""
    doc = frappe.get_doc("Trip Booking", name)
    _require_company_doc_access(doc)
    from ftms.ride_machine.state_machine import BookingStateMachine

    machine = BookingStateMachine(doc, "booking_status")
    return {
        "current": doc.booking_status,
        "allowed": machine.transitions.get(doc.booking_status, []),
        "actions": [k for k, v in machine.actions.items() if v in machine.transitions.get(doc.booking_status, [])],
    }
