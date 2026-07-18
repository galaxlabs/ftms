from __future__ import annotations

import frappe
from frappe.model.document import Document


class Route(Document):
	def validate(self):
		if self.source and self.destination:
			if self.source == self.destination:
				frappe.throw("Source and Destination cannot be the same city.")
			if not self.route_title:
				src = frappe.db.get_value("KSA City", self.source, "city_name")
				dst = frappe.db.get_value("KSA City", self.destination, "city_name")
				self.route_title = f"{src} to {dst}"
		if self.route_title and not self.route_name:
			self.route_name = self.route_title
