import frappe

from frappe.model.document import Document

from ftms.tenant import require_company
from ftms.utils.naming import booking_title


class FTMSTripBooking(Document):
	def validate(self):
		require_company(self)
		if not self.company and self.trip:
			self.company = frappe.db.get_value("FTMS Trip", self.trip, "company")
		self.set_booking_title()
		self.update_passenger_count()

	def set_booking_title(self):
		if not self.booking_title and self.customer_name:
			self.booking_title = booking_title(self.customer_name, self.route, self.trip)

	def update_passenger_count(self):
		if self.passengers:
			self.passenger_count = len(self.passengers)
