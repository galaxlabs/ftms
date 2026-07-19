from frappe.model.document import Document

from ftms.tenant import require_company


class Customer(Document):
	def validate(self):
		require_company(self)
