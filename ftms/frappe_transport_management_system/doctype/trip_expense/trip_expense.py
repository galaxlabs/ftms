import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class TripExpense(Document):
	def validate(self):
		if self.trip:
			trip = frappe.db.get_value("Trip", self.trip, ["company", "assigned_captain_user", "vehicle"], as_dict=True)
			if trip:
				if trip.company != self.company:
					frappe.throw("Trip must belong to the selected company")
				if not self.captain_user:
					self.captain_user = trip.assigned_captain_user
				if not self.vehicle:
					self.vehicle = trip.vehicle

		self.net_amount = flt(self.net_amount)
		self.vat_amount = flt(self.vat_amount)
		if not self.total_amount:
			self.total_amount = self.net_amount + self.vat_amount

		if self.captain_user:
			active = frappe.db.exists("User Company Link", {"user": self.captain_user, "company": self.company, "role": "Captain", "status": "Active"})
			if not active:
				frappe.throw("Captain user must be active in the selected company")

	def before_save(self):
		if self.status == "Approved" and not self.approved_on:
			self.approved_by = self.approved_by or frappe.session.user
			self.approved_on = now_datetime()
