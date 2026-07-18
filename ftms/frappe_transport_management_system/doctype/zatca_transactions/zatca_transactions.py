from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ZatcaTransactions(Document):
	def validate(self):
		if not self.transaction_date:
			self.transaction_date = frappe.utils.now_datetime()


	if not value or not value.startswith(("http://", "https://")):
		frappe.throw(_("{0} must be a valid URL starting with http:// or https://").format(label))


	import uuid
	return "1-FTMS|2-V15|3-" + str(uuid.uuid4())

