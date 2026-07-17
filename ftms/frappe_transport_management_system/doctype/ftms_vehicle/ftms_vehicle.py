from frappe.model.document import Document

from ftms.tenant import require_company


class FTMSVehicle(Document):
	def validate(self):
		require_company(self)
		self.set_vehicle_code()

	def set_vehicle_code(self):
		if not self.vehicle_code and self.plate_no:
			self.vehicle_code = self.plate_no
