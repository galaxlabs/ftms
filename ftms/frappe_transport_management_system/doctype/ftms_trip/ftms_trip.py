import frappe

from frappe.model.document import Document

from ftms.tenant import require_company
from ftms.utils.calculation import update_trip_counts, update_trip_pricing, update_trip_title_code


class FTMSTrip(Document):
	def validate(self):
		require_company(self)
		if not self.company and self.route:
			self.company = frappe.db.get_value("FTMS Route", self.route, "company")
		self.set_trip_title()
		self.set_trip_code()
		update_trip_title_code(self)
		update_trip_counts(self)
		update_trip_pricing(self)

	def set_trip_title(self):
		if not self.trip_title and self.route and self.driver:
			self.trip_title = f"{self.route} - {self.driver}"
		elif not self.trip_title and self.route:
			self.trip_title = self.route

	def set_trip_code(self):
		if not self.trip_code and self.trip_title:
			self.trip_code = self.trip_title

	def update_available_seats(self):
		if self.seat_capacity and self.passenger_count:
			self.available_seats = self.seat_capacity - self.passenger_count
		elif self.seat_capacity:
			self.available_seats = self.seat_capacity

	def update_passenger_count(self):
		if self.passengers:
			self.passenger_count = len(self.passengers)
