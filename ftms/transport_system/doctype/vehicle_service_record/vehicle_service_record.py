from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class VehicleServiceRecord(Document):
	def validate(self):
		if self.next_service_date and self.service_date and getdate(self.next_service_date) < getdate(self.service_date):
			frappe.throw(_("Next service date cannot be before the service date"))
