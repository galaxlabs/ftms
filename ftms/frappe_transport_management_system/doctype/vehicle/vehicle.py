from frappe.model.document import Document


class Vehicle(Document):
	def validate(self):
		self.set_vehicle_code()

	def set_vehicle_code(self):
		if not self.vehicle_code and self.plate_no:
			self.vehicle_code = self.plate_no
