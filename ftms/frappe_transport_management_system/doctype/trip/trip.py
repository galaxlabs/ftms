from __future__ import annotations

import frappe
from frappe.model.document import Document
from ftms.ride_machine.state_machine import TripStateMachine


class Trip(Document):
    def validate(self):
        pass

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
