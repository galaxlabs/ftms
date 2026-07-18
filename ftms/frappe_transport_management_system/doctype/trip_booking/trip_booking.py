from __future__ import annotations

import frappe
from frappe.model.document import Document
from ftms.ride_machine.state_machine import BookingStateMachine


class TripBooking(Document):
    def validate(self):
        pass

    def confirm(self):
        machine = BookingStateMachine(self, "booking_status")
        machine.action("confirm")

    def check_in(self):
        machine = BookingStateMachine(self, "booking_status")
        machine.action("check_in")

    def board(self):
        machine = BookingStateMachine(self, "booking_status")
        machine.action("board")

    def close(self):
        machine = BookingStateMachine(self, "booking_status")
        machine.action("close")

    def cancel(self):
        machine = BookingStateMachine(self, "booking_status")
        machine.action("cancel")
