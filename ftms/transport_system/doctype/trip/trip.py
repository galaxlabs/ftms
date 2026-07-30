from __future__ import annotations

import uuid

import frappe
from frappe.model.document import Document
from frappe.utils import getdate
from hijri_converter import Gregorian
import pyqrcode

from ftms.ride_machine.state_machine import TripStateMachine
from ftms.config.service import get_public_frontend_url


class Trip(Document):
	def before_insert(self):
		if not self.public_uuid:
			self.public_uuid = str(uuid.uuid4())
		if self.trip_date and not self.hijri_date:
			g = getdate(self.trip_date)
			h = Gregorian(g.year, g.month, g.day).to_hijri()
			self.hijri_date = f"{h.year:04d}-{h.month:02d}-{h.day:02d}"

	def after_insert(self):
		if self.public_uuid:
			public_url = f"{get_public_frontend_url()}/trip/{self.public_uuid}"
			if not self.public_url:
				self.db_set("public_url", public_url)
			if not self.qr_code:
				qr = pyqrcode.create(public_url)
				self.qr_code = "data:image/png;base64," + qr.png_as_base64_str(scale=6)
				self.db_set("qr_code", self.qr_code)

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
