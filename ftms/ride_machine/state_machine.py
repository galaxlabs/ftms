from __future__ import annotations

from frappe import _
from frappe.exceptions import ValidationError


class StateMachine:
    """Generic state machine with transition validation and hooks."""

    transitions: dict[str, list[str]] = {}
    actions: dict[str, str] = {}

    def __init__(self, doc, status_field="status"):
        self.doc = doc
        self.status_field = status_field

    @property
    def current(self):
        return self.doc.get(self.status_field)

    def can_transition(self, new_state):
        allowed = self.transitions.get(self.current, [])
        return new_state in allowed

    def transition(self, new_state, **kwargs):
        if new_state == self.current:
            return
        if not self.can_transition(new_state):
            raise ValidationError(
                _("Cannot transition from {0} to {1}").format(self.current, new_state)
            )
        hook_name = self.actions.get(new_state)
        if hook_name:
            getattr(self, hook_name)(**kwargs)
        self.doc.set(self.status_field, new_state)

    def action(self, name, **kwargs):
        new_state = self.actions.get(name)
        if not new_state:
            raise ValidationError(_("Unknown action: {0}").format(name))
        self.transition(new_state, **kwargs)


class TripStateMachine(StateMachine):
    transitions = {
        "Draft": ["Scheduled", "Cancelled"],
        "Scheduled": ["Departed", "Cancelled"],
        "Departed": ["Arrived", "Cancelled"],
        "Arrived": ["Completed", "Cancelled"],
        "Completed": [],
        "Cancelled": [],
    }

    actions = {
        "schedule": "Scheduled",
        "depart": "Departed",
        "arrive": "Arrived",
        "complete": "Completed",
        "cancel": "Cancelled",
    }

    def schedule(self, **kwargs):
        self.doc.departure_datetime = kwargs.get("departure_datetime") or self.doc.departure_datetime

    def depart(self, **kwargs):
        import frappe
        from frappe.utils import now_datetime
        self.doc.actual_departure_datetime = kwargs.get("actual_departure_datetime") or now_datetime()
        _auto_board_bookings(self.doc)

    def arrive(self, **kwargs):
        from frappe.utils import now_datetime
        self.doc.actual_arrival_datetime = kwargs.get("actual_arrival_datetime") or now_datetime()

    def complete(self, **kwargs):
        _auto_close_checked_in_bookings(self.doc)

    def cancel(self, **kwargs):
        _auto_cancel_bookings(self.doc)
        _unlink_invoice(self.doc)


class BookingStateMachine(StateMachine):
    transitions = {
        "Draft": ["Confirmed", "Cancelled"],
        "Confirmed": ["Checked In", "Cancelled"],
        "Checked In": ["Boarded", "Cancelled"],
        "Boarded": ["Closed", "Cancelled"],
        "Closed": [],
        "Cancelled": [],
    }

    actions = {
        "confirm": "Confirmed",
        "check_in": "Checked In",
        "board": "Boarded",
        "close": "Closed",
        "cancel": "Cancelled",
    }

    def confirm(self, **kwargs):
        _validate_booking_against_trip(self.doc)
        _decrement_available_seats(self.doc)

    def cancel(self, **kwargs):
        _restore_seats(self.doc)


def _auto_board_bookings(trip_doc):
    """When trip departs, auto-board all Checked In bookings."""
    import frappe

    bookings = frappe.get_all(
        "Trip Booking",
        filters={"trip": trip_doc.name, "booking_status": "Checked In"},
        fields=["name"],
    )
    for b in bookings:
        booking = frappe.get_doc("Trip Booking", b.name)
        machine = BookingStateMachine(booking, "booking_status")
        try:
            machine.action("board")
            booking.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(f"Failed to auto-board booking {b.name}")


def _auto_close_checked_in_bookings(trip_doc):
    """When trip completes, close all Boarded bookings."""
    import frappe

    bookings = frappe.get_all(
        "Trip Booking",
        filters={"trip": trip_doc.name, "booking_status": ["in", ("Checked In", "Boarded")]},
        fields=["name"],
    )
    for b in bookings:
        booking = frappe.get_doc("Trip Booking", b.name)
        machine = BookingStateMachine(booking, "booking_status")
        try:
            machine.action("close")
            booking.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(f"Failed to auto-close booking {b.name}")


def _auto_cancel_bookings(trip_doc):
    """When trip is cancelled, cancel all non-closed bookings."""
    import frappe

    bookings = frappe.get_all(
        "Trip Booking",
        filters={"trip": trip_doc.name, "booking_status": ["not in", ("Closed", "Cancelled")]},
        fields=["name"],
    )
    for b in bookings:
        frappe.db.set_value("Trip Booking", b.name, "booking_status", "Cancelled")


def _unlink_invoice(trip_doc):
    """When trip is cancelled, unlink any invoice."""
    if trip_doc.trip_invoice:
        import frappe
        frappe.db.set_value("Trip Invoice", trip_doc.trip_invoice, "trip", None)
        frappe.db.set_value("Trip", trip_doc.name, "trip_invoice", None)


def _validate_booking_against_trip(booking_doc):
    """Validate booking can be confirmed against the trip."""
    import frappe
    from frappe.utils import now_datetime

    if not booking_doc.trip:
        return
    trip = frappe.get_doc("Trip", booking_doc.trip)
    if trip.trip_status in ("Completed", "Cancelled"):
        frappe.throw(_("Cannot confirm booking: Trip is already {0}").format(trip.trip_status))
    if trip.available_seats is not None and trip.available_seats < 1:
        frappe.throw(_("No available seats on this trip"))


def _decrement_available_seats(booking_doc):
    """Reduce available seats when booking is confirmed."""
    import frappe

    if not booking_doc.trip:
        return
    trip = frappe.db.get_value("Trip", booking_doc.trip, "available_seats", as_dict=True)
    if trip and trip.available_seats is not None:
        seats = (booking_doc.seat_count or 1)
        new_available = max(trip.available_seats - seats, 0)
        frappe.db.set_value("Trip", booking_doc.trip, "available_seats", new_available)


def _restore_seats(booking_doc):
    """Restore seats when booking is cancelled."""
    import frappe

    if not booking_doc.trip:
        return
    seats = booking_doc.seat_count or 1
    trip = frappe.db.get_value("Trip", booking_doc.trip, "available_seats", as_dict=True)
    if trip and trip.available_seats is not None:
        frappe.db.set_value("Trip", booking_doc.trip, "available_seats", trip.available_seats + seats)
