import frappe
from frappe.model.document import Document


class CaptainProfile(Document):
	def _can_change_approval_status(self):
		if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
			return True
		if not self.current_company:
			return False
		link = frappe.db.get_value(
			"User Company Link",
			{"user": frappe.session.user, "company": self.current_company, "status": "Active"},
			["role", "is_owner"],
			as_dict=True,
		)
		return bool(link and (link.is_owner or link.role == "Company Admin"))

	def validate(self):
		status_changed = (self.is_new() and self.status != "Pending") or (
			not self.is_new() and self.has_value_changed("status")
		)
		if status_changed and not self._can_change_approval_status():
			frappe.throw("Only a System Manager or company administrator can change captain approval status", frappe.PermissionError)
		if self.user and not self.full_name:
			self.full_name = frappe.db.get_value("User", self.user, "full_name") or self.user
		if self.iqama_no and not self.national_id:
			self.national_id = self.iqama_no
