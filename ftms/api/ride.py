from __future__ import annotations

import frappe
from frappe import _


@frappe.whitelist()
def transition_trip(name, action):
    """Transition trip state via named action: schedule, depart, arrive, complete, cancel."""
    doc = frappe.get_doc("Trip", name)
    method = getattr(doc, action, None)
    if not method:
        frappe.throw(_("Invalid action: {0}").format(action))
    method()
    doc.save(ignore_permissions=False)
    return {"status": doc.trip_status, "name": doc.name}


@frappe.whitelist()
def transition_booking(name, action):
    """Transition booking state via named action: confirm, check_in, board, close, cancel."""
    doc = frappe.get_doc("Trip Booking", name)
    method = getattr(doc, action, None)
    if not method:
        frappe.throw(_("Invalid action: {0}").format(action))
    method()
    doc.save(ignore_permissions=False)
    return {"status": doc.booking_status, "name": doc.name}


@frappe.whitelist()
def get_trip_state(name):
    """Return current trip state and available transitions."""
    doc = frappe.get_doc("Trip", name)
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
    from ftms.ride_machine.state_machine import BookingStateMachine

    machine = BookingStateMachine(doc, "booking_status")
    return {
        "current": doc.booking_status,
        "allowed": machine.transitions.get(doc.booking_status, []),
        "actions": [k for k, v in machine.actions.items() if v in machine.transitions.get(doc.booking_status, [])],
    }
