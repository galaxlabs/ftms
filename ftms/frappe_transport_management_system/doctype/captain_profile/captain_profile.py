from frappe.model.document import Document


class CaptainProfile(Document):
	def validate(self):
		if self.user and not self.full_name:
			self.full_name = self.user
