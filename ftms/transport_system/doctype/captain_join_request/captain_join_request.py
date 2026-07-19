import frappe
import re
from frappe.model.document import Document
from frappe.utils import now_datetime


class CaptainJoinRequest(Document):
	def validate(self):
		if self.captain_profile:
			user = frappe.db.get_value("Captain Profile", self.captain_profile, "user")
			if user and not self.requested_by:
				self.requested_by = user

	def on_update(self):
		if self.status != "Approved":
			return
		profile = frappe.get_doc("Captain Profile", self.captain_profile)
		link_name = frappe.db.get_value("User Company Link", {"user": profile.user, "company": self.company}, "name")
		if link_name:
			link = frappe.get_doc("User Company Link", link_name)
			link.role = "Captain"
			link.status = "Active"
			link.save(ignore_permissions=True)
		else:
			link_code = re.sub(r"[^A-Z0-9]+", "-", f"{self.company}-{profile.user}".upper()).strip("-")[:140]
			link = frappe.get_doc({
				"doctype": "User Company Link",
				"link_code": link_code,
				"user": profile.user,
				"company": self.company,
				"role": "Captain",
				"status": "Active",
				"approved_by": self.approved_by or frappe.session.user,
				"approved_on": self.approved_on or now_datetime(),
			})
			link.insert(ignore_permissions=True)
		profile.current_company = self.company
		profile.status = "Active"
		profile.approved_by = self.approved_by or frappe.session.user
		profile.approved_on = self.approved_on or now_datetime()
		profile.save(ignore_permissions=True)
