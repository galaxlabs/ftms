import frappe
from frappe.model.document import Document
from frappe import _


class PricingRule(Document):
	def validate(self):
		if self.vehicle:
			vehicle = frappe.db.get_value("Vehicle", self.vehicle, ["company", "vehicle_type"], as_dict=True)
			if not vehicle or vehicle.company != self.company or vehicle.vehicle_type != self.vehicle_type:
				frappe.throw(_("Specific vehicle must belong to the rule company and vehicle type"))
		if self.distance_min_km and self.distance_max_km and self.distance_min_km > self.distance_max_km:
			frappe.throw(_("Minimum distance cannot exceed maximum distance"))
		if self.min_fare and self.max_fare and self.min_fare > self.max_fare:
			frappe.throw(_("Minimum fare cannot exceed maximum fare"))
