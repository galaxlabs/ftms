from __future__ import annotations

import frappe
from frappe.model.document import Document
from ftms.ride_machine.state_machine import TripStateMachine


class Trip(Document):
    def validate(self):
        if self.assigned_captain_user:
            link = frappe.db.get_value(
                "User Company Link",
                {"user": self.assigned_captain_user, "company": self.company, "role": "Captain", "status": "Active"},
                "name",
            )
            if not link:
                frappe.throw("Assigned captain must be active in this company")
        if self.vehicle and not self.seat_capacity:
            self.seat_capacity = frappe.db.get_value("Vehicle", self.vehicle, "passenger_capacity") or frappe.db.get_value("Vehicle", self.vehicle, "seat_capacity")

    def on_change(self):
        pass

    def schedule(self, departure_datetime=None):
        machine = TripStateMachine(self)
        machine.action("schedule", departure_datetime=departure_datetime)

    def depart(self, actual_departure_datetime=None):
        machine = TripStateMachine(self)
        machine.action("depart", actual_departure_datetime=actual_departure_datetime)

    def arrive(self, actual_arrival_datetime=None):
        machine = TripStateMachine(self)
        machine.action("arrive", actual_arrival_datetime=actual_arrival_datetime)

    def complete(self):
        machine = TripStateMachine(self)
        machine.action("complete")

    def cancel(self):
        machine = TripStateMachine(self)
        machine.action("cancel")
