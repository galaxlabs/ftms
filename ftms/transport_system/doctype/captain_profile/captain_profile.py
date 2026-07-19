import frappe
from frappe.model.document import Document


class CaptainProfile(Document):
	def validate(self):
		if self.user and not self.full_name:
			self.full_name = frappe.db.get_value("User", self.user, "full_name") or self.user
		if self.iqama_no and not self.national_id:
			self.national_id = self.iqama_no
