from frappe.model.document import Document

from ftms.tenant import require_company


class Employee(Document):
	def validate(self):
		require_company(self)
