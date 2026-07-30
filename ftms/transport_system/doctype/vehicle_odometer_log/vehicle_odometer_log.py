from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class VehicleOdometerLog(Document):
	def validate(self):
		previous_rows = frappe.get_all(
			"Vehicle Odometer Log",
			filters={"vehicle": self.vehicle, "name": ("!=", self.name)},
			fields=["reading"],
			order_by="reading_at desc, creation desc",
			limit_page_length=1,
		)
		previous = previous_rows[0].reading if previous_rows else None
		if previous is not None and float(self.reading or 0) < float(previous):
			frappe.throw(_("Odometer reading cannot be lower than the previous reading"))
