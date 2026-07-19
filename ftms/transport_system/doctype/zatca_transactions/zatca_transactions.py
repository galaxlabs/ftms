import frappe
from frappe.model.document import Document


class ZatcaTransactions(Document):
	def validate(self):
		if not self.transaction_time:
			self.transaction_time = frappe.utils.now_datetime()

