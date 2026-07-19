from frappe.model.document import Document


class Vehicle(Document):
	def validate(self):
		self.set_vehicle_code()
		self.set_passenger_capacity()

	def set_vehicle_code(self):
		if not self.vehicle_code and self.plate_no:
			self.vehicle_code = self.plate_no

	def set_passenger_capacity(self):
		if self.seat_capacity and not self.passenger_capacity:
			self.passenger_capacity = self.seat_capacity
		if self.passenger_capacity and not self.seat_capacity:
			self.seat_capacity = self.passenger_capacity
