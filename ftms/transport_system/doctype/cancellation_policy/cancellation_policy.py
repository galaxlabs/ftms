from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class CancellationPolicy(Document):
	def validate(self):
		if self.hours_before_min and self.hours_before_max and self.hours_before_min > self.hours_before_max:
			frappe.throw(_("Minimum hours cannot exceed maximum hours"))
		if self.penalty_type == "Percentage" and not 0 <= float(self.penalty_value or 0) <= 100:
			frappe.throw(_("Percentage penalty must be between 0 and 100"))
		if float(self.penalty_value or 0) < 0:
			frappe.throw(_("Penalty value cannot be negative"))
