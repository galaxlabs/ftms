import frappe
from frappe.model.document import Document


class VehicleAssignment(Document):
	def validate(self):
		if self.vehicle:
			vehicle_company = frappe.db.get_value("Vehicle", self.vehicle, "company")
			if vehicle_company and vehicle_company != self.company:
				frappe.throw("Vehicle must belong to the selected company")
		if self.captain_user:
			active = frappe.db.exists("User Company Link", {"user": self.captain_user, "company": self.company, "role": "Captain", "status": "Active"})
			if not active:
				frappe.throw("Captain user must be active in the selected company")

	def on_update(self):
		if self.status == "Active":
			frappe.db.set_value("Vehicle", self.vehicle, "assigned_captain_user", self.captain_user)
