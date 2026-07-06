from frappe.model.document import Document


class TripBooking(Document):
	def validate(self):
		self.set_booking_title()
		self.update_passenger_count()

	def set_booking_title(self):
		if not self.booking_title and self.customer_name:
			from frappe.utils import now_datetime
			self.booking_title = f"BK-{self.customer_name}-{now_datetime().strftime('%Y%m%d%H%M%S')}"

	def update_passenger_count(self):
		if self.passengers:
			self.passenger_count = len(self.passengers)
